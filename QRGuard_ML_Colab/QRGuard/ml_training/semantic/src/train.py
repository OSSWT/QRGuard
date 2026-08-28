"""Semantic Training entry point for Google Colab T4.

Run this from ``semantic_training.ipynb``. The script assumes Drive is mounted
and dependencies are installed by the notebook. It keeps the baseline intact, builds a
new domain-grouped data set, calibrates on validation only, runs aggregate,
per-source, and behavioural gates, then exports ONNX. A failed gate leaves all
candidate evidence in Drive but writes ``DEPLOYMENT_REJECTED.json`` and refuses
to describe the artifacts as deployable.
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import pandas as pd
import torch
import tldextract
from datasets import Dataset
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    set_seed,
)

from ml_training.semantic.src.contract import (
    acceptance_cases,
    add_hard_training_examples,
    canonical_url_key,
    evaluate_acceptance,
)

SEED = 42
# Keep reruns versioned and make the Colab output explicit. Override with
# QRGUARD_RUN_TAG when producing a deliberate future experiment.
RUN_TAG = os.environ.get("QRGUARD_RUN_TAG", "semantic-2026.02")
DRIVE_ROOT = Path("/content/drive/MyDrive/FYP2")
BASE = DRIVE_ROOT / "semantic" / RUN_TAG
DATA_DIR = DRIVE_ROOT / "data"
BEST_DIR = BASE / "best_model"
ART = BASE / "artifacts"
for directory in (BASE / "splits", BASE / "eval", ART):
    directory.mkdir(parents=True, exist_ok=True)

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
if DEVICE != "cuda":
    raise SystemExit("Enable a T4 GPU before running Semantic Training.")
print("Device:", torch.cuda.get_device_name(0), "| Run:", RUN_TAG)


def _load_raw() -> pd.DataFrame:
    frames = []
    try:
        from ucimlrepo import fetch_ucirepo

        dataset = fetch_ucirepo(id=967)
        raw = pd.concat([dataset.data.features, dataset.data.targets], axis=1)
    except Exception as exc:
        print("ucimlrepo failed:", exc, "-> Drive CSV fallback")
        raw = pd.read_csv(DATA_DIR / "PhiUSIIL_Phishing_URL_Dataset.csv")
    url_column = next(column for column in raw if column.lower() == "url")
    label_column = next(column for column in raw if column.lower() == "label")
    phi = raw[[url_column, label_column]].rename(
        columns={url_column: "url", label_column: "original_label"}
    )
    majority = phi.original_label.value_counts().idxmax()
    phi["label"] = (phi.original_label != majority).astype(int)
    phi["source"] = "phiusiil"
    frames.append(phi[["url", "label", "source"]])

    malicious = pd.read_csv(DATA_DIR / "malicious_phish.csv")
    url_column = next(column for column in malicious if column.lower() == "url")
    type_column = next(
        column for column in malicious if column.lower() in ("type", "label")
    )
    malicious = malicious[[url_column, type_column]].rename(
        columns={url_column: "url", type_column: "kind"}
    )
    malicious["label"] = (malicious.kind.astype(str).str.lower() != "benign").astype(
        int
    )
    malicious["source"] = "malicious_phish"
    frames.append(malicious[["url", "label", "source"]])

    # Tranco broadens benign registered-domain coverage. Paths are sampled from
    # real benign rows so path presence cannot become a phishing shortcut.
    try:
        from tranco import Tranco

        top = Tranco(cache=True, cache_dir="/content/tranco_cache").list().top(150_000)
    except Exception as exc:
        print("Tranco download failed:", exc, "-> Drive CSV fallback")
        top_frame = pd.read_csv(DATA_DIR / "tranco_top.csv", header=None)
        top = top_frame.iloc[:, -1].astype(str).tolist()[:150_000]

    collected = pd.concat(frames, ignore_index=True)
    benign = collected[collected.label == 0].url.astype(str)

    def path_of(url: str) -> str:
        try:
            return urlsplit(url if "//" in url else "http://" + url).path or "/"
        except ValueError:
            return "/"

    paths = benign.map(path_of)
    paths = paths[paths.str.len() > 1]
    paths = paths.sample(min(60_000, len(paths)), random_state=SEED).tolist()
    generator = np.random.default_rng(SEED)
    augmented = []
    for domain in top:
        domain = str(domain).strip().lower()
        if not domain or " " in domain or "." not in domain:
            continue
        path = paths[int(generator.integers(len(paths)))] if paths and generator.random() < 0.5 else "/"
        augmented.append(f"https://{domain}{path}")
    frames.append(
        pd.DataFrame({"url": augmented, "label": 0, "source": "tranco"})
    )
    combined, cleaning = add_hard_training_examples(pd.concat(frames, ignore_index=True))
    print("Cleaning report:", json.dumps(cleaning, indent=2))
    return combined


def _registered_domain(url: str, extractor) -> str:
    try:
        host = urlsplit(url if "//" in url else "http://" + url).hostname or ""
        extracted = extractor(host)
        return extracted.top_domain_under_public_suffix or host.lower()
    except (TypeError, ValueError):
        return canonical_url_key(url)


def _build_splits(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    split_paths = {name: BASE / "splits" / f"{name}.parquet" for name in ("train", "val", "test")}
    if all(path.exists() for path in split_paths.values()):
        return {name: pd.read_parquet(path) for name, path in split_paths.items()}

    extractor = tldextract.TLDExtract(suffix_list_urls=())
    frame = frame.copy()
    frame["domain"] = frame.url.map(lambda url: _registered_domain(url, extractor))

    # Behavioural "unseen" domains are a true holdout: remove them before any
    # split. Official regression domains may occur in hard training examples;
    # those specifically test the brand-keyword shortcut we are correcting.
    reserved = {
        _registered_domain(case.url, extractor)
        for case in acceptance_cases()
        if case.slice == "unseen_benign"
    }
    frame = frame[~frame.domain.isin(reserved)].reset_index(drop=True)

    hard_domains = set(frame[frame.source.str.startswith("semantic_hard")].domain)
    grouped = frame.groupby("domain").label.agg(["min", "max", "mean"]).reset_index()
    grouped["stratum"] = np.where(
        grouped["min"] != grouped["max"],
        "mixed",
        np.where(grouped["mean"] >= 0.5, "phish", "benign"),
    )
    forced_train = grouped[grouped.domain.isin(hard_domains)]
    remaining = grouped[~grouped.domain.isin(hard_domains)]
    stratify = remaining.stratum if remaining.stratum.value_counts().min() >= 2 else None
    train_groups, rest = train_test_split(
        remaining, test_size=0.30, random_state=SEED, stratify=stratify
    )
    rest_stratify = rest.stratum if rest.stratum.value_counts().min() >= 2 else None
    val_groups, test_groups = train_test_split(
        rest, test_size=0.50, random_state=SEED, stratify=rest_stratify
    )
    train_groups = pd.concat([train_groups, forced_train], ignore_index=True)
    domains = {
        "train": set(train_groups.domain),
        "val": set(val_groups.domain),
        "test": set(test_groups.domain),
    }
    assert not domains["train"] & domains["val"]
    assert not domains["train"] & domains["test"]
    assert not domains["val"] & domains["test"]

    splits = {}
    for name, selected in domains.items():
        part = frame[frame.domain.isin(selected)][["url", "label", "source", "domain"]]
        if name == "train" and len(part) > 200_000:
            hard = part[part.source.str.startswith("semantic_hard")]
            ordinary = part[~part.source.str.startswith("semantic_hard")]
            ordinary = ordinary.sample(200_000 - len(hard), random_state=SEED)
            part = pd.concat([ordinary, hard]).sample(frac=1, random_state=SEED)
        splits[name] = part.reset_index(drop=True)
        splits[name].to_parquet(split_paths[name])
        print(name, len(part), "phishing", round(float(part.label.mean()), 4))
    return splits


clean_path = BASE / "splits" / "combined_clean.parquet"
if clean_path.exists():
    data = pd.read_parquet(clean_path)
else:
    data = _load_raw()
    data.to_parquet(clean_path)
splits = _build_splits(data)

MODEL_ID = "amahdaouy/DomURLs_BERT"
MAX_LEN = 128
set_seed(SEED)
tokenizer = AutoTokenizer.from_pretrained(BEST_DIR if (BEST_DIR / "config.json").exists() else MODEL_ID)


def _tokenize(batch):
    return tokenizer(batch["url"], truncation=True, max_length=MAX_LEN)


datasets = {
    name: Dataset.from_pandas(part[["url", "label"]], preserve_index=False).map(
        _tokenize, batched=True, remove_columns=["url"]
    )
    for name, part in splits.items()
}


def _trainer_metrics(evaluation):
    logits, labels = evaluation
    probabilities = torch.softmax(torch.tensor(logits), -1)[:, 1].numpy()
    predictions = (probabilities >= 0.5).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="binary", zero_division=0
    )
    return {
        "accuracy": accuracy_score(labels, predictions),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": roc_auc_score(labels, probabilities),
    }


if not (BEST_DIR / "config.json").exists():
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, num_labels=2)
    common = dict(
        output_dir="/content/semantic_training_checkpoints",
        num_train_epochs=3,
        learning_rate=2e-5,
        warmup_ratio=0.1,
        weight_decay=0.01,
        per_device_train_batch_size=32,
        per_device_eval_batch_size=64,
        fp16=True,
        seed=SEED,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        save_total_limit=1,
        logging_steps=200,
        report_to="none",
    )
    try:
        arguments = TrainingArguments(eval_strategy="epoch", save_strategy="epoch", **common)
    except TypeError:
        arguments = TrainingArguments(evaluation_strategy="epoch", save_strategy="epoch", **common)
    trainer = Trainer(
        model=model,
        args=arguments,
        train_dataset=datasets["train"],
        eval_dataset=datasets["val"],
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=_trainer_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=1)],
    )
    trainer.train()
    trainer.save_model(BEST_DIR)
    tokenizer.save_pretrained(BEST_DIR)

model = AutoModelForSequenceClassification.from_pretrained(BEST_DIR).eval().to(DEVICE)
tokenizer = AutoTokenizer.from_pretrained(BEST_DIR)


def logits_for(urls: list[str], batch_size: int = 256) -> np.ndarray:
    output = []
    with torch.no_grad():
        for index in range(0, len(urls), batch_size):
            encoded = tokenizer(
                urls[index : index + batch_size],
                truncation=True,
                max_length=MAX_LEN,
                padding=True,
                return_tensors="pt",
            ).to(DEVICE)
            output.append(model(**encoded).logits.float().cpu())
    return torch.cat(output).numpy()


def metric_slice(labels: np.ndarray, probabilities: np.ndarray) -> dict:
    predictions = (probabilities >= 0.5).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="binary", zero_division=0
    )
    return {
        "n": len(labels),
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "roc_auc": float(roc_auc_score(labels, probabilities)) if len(set(labels)) > 1 else None,
    }


test = splits["test"]
test_logits = logits_for(test.url.tolist())
np.save(BASE / "eval" / "test_logits.npy", test_logits)
test_labels = test.label.to_numpy()
raw_probabilities = torch.softmax(torch.tensor(test_logits), -1)[:, 1].numpy()
metrics = {"overall": metric_slice(test_labels, raw_probabilities), "per_source": {}}
for source in sorted(test.source.unique()):
    mask = (test.source == source).to_numpy()
    metrics["per_source"][source] = metric_slice(test_labels[mask], raw_probabilities[mask])

# Temperature is fitted on validation only and applied to every acceptance/export check.
validation = splits["val"]
validation_logits = torch.tensor(logits_for(validation.url.tolist()))
validation_labels = torch.tensor(validation.label.to_numpy())
temperature_parameter = torch.nn.Parameter(torch.ones(1))
optimizer = torch.optim.LBFGS([temperature_parameter], lr=0.05, max_iter=200)
loss_function = torch.nn.CrossEntropyLoss()


def _calibration_closure():
    optimizer.zero_grad()
    loss = loss_function(
        validation_logits / temperature_parameter.clamp(min=1e-3), validation_labels
    )
    loss.backward()
    return loss


optimizer.step(_calibration_closure)
temperature = float(temperature_parameter.detach().clamp(min=1e-3))


def _ece(probabilities: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    edges = np.linspace(0, 1, bins + 1)
    confidence = np.maximum(probabilities, 1 - probabilities)
    correct = (probabilities >= 0.5).astype(int) == labels
    total = 0.0
    for lower, upper in zip(edges[:-1], edges[1:], strict=True):
        selected = (confidence > lower) & (confidence <= upper)
        if selected.any():
            total += float(selected.mean()) * abs(
                float(correct[selected].mean()) - float(confidence[selected].mean())
            )
    return total


test_tensor = torch.tensor(test_logits)
calibrated_test_probabilities = torch.softmax(test_tensor / temperature, -1)[:, 1].numpy()
calibration = {
    "temperature": temperature,
    "ece_before": _ece(raw_probabilities, test_labels),
    "ece_after": _ece(calibrated_test_probabilities, test_labels),
}
(ART / "temperature.json").write_text(
    json.dumps(calibration, indent=2), encoding="utf-8"
)

cases = acceptance_cases()
case_logits = logits_for([case.url for case in cases])
case_probabilities = torch.softmax(torch.tensor(case_logits) / temperature, -1)[:, 1].numpy()
behavioural = evaluate_acceptance(case_probabilities, cases)
(BASE / "eval" / "behavioural_acceptance.json").write_text(
    json.dumps(behavioural, indent=2), encoding="utf-8"
)

gate_failures = list(behavioural["failures"])
if calibration["ece_after"] > 0.03:
    gate_failures.append(f"calibrated ECE {calibration['ece_after']:.4f} > 0.03")
for source, source_metrics in metrics["per_source"].items():
    auc = source_metrics["roc_auc"]
    if auc is not None and auc < 0.90:
        gate_failures.append(f"{source} ROC-AUC {auc:.4f} < 0.90")

# Export and quantify INT8; the deploy selector is written only after all gates pass.
from onnxruntime.quantization import QuantType, quantize_dynamic
from optimum.onnxruntime import ORTModelForSequenceClassification
import onnxruntime as ort

fp32_dir = ART / "onnx_fp32"
if not (fp32_dir / "model.onnx").exists():
    ORTModelForSequenceClassification.from_pretrained(BEST_DIR, export=True).save_pretrained(fp32_dir)
quant_path = ART / "model_quant.onnx"
if not quant_path.exists():
    quantize_dynamic(fp32_dir / "model.onnx", quant_path, weight_type=QuantType.QInt8)
tokenizer.save_pretrained(ART)


def _session(path: Path):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def _onnx_logits(session, urls: list[str], batch_size: int = 64) -> np.ndarray:
    names = {item.name for item in session.get_inputs()}
    output = []
    for index in range(0, len(urls), batch_size):
        encoded = tokenizer(
            urls[index : index + batch_size],
            truncation=True,
            max_length=MAX_LEN,
            padding=True,
            return_tensors="np",
        )
        inputs = {
            key: value.astype(np.int64)
            for key, value in encoded.items()
            if key in names
        }
        output.append(session.run(None, inputs)[0])
    return np.concatenate(output)


sample = test.sample(min(2_000, len(test)), random_state=SEED)
sample_labels = sample.label.to_numpy()


def _f1(logits: np.ndarray) -> float:
    probability = torch.softmax(torch.tensor(logits), -1)[:, 1].numpy()
    prediction = (probability >= 0.5).astype(int)
    return float(
        precision_recall_fscore_support(
            sample_labels, prediction, average="binary", zero_division=0
        )[2]
    )


torch_f1 = _f1(logits_for(sample.url.tolist()))
fp32_session = _session(fp32_dir / "model.onnx")
int8_session = _session(quant_path)
int8_f1 = _f1(_onnx_logits(int8_session, sample.url.tolist()))
quant_drop_pp = (torch_f1 - int8_f1) * 100
deploy_model = quant_path.name if quant_drop_pp <= 2.0 else "onnx_fp32/model.onnx"

summary = {
    "run": RUN_TAG,
    "metrics": metrics,
    "calibration": calibration,
    "behavioural_acceptance": behavioural,
    "quantization": {
        "torch_f1": torch_f1,
        "int8_f1": int8_f1,
        "drop_pp": quant_drop_pp,
        "candidate": deploy_model,
    },
    "deployment_gates_passed": not gate_failures,
    "deployment_gate_failures": gate_failures,
    "completed_at_epoch_seconds": time.time(),
}
(ART / "metrics_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
if gate_failures:
    (ART / "DEPLOYMENT_REJECTED.json").write_text(
        json.dumps({"failures": gate_failures}, indent=2), encoding="utf-8"
    )
    raise RuntimeError("Semantic Training export rejected: " + "; ".join(gate_failures))
(ART / "deploy_choice.json").write_text(
    json.dumps({"deploy_model": deploy_model}, indent=2), encoding="utf-8"
)
print("Semantic Training passed every gate ->", ART)
