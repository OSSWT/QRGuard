"""Train, calibrate, evaluate and export the local Structural candidate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "ml_training/.matplotlib_cache"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
from PIL import Image  # noqa: E402
from scipy.optimize import minimize_scalar  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    precision_recall_fscore_support,
    roc_curve,
)
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler  # noqa: E402
from torchvision import models, transforms  # noqa: E402

from ml_training.structural.src.structural_recipes import (  # noqa: E402
    CLASS_NAMES,
    MANIFEST,
    VERSION,
    prepare_dataset,
)


SEED = 42
RUN = ROOT / "ml_training/structural/runs" / VERSION
ARTIFACTS = RUN / "artifacts"
PERFORMANCE = ROOT / "ml_training/structural/performance" / VERSION
BATCH_SIZE = 32
HEAD_EPOCHS = 2
FINETUNE_EPOCHS = 5
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


class ManifestDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, transform) -> None:
        self.frame = frame.reset_index(drop=True)
        self.transform = transform

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int):
        row = self.frame.iloc[index]
        with Image.open(ROOT / row.path) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, int(row.class_id), index


def _transforms(training: bool):
    steps = [transforms.Resize((224, 224), antialias=True)]
    if training:
        steps.extend(
            [
                transforms.RandomApply(
                    [
                        transforms.ColorJitter(
                            brightness=0.12, contrast=0.12, saturation=0.08
                        )
                    ],
                    p=0.35,
                ),
                transforms.RandomRotation(4, fill=255),
                transforms.RandomPerspective(distortion_scale=0.08, p=0.20, fill=255),
            ]
        )
    steps.extend(
        [transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)]
    )
    return transforms.Compose(steps)


def _sampler(frame: pd.DataFrame) -> WeightedRandomSampler:
    """Balance classes and the three very unequal clean-camera sources."""
    weights = np.zeros(len(frame), dtype=np.float64)
    for class_id in (0, 1, 2):
        class_mask = frame.class_id.to_numpy() == class_id
        sources = frame.loc[class_mask, "source"].unique().tolist()
        if not sources:
            continue
        has_runtime = "qrguard_runtime" in sources
        runtime_share = 0.40 if has_runtime else 0.0
        non_runtime = [source for source in sources if source != "qrguard_runtime"]
        if class_id == 0:
            preferred = {
                "QR-DN1.0": 0.60,
                "procedural_qrguard": 0.30,
                "qr_codes_in_surfaces": 0.10,
            }
            present_total = sum(preferred.get(source, 0.0) for source in non_runtime)
            shares = {
                source: (1 - runtime_share)
                * (
                    preferred.get(source, 0.0) / present_total
                    if present_total
                    else 1 / max(len(non_runtime), 1)
                )
                for source in non_runtime
            }
        else:
            shares = {
                source: (1 - runtime_share) / max(len(non_runtime), 1)
                for source in non_runtime
            }
        if has_runtime:
            shares["qrguard_runtime"] = runtime_share
        for source, source_share in shares.items():
            mask = class_mask & (frame.source.to_numpy() == source)
            if mask.any():
                weights[mask] = (1 / 3) * source_share / int(mask.sum())
    if np.any(weights <= 0):
        missing = frame.loc[weights <= 0, ["label", "source"]].drop_duplicates()
        raise ValueError(f"sampler has uncovered rows:\n{missing}")
    return WeightedRandomSampler(
        torch.as_tensor(weights, dtype=torch.double),
        num_samples=len(frame),
        replacement=True,
        generator=torch.Generator().manual_seed(SEED),
    )


def _model() -> nn.Module:
    model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
    model.fc = nn.Sequential(nn.Dropout(0.20), nn.Linear(model.fc.in_features, 3))
    return model


def _set_stage(model: nn.Module, stage: str) -> None:
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.fc.parameters():
        parameter.requires_grad = True
    if stage == "finetune":
        for parameter in model.layer4.parameters():
            parameter.requires_grad = True


def _predict(model, loader, device) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    logits, labels, indices = [], [], []
    with torch.no_grad():
        for images, targets, row_indices in loader:
            logits.append(model(images.to(device)).cpu().numpy())
            labels.append(targets.numpy())
            indices.append(row_indices.numpy())
    return np.concatenate(logits), np.concatenate(labels), np.concatenate(indices)


def _probabilities(logits: np.ndarray, temperature: float) -> np.ndarray:
    scaled = logits / temperature
    exponential = np.exp(scaled - scaled.max(axis=1, keepdims=True))
    return exponential / exponential.sum(axis=1, keepdims=True)


def _ece(labels: np.ndarray, probabilities: np.ndarray, bins: int = 15) -> float:
    confidence = probabilities.max(axis=1)
    prediction = probabilities.argmax(axis=1)
    edges = np.linspace(0, 1, bins + 1)
    value = 0.0
    for lower, upper in zip(edges[:-1], edges[1:], strict=True):
        mask = (confidence >= lower) & (
            (confidence <= upper) if upper == 1 else (confidence < upper)
        )
        if mask.any():
            value += mask.mean() * abs(
                (prediction[mask] == labels[mask]).mean() - confidence[mask].mean()
            )
    return float(value)


def _fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    def objective(log_temperature: float) -> float:
        probabilities = _probabilities(logits, float(np.exp(log_temperature)))
        selected = np.clip(probabilities[np.arange(len(labels)), labels], 1e-12, 1)
        return float(-np.log(selected).mean())

    result = minimize_scalar(objective, bounds=(-3, 3), method="bounded")
    return float(np.exp(result.x))


def _class_metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict:
    predictions = probabilities.argmax(axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(
        labels,
        predictions,
        labels=[0, 1, 2],
        zero_division=0,
    )
    return {
        "n": int(len(labels)),
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(f1.mean()),
        "ece": _ece(labels, probabilities),
        "per_class": {
            name: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index, name in enumerate(CLASS_NAMES)
        },
    }


def _clean_metrics(frame: pd.DataFrame, probabilities: np.ndarray) -> dict:
    p_structural = 1 - probabilities[:, 0]
    return {
        "n": int(len(frame)),
        "qr_identities": int(frame.group_id.nunique()),
        "false_positive_rate_at_0_5": float((p_structural >= 0.5).mean()),
        "nonclean_class_rate": float((probabilities.argmax(axis=1) != 0).mean()),
        "median_p_structural": float(np.median(p_structural)),
        "p95_p_structural": float(np.percentile(p_structural, 95)),
        "maximum_p_structural": float(p_structural.max()),
    }


def _save_figures(
    history: list[dict],
    test_labels: np.ndarray,
    test_probabilities: np.ndarray,
    qrdn_probabilities: np.ndarray,
) -> None:
    PERFORMANCE.mkdir(parents=True, exist_ok=True)
    history_frame = pd.DataFrame(history)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].plot(history_frame.epoch, history_frame.train_loss, marker="o")
    axes[0].set(title="Training loss", xlabel="Epoch", ylabel="Cross-entropy")
    axes[1].plot(history_frame.epoch, history_frame.validation_macro_f1, marker="o")
    axes[1].set(
        title="Validation macro-F1", xlabel="Epoch", ylabel="Macro-F1", ylim=(0, 1)
    )
    figure.suptitle("Structural Training — convergence")
    figure.tight_layout()
    figure.savefig(PERFORMANCE / "training_curves.png", dpi=180)
    plt.close(figure)

    matrix = confusion_matrix(
        test_labels, test_probabilities.argmax(axis=1), labels=[0, 1, 2]
    )
    plt.figure(figsize=(6, 5))
    sns.heatmap(
        matrix,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=CLASS_NAMES,
        yticklabels=CLASS_NAMES,
    )
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("Structural Training — grouped synthetic test")
    plt.tight_layout()
    plt.savefig(PERFORMANCE / "confusion_matrix.png", dpi=180)
    plt.close()

    p_structural = 1 - qrdn_probabilities[:, 0]
    plt.figure(figsize=(6.5, 4.5))
    plt.hist(p_structural, bins=40, color="#d98247", alpha=0.85)
    plt.axvline(0.5, color="black", linestyle="--", label="risk threshold")
    plt.xlabel("p_structural")
    plt.ylabel("QR-DN clean images")
    plt.title("Structural Training — external camera-derived clean holdout")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PERFORMANCE / "qrdn_clean_distribution.png", dpi=180)
    plt.close()

    binary_labels = (test_labels != 0).astype(int)
    p_structural = 1 - test_probabilities[:, 0]
    fpr, tpr, _ = roc_curve(binary_labels, p_structural)
    precision, recall, _ = precision_recall_curve(binary_labels, p_structural)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].plot(fpr, tpr)
    axes[0].plot([0, 1], [0, 1], "--", color="grey")
    axes[0].set(
        title="Structural risk ROC",
        xlabel="False-positive rate",
        ylabel="True-positive rate",
    )
    axes[1].plot(recall, precision)
    axes[1].set(
        title="Structural risk precision-recall",
        xlabel="Recall",
        ylabel="Precision",
    )
    figure.suptitle("Structural Training — clean versus manipulated")
    figure.tight_layout()
    figure.savefig(PERFORMANCE / "roc_pr_curves.png", dpi=180)
    plt.close(figure)

    predicted, observed = [], []
    for lower, upper in zip(
        np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:], strict=True
    ):
        mask = (p_structural >= lower) & (
            (p_structural <= upper) if upper == 1 else (p_structural < upper)
        )
        if mask.any():
            predicted.append(float(p_structural[mask].mean()))
            observed.append(float(binary_labels[mask].mean()))
    plt.figure(figsize=(5, 5))
    plt.plot([0, 1], [0, 1], "--", color="grey")
    plt.plot(predicted, observed, marker="o")
    plt.xlabel("Mean predicted structural risk")
    plt.ylabel("Observed manipulated fraction")
    plt.title("Structural Training — calibration")
    plt.tight_layout()
    plt.savefig(PERFORMANCE / "calibration_curve.png", dpi=180)
    plt.close()


def _runtime_metrics(frame: pd.DataFrame, probabilities: np.ndarray) -> dict:
    if frame.empty:
        return {
            "n": 0,
            "clean_false_positive_rate": None,
            "adversarial_recall": None,
            "tampered_recall": None,
        }
    predictions = probabilities.argmax(axis=1)
    result = {"n": int(len(frame))}
    for class_id, name in enumerate(CLASS_NAMES):
        mask = frame.class_id.to_numpy(dtype=int) == class_id
        if not mask.any():
            value = None
        elif class_id == 0:
            value = float((predictions[mask] != 0).mean())
        else:
            value = float((predictions[mask] == class_id).mean())
        key = "clean_false_positive_rate" if class_id == 0 else f"{name}_recall"
        result[key] = value
    return result


def _slice_row(name: str, frame: pd.DataFrame, probabilities: np.ndarray) -> dict:
    metrics = _class_metrics(frame.class_id.to_numpy(dtype=int), probabilities)
    return {
        "slice": name,
        "rows": len(frame),
        "accuracy": metrics["accuracy"],
        "macro_f1": metrics["macro_f1"],
        "ece": metrics["ece"],
        **{
            f"{class_name}_recall": metrics["per_class"][class_name]["recall"]
            for class_name in CLASS_NAMES
        },
    }


def _write_complete_tables(
    test_frame: pd.DataFrame,
    test_probabilities: np.ndarray,
    external_frame: pd.DataFrame,
    external_probabilities: np.ndarray,
    runtime_frame: pd.DataFrame,
    runtime_probabilities: np.ndarray,
) -> None:
    source_rows = []
    for source in sorted(test_frame.source.unique()):
        mask = (test_frame.source == source).to_numpy()
        source_rows.append(
            _slice_row(
                f"grouped_test/{source}", test_frame[mask], test_probabilities[mask]
            )
        )
    source_rows.append(
        {
            "slice": "external_holdout/QR-DN1.0",
            "rows": len(external_frame),
            "accuracy": float((external_probabilities.argmax(axis=1) == 0).mean()),
            "macro_f1": None,
            "ece": None,
            "clean_recall": float((external_probabilities.argmax(axis=1) == 0).mean()),
            "adversarial_recall": None,
            "tampered_recall": None,
        }
    )
    if not runtime_frame.empty:
        source_rows.append(
            _slice_row(
                "runtime_holdout/qrguard_app", runtime_frame, runtime_probabilities
            )
        )
    pd.DataFrame(source_rows).to_csv(
        PERFORMANCE / "per_source_results.csv", index=False
    )

    if runtime_frame.empty:
        device_rows = [
            {
                "status": "not_evaluated",
                "reason": "exact app-camera test captures missing",
            }
        ]
    else:
        device_rows = []
        for device in sorted(
            runtime_frame.device_model.fillna("not_recorded").unique()
        ):
            mask = (
                runtime_frame.device_model.fillna("not_recorded") == device
            ).to_numpy()
            device_rows.append(
                {
                    "status": "evaluated",
                    "device_model": device,
                    **_slice_row(
                        device, runtime_frame[mask], runtime_probabilities[mask]
                    ),
                }
            )
    pd.DataFrame(device_rows).to_csv(
        PERFORMANCE / "per_device_results.csv", index=False
    )

    # A valid consistency metric needs the same physical/payload group captured
    # once through Gallery and once through the exact app camera pipeline.
    pd.DataFrame(
        [
            {
                "status": "not_evaluated",
                "paired_groups": 0,
                "reason": "paired Gallery and exact-camera captures are required",
            }
        ]
    ).to_csv(PERFORMANCE / "gallery_camera_consistency.csv", index=False)

    mistakes = []
    for split, frame, probabilities in (
        ("grouped_test", test_frame, test_probabilities),
        ("runtime_holdout_test", runtime_frame, runtime_probabilities),
    ):
        if frame.empty:
            continue
        predictions = probabilities.argmax(axis=1)
        for index in np.flatnonzero(predictions != frame.class_id.to_numpy(dtype=int)):
            row = frame.iloc[index]
            mistakes.append(
                {
                    "split": split,
                    "sample_path": row.path,
                    "group_id": row.group_id,
                    "actual": row.label,
                    "predicted": CLASS_NAMES[predictions[index]],
                    "p_clean": float(probabilities[index, 0]),
                    "p_adversarial": float(probabilities[index, 1]),
                    "p_tampered": float(probabilities[index, 2]),
                }
            )
    pd.DataFrame(
        mistakes,
        columns=[
            "split",
            "sample_path",
            "group_id",
            "actual",
            "predicted",
            "p_clean",
            "p_adversarial",
            "p_tampered",
        ],
    ).to_csv(PERFORMANCE / "misclassified_samples.csv", index=False)


def _export(model: nn.Module, temperature: float) -> dict:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    model_path = ARTIFACTS / "structural_fp32.onnx"
    dummy = torch.randn(1, 3, 224, 224)
    torch.onnx.export(
        model.cpu().eval(),
        dummy,
        model_path,
        input_names=["pixel_values"],
        output_names=["logits"],
        dynamic_axes={"pixel_values": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    (ARTIFACTS / "temperature.json").write_text(
        json.dumps({"temperature": temperature}, indent=2), encoding="utf-8"
    )
    (ARTIFACTS / "deploy_choice.json").write_text(
        json.dumps({"deploy_model": model_path.name}, indent=2), encoding="utf-8"
    )
    return {
        "path": model_path,
        "bytes": model_path.stat().st_size,
        "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
    }


def _onnx_audit(
    artifact: Path, model: nn.Module, samples: torch.Tensor, temperature: float
) -> dict:
    import onnxruntime as ort

    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = 1
    session = ort.InferenceSession(
        str(artifact), session_options, providers=["CPUExecutionProvider"]
    )
    input_name = session.get_inputs()[0].name
    array = samples.numpy().astype(np.float32)
    with torch.no_grad():
        torch_logits = model.cpu().eval()(samples).numpy()
    onnx_logits = session.run(None, {input_name: array})[0]
    parity = float(np.max(np.abs(torch_logits - onnx_logits)))
    for _ in range(10):
        session.run(None, {input_name: array[:1]})
    timings = []
    for _ in range(100):
        started = time.perf_counter()
        session.run(None, {input_name: array[:1]})
        timings.append((time.perf_counter() - started) * 1000)
    probability_error = float(
        np.max(
            np.abs(
                _probabilities(torch_logits, temperature)
                - _probabilities(onnx_logits, temperature)
            )
        )
    )
    return {
        "max_abs_logit_error": parity,
        "max_abs_probability_error": probability_error,
        "latency_median_ms": float(np.median(timings)),
        "latency_p95_ms": float(np.percentile(timings, 95)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument(
        "--rebuild-data",
        action="store_true",
        help="rebuild the grouped manifest, including newly audited runtime captures",
    )
    args = parser.parse_args()
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(min(6, max(1, torch.get_num_threads())))

    if args.rebuild_data or not MANIFEST.is_file():
        prepare_dataset()
    if args.prepare_only:
        return
    for directory in (RUN, ARTIFACTS, PERFORMANCE):
        directory.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(MANIFEST)
    train_frame = frame[frame.split == "train"].reset_index(drop=True)
    validation_frame = frame[frame.split == "validation"].reset_index(drop=True)
    test_frame = frame[frame.split == "test"].reset_index(drop=True)
    external_frame = frame[frame.split == "external_holdout_test"].reset_index(
        drop=True
    )
    runtime_frame = frame[frame.split == "runtime_holdout_test"].reset_index(drop=True)
    pd.crosstab(frame.split, [frame.label, frame.source]).to_csv(
        PERFORMANCE / "dataset_composition.csv"
    )

    train_loader = DataLoader(
        ManifestDataset(train_frame, _transforms(True)),
        batch_size=BATCH_SIZE,
        sampler=_sampler(train_frame),
        num_workers=0,
    )
    validation_loader = DataLoader(
        ManifestDataset(validation_frame, _transforms(False)),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )
    test_loader = DataLoader(
        ManifestDataset(test_frame, _transforms(False)),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )
    external_loader = DataLoader(
        ManifestDataset(external_frame, _transforms(False)),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )
    runtime_loader = (
        DataLoader(
            ManifestDataset(runtime_frame, _transforms(False)),
            batch_size=BATCH_SIZE,
            shuffle=False,
            num_workers=0,
        )
        if not runtime_frame.empty
        else None
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(
        "Structural device:",
        torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
    )
    model = _model().to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    history = []
    best_score = -float("inf")
    best_path = RUN / "best_model.pt"
    global_epoch = 0
    for stage, epochs, learning_rate in (
        ("head", HEAD_EPOCHS, 2e-3),
        ("finetune", FINETUNE_EPOCHS, 2e-4),
    ):
        _set_stage(model, stage)
        optimizer = torch.optim.AdamW(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            lr=learning_rate,
            weight_decay=1e-4,
        )
        for _ in range(epochs):
            global_epoch += 1
            model.train()
            running_loss, seen = 0.0, 0
            for images, labels, _ in train_loader:
                optimizer.zero_grad(set_to_none=True)
                logits = model(images.to(device))
                loss = criterion(logits, labels.to(device))
                loss.backward()
                optimizer.step()
                running_loss += float(loss.item()) * len(labels)
                seen += len(labels)
            validation_logits, validation_labels, _ = _predict(
                model, validation_loader, device
            )
            validation_probabilities = _probabilities(validation_logits, 1.0)
            metrics = _class_metrics(validation_labels, validation_probabilities)
            qrdn_mask = validation_frame.source.to_numpy() == "QR-DN1.0"
            qrdn_fpr = float(
                ((1 - validation_probabilities[qrdn_mask, 0]) >= 0.5).mean()
            )
            selection_score = metrics["macro_f1"] - max(0, qrdn_fpr - 0.05) * 2
            row = {
                "epoch": global_epoch,
                "stage": stage,
                "train_loss": running_loss / seen,
                "validation_macro_f1": metrics["macro_f1"],
                "validation_qrdn_clean_fpr": qrdn_fpr,
                "selection_score": selection_score,
            }
            history.append(row)
            print(json.dumps(row))
            if selection_score > best_score:
                best_score = selection_score
                torch.save(model.state_dict(), best_path)

    model.load_state_dict(torch.load(best_path, map_location=device, weights_only=True))
    validation_logits, validation_labels, _ = _predict(model, validation_loader, device)
    temperature = _fit_temperature(validation_logits, validation_labels)
    test_logits, test_labels, _ = _predict(model, test_loader, device)
    external_logits, external_labels, _ = _predict(model, external_loader, device)
    runtime_logits = (
        _predict(model, runtime_loader, device)[0]
        if runtime_loader is not None
        else np.empty((0, len(CLASS_NAMES)), dtype=np.float32)
    )
    test_probabilities = _probabilities(test_logits, temperature)
    external_probabilities = _probabilities(external_logits, temperature)
    runtime_probabilities = (
        _probabilities(runtime_logits, temperature)
        if len(runtime_logits)
        else runtime_logits
    )
    test_metrics = _class_metrics(test_labels, test_probabilities)
    external_metrics = _clean_metrics(external_frame, external_probabilities)

    gate_failures = []
    if test_metrics["macro_f1"] < 0.85:
        gate_failures.append(
            f"synthetic grouped macro-F1 {test_metrics['macro_f1']:.4f} < 0.8500"
        )
    if test_metrics["per_class"]["adversarial"]["recall"] < 0.75:
        gate_failures.append(
            f"adversarial recall {test_metrics['per_class']['adversarial']['recall']:.4f} < 0.7500"
        )
    if test_metrics["per_class"]["tampered"]["recall"] < 0.90:
        gate_failures.append(
            f"tampered recall {test_metrics['per_class']['tampered']['recall']:.4f} < 0.9000"
        )
    if external_metrics["false_positive_rate_at_0_5"] > 0.05:
        gate_failures.append(
            f"QR-DN clean FPR {external_metrics['false_positive_rate_at_0_5']:.4f} > 0.0500"
        )
    if test_metrics["ece"] > 0.05:
        gate_failures.append(f"synthetic test ECE {test_metrics['ece']:.4f} > 0.0500")

    export = _export(model, temperature)
    sample_images, _, _ = next(iter(test_loader))
    onnx_audit = _onnx_audit(export["path"], model, sample_images[:16], temperature)
    if onnx_audit["max_abs_probability_error"] > 1e-5:
        gate_failures.append(
            f"ONNX parity probability error {onnx_audit['max_abs_probability_error']:.3g} > 1e-5"
        )
    if onnx_audit["latency_p95_ms"] > 100:
        gate_failures.append(
            f"ONNX latency P95 {onnx_audit['latency_p95_ms']:.2f} ms > 100 ms"
        )

    runtime_audit_path = ROOT / "data/runtime_captures/audit.json"
    runtime_audit = (
        json.loads(runtime_audit_path.read_text(encoding="utf-8"))
        if runtime_audit_path.is_file()
        else {"strict_ready": False, "strict_failures": ["runtime audit missing"]}
    )
    deployment_failures = list(gate_failures)
    if not runtime_audit.get("strict_ready"):
        deployment_failures.extend(
            f"exact app-crop gate: {failure}"
            for failure in runtime_audit.get("strict_failures", ["not ready"])
        )
    runtime_metrics = _runtime_metrics(runtime_frame, runtime_probabilities)
    if runtime_audit.get("strict_ready"):
        runtime_gates = {
            "clean_false_positive_rate": (0.05, "max"),
            "adversarial_recall": (0.80, "min"),
            "tampered_recall": (0.85, "min"),
        }
        for metric, (threshold, direction) in runtime_gates.items():
            value = runtime_metrics.get(metric)
            failed = value is None or (
                value > threshold if direction == "max" else value < threshold
            )
            if failed:
                deployment_failures.append(
                    f"exact app-crop {metric}={value}; requires {direction} {threshold:.2f}"
                )

    _save_figures(history, test_labels, test_probabilities, external_probabilities)
    _write_complete_tables(
        test_frame,
        test_probabilities,
        external_frame,
        external_probabilities,
        runtime_frame,
        runtime_probabilities,
    )
    pd.DataFrame(history).to_csv(PERFORMANCE / "training_history.csv", index=False)
    predictions = test_probabilities.argmax(axis=1)
    classification = classification_report(
        test_labels,
        predictions,
        target_names=CLASS_NAMES,
        output_dict=True,
        zero_division=0,
    )
    metrics = {
        "display_name": "Structural Training",
        "version": VERSION,
        "architecture": "ImageNet-pretrained ResNet-18; 3-class fine-tuning",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "split_rows": {
            "train": len(train_frame),
            "validation": len(validation_frame),
            "synthetic_grouped_test": len(test_frame),
            "qrdn_external_holdout_test": len(external_frame),
            "exact_app_runtime_holdout_test": len(runtime_frame),
        },
        "temperature": temperature,
        "synthetic_grouped_test": test_metrics,
        "classification_report": classification,
        "qrdn_external_clean_holdout": external_metrics,
        "exact_app_runtime_holdout": runtime_metrics,
        "onnx": {**onnx_audit, "bytes": export["bytes"], "sha256": export["sha256"]},
        "research_gates_passed": not gate_failures,
        "research_gate_failures": gate_failures,
        "runtime_capture_audit": runtime_audit,
        "deployment_gates_passed": not deployment_failures,
        "deployment_gate_failures": deployment_failures,
    }
    (PERFORMANCE / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    metadata = {
        "display_name": "Structural Training",
        "version": VERSION,
        "architecture": metrics["architecture"],
        "artifact_sha256": export["sha256"],
        "research_gates_passed": not gate_failures,
        "deployment_gates_passed": not deployment_failures,
        "deployment_gate_failures": deployment_failures,
    }
    (ARTIFACTS / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    status = "DEPLOYMENT APPROVED" if not deployment_failures else "CANDIDATE ONLY"
    report = f"""# Structural Training performance

Architecture: ImageNet-pretrained ResNet-18, 3-class fine-tuning
Synthetic grouped test identities: {test_frame.group_id.nunique()}
QR-DN external clean identities: {external_frame.group_id.nunique()}

| Metric | Result |
|---|---:|
| Synthetic grouped accuracy | {test_metrics["accuracy"]:.4f} |
| Synthetic grouped macro-F1 | {test_metrics["macro_f1"]:.4f} |
| Adversarial recall | {test_metrics["per_class"]["adversarial"]["recall"]:.4f} |
| Tampered recall | {test_metrics["per_class"]["tampered"]["recall"]:.4f} |
| QR-DN clean false-positive rate | {external_metrics["false_positive_rate_at_0_5"]:.4f} |
| QR-DN median `p_structural` | {external_metrics["median_p_structural"]:.4f} |
| Exact app-camera test frames | {runtime_metrics["n"]} |
| Exact app-camera clean FPR | {runtime_metrics["clean_false_positive_rate"] if runtime_metrics["clean_false_positive_rate"] is not None else "not evaluated"} |
| Exact app-camera adversarial recall | {runtime_metrics["adversarial_recall"] if runtime_metrics["adversarial_recall"] is not None else "not evaluated"} |
| Exact app-camera tampered recall | {runtime_metrics["tampered_recall"] if runtime_metrics["tampered_recall"] is not None else "not evaluated"} |
| ECE | {test_metrics["ece"]:.4f} |
| ONNX P95 latency | {onnx_audit["latency_p95_ms"]:.2f} ms |

Status: **{status}**
"""
    if deployment_failures:
        report += "\nDeployment gate failures:\n" + "".join(
            f"\n- {failure}" for failure in deployment_failures
        )
        report += "\n"
        (ARTIFACTS / "DEPLOYMENT_REJECTED.json").write_text(
            json.dumps({"failures": deployment_failures}, indent=2), encoding="utf-8"
        )
    (PERFORMANCE / "STRUCTURAL_PERFORMANCE.md").write_text(report, encoding="utf-8")
    with (PERFORMANCE / "metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerow(["synthetic_accuracy", test_metrics["accuracy"]])
        writer.writerow(["synthetic_macro_f1", test_metrics["macro_f1"]])
        writer.writerow(
            ["adversarial_recall", test_metrics["per_class"]["adversarial"]["recall"]]
        )
        writer.writerow(
            ["tampered_recall", test_metrics["per_class"]["tampered"]["recall"]]
        )
        writer.writerow(
            ["qrdn_clean_fpr", external_metrics["false_positive_rate_at_0_5"]]
        )
        writer.writerow(
            ["runtime_clean_fpr", runtime_metrics["clean_false_positive_rate"]]
        )
        writer.writerow(
            ["runtime_adversarial_recall", runtime_metrics["adversarial_recall"]]
        )
        writer.writerow(["runtime_tampered_recall", runtime_metrics["tampered_recall"]])
        writer.writerow(["ece", test_metrics["ece"]])
        writer.writerow(["onnx_latency_p95_ms", onnx_audit["latency_p95_ms"]])
    print(report)
    if deployment_failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
