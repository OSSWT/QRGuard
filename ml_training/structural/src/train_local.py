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

from ml_training.structural.src.evaluate_exported_v3 import (  # noqa: E402
    evaluate_export as evaluate_exported_runtime,
)
from ml_training.structural.src.evaluate_paired_consistency import (  # noqa: E402
    evaluate as evaluate_paired_consistency,
)
from ml_training.structural.src.run_state import (  # noqa: E402
    RUN_MODES,
    build_run_identity,
    validate_run_identity,
    write_run_state,
)
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
CONFIG = ROOT / "ml_training/configs" / f"{VERSION}.json"
if not CONFIG.is_file():
    CONFIG = ROOT / "ml_training/configs/structural.json"
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


def _sampler(
    frame: pd.DataFrame, generator: torch.Generator | None = None
) -> WeightedRandomSampler:
    """Balance classes and Camera/Gallery/other domains without sparse oversampling."""
    weights = np.zeros(len(frame), dtype=np.float64)
    target_domain_shares = {"camera": 0.40, "gallery": 0.30, "other": 0.30}

    def source_domain(source: str) -> str:
        source = str(source)
        if source in {"qrguard_runtime", "qrguard_runtime_v3_camera"}:
            return "camera"
        if source in {
            "qrguard_runtime_v3_gallery",
            "qrguard_prepared_gallery_reference",
        }:
            return "gallery"
        return "other"

    for class_id in (0, 1, 2):
        class_mask = frame.class_id.to_numpy() == class_id
        if not class_mask.any():
            continue
        domains = frame.loc[class_mask, "source"].map(source_domain).to_numpy()
        present_domains = set(domains)
        normalizer = sum(target_domain_shares[domain] for domain in present_domains)
        for domain in present_domains:
            mask = class_mask.copy()
            mask[class_mask] = domains == domain
            domain_share = target_domain_shares[domain] / normalizer
            # Rows share one domain allocation directly. A single pilot Gallery
            # crop cannot receive the same mass as every prepared Gallery
            # reference combined.
            weights[mask] = (1 / 3) * domain_share / int(mask.sum())
    if np.any(weights <= 0):
        missing = frame.loc[weights <= 0, ["label", "source"]].drop_duplicates()
        raise ValueError(f"sampler has uncovered rows:\n{missing}")
    return WeightedRandomSampler(
        torch.as_tensor(weights, dtype=torch.double),
        num_samples=len(frame),
        replacement=True,
        generator=generator or torch.Generator().manual_seed(SEED),
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


def _deployment_validation_metrics(
    frame: pd.DataFrame, probabilities: np.ndarray
) -> dict:
    """Score non-test Camera/Gallery evidence used for checkpoint selection."""
    sources = frame.source.astype(str).to_numpy()
    camera_mask = np.isin(sources, ["qrguard_runtime", "qrguard_runtime_v3_camera"])
    gallery_mask = np.isin(
        sources,
        [
            "qrguard_runtime_v3_gallery",
            "qrguard_prepared_gallery_reference",
        ],
    )
    deployment_mask = camera_mask | gallery_mask
    if not deployment_mask.any():
        return {
            "rows": 0,
            "macro_f1": None,
            "paired_groups": 0,
            "paired_verdict_agreement": None,
        }
    metrics = _class_metrics(
        frame.loc[deployment_mask, "class_id"].to_numpy(dtype=int),
        probabilities[deployment_mask],
    )
    group_ids = frame.group_id.astype(str).to_numpy()
    paired_agreements = []
    for group_id in sorted(set(group_ids[deployment_mask])):
        group_mask = group_ids == group_id
        camera_indices = np.flatnonzero(group_mask & camera_mask)
        gallery_indices = np.flatnonzero(group_mask & gallery_mask)
        if not len(camera_indices) or not len(gallery_indices):
            continue
        camera_prediction = int(probabilities[camera_indices].mean(axis=0).argmax())
        gallery_prediction = int(probabilities[gallery_indices].mean(axis=0).argmax())
        paired_agreements.append((camera_prediction != 0) == (gallery_prediction != 0))
    metrics.update(
        {
            "rows": int(deployment_mask.sum()),
            "paired_groups": len(paired_agreements),
            "paired_verdict_agreement": (
                float(np.mean(paired_agreements)) if paired_agreements else None
            ),
        }
    )
    return metrics


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


def _quality_slice_row(
    scope: str,
    condition: str,
    frame: pd.DataFrame,
    probabilities: np.ndarray,
) -> dict:
    """Report quality slices without treating a missing class as zero recall."""
    labels = frame.class_id.to_numpy(dtype=int)
    predictions = probabilities.argmax(axis=1)
    row = {
        "scope": scope,
        "status": "evaluated",
        "quality_condition": condition,
        "rows": int(len(frame)),
        "groups": int(frame.group_id.nunique()),
        "accuracy": float((predictions == labels).mean()),
        "clean_rows": int((labels == 0).sum()),
        "adversarial_rows": int((labels == 1).sum()),
        "tampered_rows": int((labels == 2).sum()),
        "clean_false_positive_rate": None,
        "adversarial_recall": None,
        "tampered_recall": None,
        "evidence_note": (
            "controlled simulation; not a substitute for exact app-camera evidence"
            if scope == "controlled_synthetic_grouped_test"
            else (
                "exact app-crop model-only slice; severe inputs are audited "
                "before inference"
            )
        ),
    }
    for class_id, metric in (
        (0, "clean_false_positive_rate"),
        (1, "adversarial_recall"),
        (2, "tampered_recall"),
    ):
        mask = labels == class_id
        if not mask.any():
            continue
        row[metric] = float(
            (predictions[mask] != 0).mean()
            if class_id == 0
            else (predictions[mask] == class_id).mean()
        )
    return row


def _paired_consistency(
    frame: pd.DataFrame, probabilities: np.ndarray
) -> dict[str, object] | None:
    predictions_path = PERFORMANCE / "runtime_predictions.csv"
    if frame.empty:
        pd.DataFrame().to_csv(predictions_path, index=False)
        pd.DataFrame([{"status": "not_evaluated", "paired_groups": 0}]).to_csv(
            PERFORMANCE / "gallery_camera_consistency.csv", index=False
        )
        return None

    predictions = frame.copy().reset_index(drop=True)
    predictions["p_clean"] = probabilities[:, 0]
    predictions["p_adversarial"] = probabilities[:, 1]
    predictions["p_tampered"] = probabilities[:, 2]
    predictions["predicted_type"] = [
        CLASS_NAMES[index] for index in probabilities.argmax(axis=1)
    ]
    predictions.to_csv(predictions_path, index=False)
    required = {"paired_group", "image_source"}
    if not required <= set(predictions.columns):
        pd.DataFrame(
            [{"status": "not_evaluated", "reason": "v3 pairing metadata missing"}]
        ).to_csv(PERFORMANCE / "gallery_camera_consistency.csv", index=False)
        return None
    try:
        metrics, pairs = evaluate_paired_consistency(predictions)
    except ValueError as error:
        pd.DataFrame([{"status": "not_evaluated", "reason": str(error)}]).to_csv(
            PERFORMANCE / "gallery_camera_consistency.csv", index=False
        )
        return None

    pairs.to_csv(PERFORMANCE / "gallery_camera_pairs.csv", index=False)
    (PERFORMANCE / "gallery_camera_consistency.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    rows = [
        {"slice": "overall", **metrics["overall"]},
        *(
            {"slice": f"class/{label}", **values}
            for label, values in metrics["per_class"].items()
        ),
    ]
    pd.DataFrame(rows).to_csv(
        PERFORMANCE / "gallery_camera_consistency.csv", index=False
    )
    return metrics


def _write_complete_tables(
    test_frame: pd.DataFrame,
    test_probabilities: np.ndarray,
    external_frame: pd.DataFrame,
    external_probabilities: np.ndarray,
    runtime_frame: pd.DataFrame,
    runtime_probabilities: np.ndarray,
) -> list[dict]:
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
        if "image_source" in runtime_frame:
            for image_source in sorted(runtime_frame.image_source.unique()):
                mask = (runtime_frame.image_source == image_source).to_numpy()
                source_rows.append(
                    _slice_row(
                        f"runtime_holdout/{image_source}",
                        runtime_frame[mask],
                        runtime_probabilities[mask],
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

    quality_rows = []
    if "quality_condition" in test_frame:
        for condition in sorted(test_frame.quality_condition.dropna().unique()):
            mask = (test_frame.quality_condition == condition).to_numpy()
            quality_rows.append(
                _quality_slice_row(
                    "controlled_synthetic_grouped_test",
                    str(condition),
                    test_frame[mask],
                    test_probabilities[mask],
                )
            )
    if not runtime_frame.empty and "quality_condition" in runtime_frame:
        for condition in sorted(runtime_frame.quality_condition.unique()):
            mask = (runtime_frame.quality_condition == condition).to_numpy()
            quality_rows.append(
                _quality_slice_row(
                    "exact_app_runtime_model_only",
                    str(condition),
                    runtime_frame[mask],
                    runtime_probabilities[mask],
                )
            )
    else:
        quality_rows.append(
            {
                "scope": "exact_app_runtime_model_only",
                "status": "not_evaluated",
                "quality_condition": "not_evaluated",
                "rows": 0,
                "groups": 0,
                "evidence_note": "exact app-crop quality slices missing",
            }
        )
    pd.DataFrame(quality_rows).to_csv(
        PERFORMANCE / "per_quality_condition_results.csv", index=False
    )

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
    return quality_rows


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


def _rng_state() -> dict:
    state = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["cuda"] = torch.cuda.get_rng_state_all()
    return state


def _restore_rng_state(state: dict) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"])
    if torch.cuda.is_available() and "cuda" in state:
        torch.cuda.set_rng_state_all(state["cuda"])


def _atomic_torch_save(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def _checkpoint_payload(
    *,
    identity: dict[str, str],
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    history: list[dict],
    best_score: float,
    global_epoch: int,
    stage_index: int,
    stage: str,
    stage_epoch: int,
    sampler_generator: torch.Generator,
) -> dict:
    return {
        "schema_version": 1,
        "identity": identity,
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "history": history,
        "best_score": best_score,
        "global_epoch": global_epoch,
        "stage_index": stage_index,
        "stage": stage,
        "stage_epoch": stage_epoch,
        "sampler_generator_state": sampler_generator.get_state(),
        "rng_state": _rng_state(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=RUN_MODES, default="fresh")
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=RUN / "checkpoints",
        help="persistent checkpoint directory; use Google Drive on Colab",
    )
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument(
        "--rebuild-data",
        action="store_true",
        help="rebuild the grouped manifest, including newly audited runtime captures",
    )
    args = parser.parse_args()
    checkpoint_dir = args.checkpoint_dir.expanduser().resolve()
    checkpoint_last = checkpoint_dir / "last_checkpoint.pt"
    checkpoint_best = checkpoint_dir / "best_model.pt"
    run_state_path = checkpoint_dir / "run_state.json"

    if args.mode == "report_only":
        metrics_path = PERFORMANCE / "metrics.json"
        report_path = PERFORMANCE / "STRUCTURAL_PERFORMANCE.md"
        if not metrics_path.is_file() or not report_path.is_file():
            raise FileNotFoundError(
                f"report_only requires a restored performance bundle: {PERFORMANCE}"
            )
        print(report_path.read_text(encoding="utf-8"))
        print(
            json.dumps(json.loads(metrics_path.read_text(encoding="utf-8")), indent=2)
        )
        return

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
    identity = build_run_identity(VERSION, CONFIG, MANIFEST)
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

    sampler_generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(
        ManifestDataset(train_frame, _transforms(True)),
        batch_size=BATCH_SIZE,
        sampler=_sampler(train_frame, sampler_generator),
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
    resume_checkpoint = None
    if args.mode == "fresh":
        existing = [
            path
            for path in (checkpoint_last, checkpoint_best, run_state_path)
            if path.exists()
        ]
        if existing:
            raise FileExistsError(
                "fresh mode will not overwrite an existing run. Choose a new "
                "checkpoint directory or use resume: " + ", ".join(map(str, existing))
            )
    elif args.mode == "resume":
        if not checkpoint_last.is_file():
            raise FileNotFoundError(
                f"resume requires the last checkpoint: {checkpoint_last}"
            )
        resume_checkpoint = torch.load(
            checkpoint_last, map_location=device, weights_only=False
        )
        validate_run_identity(identity, resume_checkpoint.get("identity", {}))
        model.load_state_dict(resume_checkpoint["model_state"])
        history = list(resume_checkpoint["history"])
        best_score = float(resume_checkpoint["best_score"])
        global_epoch = int(resume_checkpoint["global_epoch"])
        sampler_generator.set_state(resume_checkpoint["sampler_generator_state"])
        _restore_rng_state(resume_checkpoint["rng_state"])
        print(f"Resuming {VERSION} after epoch {global_epoch}")
    elif args.mode == "evaluate_only":
        if not checkpoint_best.is_file() or not run_state_path.is_file():
            raise FileNotFoundError(
                "evaluate_only requires best_model.pt and run_state.json in "
                f"{checkpoint_dir}"
            )
        recorded = json.loads(run_state_path.read_text(encoding="utf-8"))
        validate_run_identity(identity, recorded.get("identity", {}))
        model.load_state_dict(
            torch.load(checkpoint_best, map_location=device, weights_only=True)
        )
        history = list(recorded.get("history", []))
        best_score = float(recorded.get("best_score", -float("inf")))
        global_epoch = int(recorded.get("last_completed_epoch", 0))
        print(f"Evaluating saved {VERSION} checkpoint without training")

    stage_plan = (
        ("head", HEAD_EPOCHS, 2e-3),
        ("finetune", FINETUNE_EPOCHS, 2e-4),
    )
    if args.mode in {"fresh", "resume"}:
        for stage_index, (stage, epochs, learning_rate) in enumerate(stage_plan):
            start_epoch = 0
            restore_optimizer = False
            if resume_checkpoint is not None:
                completed_stage = int(resume_checkpoint["stage_index"])
                if stage_index < completed_stage:
                    continue
                if stage_index == completed_stage:
                    start_epoch = int(resume_checkpoint["stage_epoch"])
                    if start_epoch >= epochs:
                        continue
                    restore_optimizer = True

            _set_stage(model, stage)
            optimizer = torch.optim.AdamW(
                [
                    parameter
                    for parameter in model.parameters()
                    if parameter.requires_grad
                ],
                lr=learning_rate,
                weight_decay=1e-4,
            )
            if restore_optimizer:
                optimizer.load_state_dict(resume_checkpoint["optimizer_state"])

            for stage_epoch in range(start_epoch, epochs):
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
                deployment_validation = _deployment_validation_metrics(
                    validation_frame, validation_probabilities
                )
                qrdn_mask = validation_frame.source.to_numpy() == "QR-DN1.0"
                qrdn_fpr = float(
                    ((1 - validation_probabilities[qrdn_mask, 0]) >= 0.5).mean()
                )
                deployment_macro_f1 = (
                    deployment_validation["macro_f1"]
                    if deployment_validation["macro_f1"] is not None
                    else metrics["macro_f1"]
                )
                paired_agreement = (
                    deployment_validation["paired_verdict_agreement"]
                    if deployment_validation["paired_verdict_agreement"] is not None
                    else metrics["macro_f1"]
                )
                selection_score = (
                    0.25 * metrics["macro_f1"]
                    + 0.50 * deployment_macro_f1
                    + 0.25 * paired_agreement
                    - max(0, qrdn_fpr - 0.05) * 2
                )
                row = {
                    "epoch": global_epoch,
                    "stage": stage,
                    "stage_epoch": stage_epoch + 1,
                    "train_loss": running_loss / seen,
                    "validation_macro_f1": metrics["macro_f1"],
                    "validation_deployment_macro_f1": deployment_macro_f1,
                    "validation_paired_groups": deployment_validation["paired_groups"],
                    "validation_paired_verdict_agreement": paired_agreement,
                    "validation_qrdn_clean_fpr": qrdn_fpr,
                    "selection_score": selection_score,
                }
                history.append(row)
                print(json.dumps(row))
                if selection_score > best_score:
                    best_score = selection_score
                    _atomic_torch_save(model.state_dict(), best_path)
                    _atomic_torch_save(model.state_dict(), checkpoint_best)

                payload = _checkpoint_payload(
                    identity=identity,
                    model=model,
                    optimizer=optimizer,
                    history=history,
                    best_score=best_score,
                    global_epoch=global_epoch,
                    stage_index=stage_index,
                    stage=stage,
                    stage_epoch=stage_epoch + 1,
                    sampler_generator=sampler_generator,
                )
                _atomic_torch_save(payload, checkpoint_last)
                write_run_state(
                    run_state_path,
                    {
                        "schema_version": 1,
                        "status": "training",
                        "mode": args.mode,
                        "identity": identity,
                        "last_completed_epoch": global_epoch,
                        "stage": stage,
                        "stage_epoch": stage_epoch + 1,
                        "best_score": best_score,
                        "history": history,
                    },
                )

    model.load_state_dict(
        torch.load(checkpoint_best, map_location=device, weights_only=True)
    )
    validation_logits, validation_labels, _ = _predict(model, validation_loader, device)
    validation_selection_metrics = _deployment_validation_metrics(
        validation_frame, _probabilities(validation_logits, 1.0)
    )
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

    exported_runtime_metrics = None
    if VERSION.startswith("structural-2026.03"):
        capture_root = ROOT / "data/runtime_captures"
        capture_manifest = capture_root / "manifest_v3.csv"
        if capture_manifest.is_file():
            try:
                exported_runtime_metrics = evaluate_exported_runtime(
                    ARTIFACTS,
                    capture_manifest,
                    capture_root,
                    PERFORMANCE,
                )
            except (KeyError, OSError, RuntimeError, ValueError) as error:
                gate_failures.append(
                    f"exported source-neutral runtime evaluation failed: {error}"
                )

    runtime_audit_name = (
        "audit_v3.json" if VERSION.startswith("structural-2026.03") else "audit.json"
    )
    runtime_audit_path = ROOT / "data/runtime_captures" / runtime_audit_name
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
    if not runtime_frame.empty and "image_source" in runtime_frame:
        camera_mask = (runtime_frame.image_source == "camera").to_numpy()
        gallery_mask = (runtime_frame.image_source == "gallery").to_numpy()
    else:
        camera_mask = np.ones(len(runtime_frame), dtype=bool)
        gallery_mask = np.zeros(len(runtime_frame), dtype=bool)
    runtime_metrics = _runtime_metrics(
        runtime_frame[camera_mask].reset_index(drop=True),
        runtime_probabilities[camera_mask],
    )
    gallery_metrics = _runtime_metrics(
        runtime_frame[gallery_mask].reset_index(drop=True),
        runtime_probabilities[gallery_mask],
    )
    paired_metrics = _paired_consistency(runtime_frame, runtime_probabilities)
    if runtime_audit.get("strict_ready"):
        exported_deployment = (
            exported_runtime_metrics.get("deployment_holdout", {})
            if exported_runtime_metrics
            else {}
        )
        contract_camera = (
            exported_deployment.get("per_source", {}).get("camera", {})
            if exported_runtime_metrics
            else runtime_metrics
        )
        runtime_gates = {
            "clean_false_positive_rate": (0.05, "max"),
            "adversarial_recall": (0.80, "min"),
            "tampered_recall": (0.85, "min"),
        }
        for metric, (threshold, direction) in runtime_gates.items():
            value = contract_camera.get(metric)
            failed = value is None or (
                value > threshold if direction == "max" else value < threshold
            )
            if failed:
                deployment_failures.append(
                    f"exact app-crop {metric}={value}; requires {direction} {threshold:.2f}"
                )
        exported_pair = (
            exported_deployment.get("paired_gallery_camera")
            if exported_runtime_metrics
            else None
        )
        contract_pair = exported_pair or paired_metrics
        paired_agreement = (
            contract_pair.get("overall", {}).get("verdict_agreement")
            if contract_pair
            else None
        )
        if paired_agreement is None or paired_agreement < 0.95:
            deployment_failures.append(
                "paired Gallery/Camera verdict agreement "
                f"{paired_agreement}; require min 0.95"
            )

    _save_figures(history, test_labels, test_probabilities, external_probabilities)
    quality_slice_rows = _write_complete_tables(
        test_frame,
        test_probabilities,
        external_frame,
        external_probabilities,
        runtime_frame,
        runtime_probabilities,
    )
    controlled_quality_rows = [
        row
        for row in quality_slice_rows
        if row.get("scope") == "controlled_synthetic_grouped_test"
        and row.get("status") == "evaluated"
    ]
    controlled_clean_rows = [
        row
        for row in controlled_quality_rows
        if row.get("clean_false_positive_rate") is not None
    ]
    worst_controlled_clean = (
        max(controlled_clean_rows, key=lambda row: row["clean_false_positive_rate"])
        if controlled_clean_rows
        else None
    )
    worst_controlled_clean_display = (
        f"{worst_controlled_clean['clean_false_positive_rate']:.4f} "
        f"({worst_controlled_clean['quality_condition']})"
        if worst_controlled_clean
        else "not evaluated"
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
        "run_identity": identity,
        "execution_mode": args.mode,
        "architecture": "ImageNet-pretrained ResNet-18; 3-class fine-tuning",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "split_rows": {
            "train": len(train_frame),
            "validation": len(validation_frame),
            "synthetic_grouped_test": len(test_frame),
            "qrdn_external_holdout_test": len(external_frame),
            "exact_app_runtime_holdout_test": len(runtime_frame),
            "exact_app_camera_holdout_test": int(camera_mask.sum()),
            "exact_app_gallery_holdout_test": int(gallery_mask.sum()),
        },
        "temperature": temperature,
        "validation_selection_contract": validation_selection_metrics,
        "synthetic_grouped_test": test_metrics,
        "classification_report": classification,
        "qrdn_external_clean_holdout": external_metrics,
        "exact_app_runtime_holdout": runtime_metrics,
        "exact_app_gallery_holdout": gallery_metrics,
        "paired_gallery_camera_consistency": paired_metrics,
        "quality_condition_slices": quality_slice_rows,
        "controlled_quality_summary": {
            "conditions_evaluated": len(controlled_quality_rows),
            "evidence_scope": "controlled simulation; not deployment evidence",
            "worst_clean_condition": (
                worst_controlled_clean["quality_condition"]
                if worst_controlled_clean
                else None
            ),
            "worst_clean_false_positive_rate": (
                worst_controlled_clean["clean_false_positive_rate"]
                if worst_controlled_clean
                else None
            ),
        },
        "exported_source_neutral_runtime": exported_runtime_metrics,
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
    exported_camera_metrics = (
        exported_runtime_metrics.get("deployment_holdout", {})
        .get("per_source", {})
        .get("camera", {})
        if exported_runtime_metrics
        else {}
    )
    reported_pair = (
        exported_runtime_metrics.get("deployment_holdout", {}).get(
            "paired_gallery_camera"
        )
        if exported_runtime_metrics
        else None
    ) or paired_metrics
    paired_verdict_agreement = (
        reported_pair.get("overall", {}).get("verdict_agreement")
        if reported_pair
        else "not evaluated"
    )
    exported_abstention_rate = (
        exported_runtime_metrics.get("deployment_holdout", {})
        .get("overall", {})
        .get("abstention_rate")
        if exported_runtime_metrics
        else "not evaluated"
    )
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
| Controlled nuisance conditions evaluated | {len(controlled_quality_rows)} |
| Worst controlled clean FPR | {worst_controlled_clean_display} |
| Exact app-camera test frames | {runtime_metrics["n"]} |
| Exact app-camera clean FPR | {runtime_metrics["clean_false_positive_rate"] if runtime_metrics["clean_false_positive_rate"] is not None else "not evaluated"} |
| Exact app-camera adversarial recall | {runtime_metrics["adversarial_recall"] if runtime_metrics["adversarial_recall"] is not None else "not evaluated"} |
| Exact app-camera tampered recall | {runtime_metrics["tampered_recall"] if runtime_metrics["tampered_recall"] is not None else "not evaluated"} |
| Exact app-gallery clean FPR | {gallery_metrics["clean_false_positive_rate"] if gallery_metrics["clean_false_positive_rate"] is not None else "not evaluated"} |
| Exported source-neutral camera clean FPR | {exported_camera_metrics.get("clean_false_positive_rate", "not evaluated")} |
| Exported quality abstention rate | {exported_abstention_rate} |
| Paired Gallery/Camera verdict agreement | {paired_verdict_agreement} |
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
        writer.writerow(
            ["paired_gallery_camera_verdict_agreement", paired_verdict_agreement]
        )
        writer.writerow(
            [
                "exported_camera_clean_fpr",
                exported_camera_metrics.get("clean_false_positive_rate"),
            ]
        )
        writer.writerow(["quality_abstention_rate", exported_abstention_rate])
        writer.writerow(["ece", test_metrics["ece"]])
        writer.writerow(["onnx_latency_p95_ms", onnx_audit["latency_p95_ms"]])
    write_run_state(
        run_state_path,
        {
            "schema_version": 1,
            "status": "evaluated",
            "mode": args.mode,
            "identity": identity,
            "last_completed_epoch": global_epoch,
            "best_score": best_score,
            "history": history,
            "research_gates_passed": not gate_failures,
            "deployment_gates_passed": not deployment_failures,
        },
    )
    print(report)
    if deployment_failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
