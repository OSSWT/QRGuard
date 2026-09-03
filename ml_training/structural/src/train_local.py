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
from ml_training.structural.src.exposure_invariance import (  # noqa: E402
    ExposureInvarianceConfig,
    FixedExposureTransform,
    RandomExposureTransform,
    exposure_consistency_metrics,
    symmetric_kl_loss,
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
RUN_CONFIG = json.loads(CONFIG.read_text(encoding="utf-8"))
TRAINING_CONFIG = RUN_CONFIG.get("training", {})
EXPOSURE_CONFIG = ExposureInvarianceConfig.from_mapping(
    TRAINING_CONFIG.get("exposure_invariance")
)
BATCH_SIZE = int(TRAINING_CONFIG.get("batch_size", 32))
HEAD_EPOCHS = int(TRAINING_CONFIG.get("head_epochs", 2))
FINETUNE_EPOCHS = int(TRAINING_CONFIG.get("finetune_epochs", 5))
HEAD_LEARNING_RATE = float(TRAINING_CONFIG.get("head_learning_rate", 2e-3))
FINETUNE_LEARNING_RATE = float(
    TRAINING_CONFIG.get("finetune_learning_rate", 2e-4)
)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
TOPOLOGY_COUNTERFACTUAL_SOURCE = "procedural_qrguard_topology_counterfactual"
CONSUMED_BLIND_CLEAN_SOURCE = "qrguard_consumed_blind_clean_2026_09_camera"
CONSUMED_BLIND_ATTACK_SOURCE = "qrguard_consumed_blind_verified_attack_camera"


def _paired_partner_indices(frame: pd.DataFrame) -> list[int]:
    """Choose same-class partners, connecting every topology view in one cycle."""

    partner_indices = list(range(len(frame)))
    if frame.empty:
        return partner_indices
    groups: dict[tuple[str, int], list[int]] = {}
    for index, row in frame.iterrows():
        paired_group = row.get("paired_group", row.get("group_id", index))
        if pd.isna(paired_group):
            paired_group = row.get("group_id", index)
        key = (str(paired_group), int(row.class_id))
        groups.setdefault(key, []).append(index)
    for indices in groups.values():
        is_topology_group = all(
            str(frame.iloc[index].get("source", ""))
            == TOPOLOGY_COUNTERFACTUAL_SOURCE
            for index in indices
        )
        has_topology_columns = {"mask_pattern", "quality_condition"}.issubset(
            frame.columns
        )
        if not is_topology_group or not has_topology_columns:
            for position, index in enumerate(indices):
                partner_indices[index] = indices[(position + 1) % len(indices)]
            continue

        # The old ``mask + 4`` policy formed four disconnected mask pairs. A
        # model could therefore satisfy every pairwise loss while retaining a
        # large probability offset between pairs. Ordering all mask/condition
        # views and joining consecutive rows creates one connected cycle for
        # the complete standards-valid QR identity.
        ordered = sorted(
            indices,
            key=lambda candidate: (
                int(frame.iloc[candidate].mask_pattern),
                str(frame.iloc[candidate].quality_condition)
                != "normal",
                str(frame.iloc[candidate].quality_condition),
            ),
        )
        for position, index in enumerate(ordered):
            partner_indices[index] = ordered[(position + 1) % len(ordered)]
    return partner_indices


class ManifestDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, transform, paired_transform=None) -> None:
        self.frame = frame.reset_index(drop=True)
        self.transform = transform
        self.paired_transform = paired_transform
        self.partner_indices = (
            _paired_partner_indices(self.frame)
            if paired_transform is not None
            else list(range(len(self.frame)))
        )

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int):
        row = self.frame.iloc[index]
        with Image.open(ROOT / row.path) as image:
            tensor = self.transform(image.convert("RGB"))
        if self.paired_transform is not None:
            partner = self.frame.iloc[self.partner_indices[index]]
            if int(partner.class_id) != int(row.class_id):
                raise AssertionError("exposure partner crossed a Structural class")
            with Image.open(ROOT / partner.path) as image:
                paired_tensor = self.paired_transform(image.convert("RGB"))
            return tensor, paired_tensor, int(row.class_id), index
        return tensor, int(row.class_id), index


def _transforms(training: bool, *, exposure_variant: bool = False):
    steps = [transforms.Resize((224, 224), antialias=True)]
    if training:
        if exposure_variant:
            steps.append(RandomExposureTransform(EXPOSURE_CONFIG))
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


def _exposure_eval_transform(ev: float):
    return transforms.Compose(
        [
            transforms.Resize((224, 224), antialias=True),
            FixedExposureTransform(ev),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


def _source_family(source: str, *, separate_topology: bool = False) -> str:
    source = str(source)
    if source in {
        "qrguard_runtime",
        "qrguard_runtime_v3_camera",
        "qrguard_coverage_2026_09_camera",
        "qrguard_physical_attack_2026_09_camera",
        "qrguard_acquisition_quality_2026_09_camera",
        CONSUMED_BLIND_CLEAN_SOURCE,
        CONSUMED_BLIND_ATTACK_SOURCE,
    }:
        return "camera"
    if source in {
        "qrguard_runtime_v3_gallery",
        "qrguard_prepared_gallery_reference",
    }:
        return "gallery"
    if source == TOPOLOGY_COUNTERFACTUAL_SOURCE and separate_topology:
        return "topology_counterfactual"
    if source in {
        "procedural_qrguard",
        TOPOLOGY_COUNTERFACTUAL_SOURCE,
    }:
        return "procedural"
    return "public_clean"


def _sampling_weights(
    frame: pd.DataFrame, sampling_config: dict | None = None
) -> np.ndarray:
    """Return class-balanced row weights without allowing source shortcuts.

    The legacy domain policy pooled public clean datasets and paired procedural
    clean QR codes into one ``other`` bucket. Since FGSM/PGD rows exist only for
    the procedural source, that made a procedural adversarial crop about five
    times more likely to be sampled than its clean counterpart. A configured
    source-family policy gives each Structural class an explicit allocation for
    procedural, Camera, Gallery, and public-clean evidence.
    """
    weights = np.zeros(len(frame), dtype=np.float64)
    configured = (sampling_config or {}).get("source_family_draw_fractions")
    if configured:
        separate_topology = any(
            isinstance(shares, dict) and "topology_counterfactual" in shares
            for shares in configured.values()
        )
        families = frame.source.map(
            lambda source: _source_family(
                source, separate_topology=separate_topology
            )
        ).to_numpy()
        sources = frame.source.astype(str).to_numpy()
        configured_multipliers = (sampling_config or {}).get(
            "source_multipliers", {}
        )
        if not isinstance(configured_multipliers, dict):
            raise ValueError("source_multipliers must be an object")
        row_multipliers = np.array(
            [float(configured_multipliers.get(source, 1.0)) for source in sources],
            dtype=np.float64,
        )
        if np.any(~np.isfinite(row_multipliers)) or np.any(row_multipliers <= 0):
            raise ValueError("source_multipliers must be finite and positive")
        for class_id, label in enumerate(CLASS_NAMES):
            class_mask = frame.class_id.to_numpy() == class_id
            if not class_mask.any():
                continue
            shares = configured.get(label)
            if not isinstance(shares, dict) or not shares:
                raise ValueError(f"missing source-family sampling policy for {label}")
            present = set(families[class_mask])
            missing = sorted(family for family in present if family not in shares)
            if missing:
                raise ValueError(
                    f"source-family sampling policy for {label} omits {missing}"
                )
            normalizer = sum(float(shares[family]) for family in present)
            if normalizer <= 0:
                raise ValueError(f"invalid source-family sampling mass for {label}")
            for family in present:
                mask = class_mask & (families == family)
                family_share = float(shares[family]) / normalizer
                if family_share <= 0:
                    raise ValueError(
                        f"source-family sampling mass must be positive: "
                        f"{label}/{family}"
                    )
                multiplier_mass = float(row_multipliers[mask].sum())
                weights[mask] = (
                    (1 / len(CLASS_NAMES))
                    * family_share
                    * row_multipliers[mask]
                    / multiplier_mass
                )
        if np.any(weights <= 0):
            missing = frame.loc[weights <= 0, ["label", "source"]].drop_duplicates()
            raise ValueError(f"sampler has uncovered rows:\n{missing}")
        return weights

    # Backward-compatible policy for frozen configurations that predate the
    # explicit source-family contract.
    target_domain_shares = {"camera": 0.40, "gallery": 0.30, "other": 0.30}

    def source_domain(source: str) -> str:
        source = str(source)
        if source in {
            "qrguard_runtime",
            "qrguard_runtime_v3_camera",
            "qrguard_coverage_2026_09_camera",
        }:
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
    return weights


def _sampler(
    frame: pd.DataFrame,
    generator: torch.Generator | None = None,
    sampling_config: dict | None = None,
) -> WeightedRandomSampler:
    weights = _sampling_weights(frame, sampling_config)
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


def _evaluate_exposure_invariance(
    model: nn.Module,
    frame: pd.DataFrame,
    device: torch.device,
    *,
    temperature: float,
) -> dict:
    if frame.empty or not EXPOSURE_CONFIG.enabled:
        return {
            "status": "not_evaluated",
            "views": 0,
            "rows": int(len(frame)),
        }
    views = []
    labels = None
    for ev in EXPOSURE_CONFIG.evaluation_ev:
        loader = DataLoader(
            ManifestDataset(frame, _exposure_eval_transform(ev)),
            batch_size=BATCH_SIZE,
            shuffle=False,
            num_workers=0,
        )
        logits, view_labels, _ = _predict(model, loader, device)
        if labels is None:
            labels = view_labels
        elif not np.array_equal(labels, view_labels):
            raise AssertionError("exposure evaluation changed row order")
        views.append(_probabilities(logits, temperature))
    metrics = exposure_consistency_metrics(views, labels)
    return {
        "status": "evaluated",
        "evaluation_ev": list(EXPOSURE_CONFIG.evaluation_ev),
        **metrics,
    }


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


def _fit_temperature(
    logits: np.ndarray,
    labels: np.ndarray,
    sample_weights: np.ndarray | None = None,
) -> float:
    if sample_weights is None:
        normalized_weights = np.full(len(labels), 1 / len(labels), dtype=np.float64)
    else:
        normalized_weights = np.asarray(sample_weights, dtype=np.float64)
        if normalized_weights.shape != labels.shape:
            raise ValueError("temperature sample weights must match labels")
        if np.any(normalized_weights <= 0) or normalized_weights.sum() <= 0:
            raise ValueError("temperature sample weights must be positive")
        normalized_weights = normalized_weights / normalized_weights.sum()

    def objective(log_temperature: float) -> float:
        probabilities = _probabilities(logits, float(np.exp(log_temperature)))
        selected = np.clip(probabilities[np.arange(len(labels)), labels], 1e-12, 1)
        return float(np.sum(normalized_weights * -np.log(selected)))

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
    image_sources = (
        frame.image_source.astype(str).to_numpy()
        if "image_source" in frame
        else np.full(len(frame), "not_recorded")
    )
    camera_mask = np.isin(
        sources,
        [
            "qrguard_runtime",
            "qrguard_runtime_v3_camera",
            "qrguard_coverage_2026_09_camera",
        ],
    ) | (image_sources == "camera")
    gallery_mask = np.isin(
        sources,
        [
            "qrguard_runtime_v3_gallery",
            "qrguard_prepared_gallery_reference",
        ],
    ) | (image_sources == "gallery")
    deployment_mask = camera_mask | gallery_mask
    if not deployment_mask.any():
        return {
            "rows": 0,
            "macro_f1": None,
            "paired_groups": 0,
            "paired_verdict_agreement": None,
            "camera_clean_false_positive_rate": None,
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
            "camera_clean_false_positive_rate": (
                float(
                    (
                        probabilities[
                            camera_mask
                            & (frame.class_id.to_numpy(dtype=int) == 0)
                        ].argmax(axis=1)
                        != 0
                    ).mean()
                )
                if np.any(
                    camera_mask & (frame.class_id.to_numpy(dtype=int) == 0)
                )
                else None
            ),
        }
    )
    return metrics


def _topology_counterfactual_metrics(
    frame: pd.DataFrame, probabilities: np.ndarray
) -> dict:
    """Measure clean-label stability across fixed Version/mask QR families."""

    source = "procedural_qrguard_topology_counterfactual"
    mask = frame.source.astype(str).to_numpy() == source
    subset = frame.loc[mask].reset_index(drop=True)
    selected = probabilities[mask]
    if subset.empty:
        return {
            "rows": 0,
            "groups": 0,
            "versions": [],
            "masks": [],
            "clean_false_positive_rate": None,
            "clean_structural_probability_span_p95": None,
            "maximum_group_probability_span": None,
            "per_version_clean_false_positive_rate": {},
            "per_mask_clean_false_positive_rate": {},
            "per_condition_clean_false_positive_rate": {},
            "mask_probability_span_p95_within_condition": None,
            "condition_probability_span_p95_within_mask": None,
            "worst_group_probability_spans": [],
        }
    if len(selected) != len(subset):
        raise AssertionError("topology probability/frame alignment failed")
    p_structural = 1.0 - selected[:, 0]
    predicted_nonclean = selected.argmax(axis=1) != 0
    working = subset.copy()
    if "quality_condition" not in working:
        working["quality_condition"] = "not_recorded"
    working["p_structural"] = p_structural
    working["predicted_nonclean"] = predicted_nonclean
    group_span_frame = (
        working.groupby("group_id", dropna=False)
        .agg(
            qr_version=("qr_version", "first"),
            probability_min=("p_structural", "min"),
            probability_max=("p_structural", "max"),
        )
        .reset_index()
    )
    group_span_frame["probability_span"] = (
        group_span_frame.probability_max - group_span_frame.probability_min
    )
    group_spans = group_span_frame.probability_span.to_numpy(dtype=float)
    within_condition_spans = (
        working.groupby(["group_id", "quality_condition"], dropna=False)
        .p_structural.agg(lambda values: float(values.max() - values.min()))
        .to_numpy(dtype=float)
    )
    within_mask_condition_spans = (
        working.groupby(["group_id", "mask_pattern"], dropna=False)
        .p_structural.agg(lambda values: float(values.max() - values.min()))
        .to_numpy(dtype=float)
    )

    def false_positive_rates(column: str) -> dict[str, float]:
        return {
            str(key): float(part.predicted_nonclean.mean())
            for key, part in working.groupby(column, dropna=False)
        }

    versions = sorted(int(value) for value in working.qr_version.unique())
    masks = sorted(int(value) for value in working.mask_pattern.unique())
    return {
        "rows": int(len(working)),
        "groups": int(working.group_id.nunique()),
        "versions": versions,
        "masks": masks,
        "clean_false_positive_rate": float(predicted_nonclean.mean()),
        "clean_structural_probability_span_p95": float(
            np.percentile(group_spans, 95)
        ),
        "maximum_group_probability_span": float(group_spans.max()),
        "per_version_clean_false_positive_rate": false_positive_rates("qr_version"),
        "per_mask_clean_false_positive_rate": false_positive_rates("mask_pattern"),
        "per_condition_clean_false_positive_rate": false_positive_rates(
            "quality_condition"
        ),
        "mask_probability_span_p95_within_condition": float(
            np.percentile(within_condition_spans, 95)
        ),
        "condition_probability_span_p95_within_mask": float(
            np.percentile(within_mask_condition_spans, 95)
        ),
        "worst_group_probability_spans": [
            {
                "group_id": str(row.group_id),
                "qr_version": int(row.qr_version),
                "probability_span": float(row.probability_span),
            }
            for row in group_span_frame.sort_values(
                "probability_span", ascending=False
            ).itertuples(index=False)
        ][:10],
    }


def _source_clean_false_positive_rate(
    frame: pd.DataFrame, probabilities: np.ndarray, source: str
) -> float | None:
    mask = (frame.source.astype(str).to_numpy() == source) & (
        frame.class_id.to_numpy(dtype=int) == 0
    )
    if not mask.any():
        return None
    return float((probabilities[mask].argmax(axis=1) != 0).mean())


def _clean_capture_stability_metrics(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
    source: str = CONSUMED_BLIND_CLEAN_SOURCE,
) -> dict:
    """Measure clean verdict and temporal stability for one Camera source."""
    mask = (frame.source.astype(str).to_numpy() == source) & (
        frame.class_id.to_numpy(dtype=int) == 0
    )
    subset = frame.loc[mask].reset_index(drop=True)
    selected = probabilities[mask]
    if subset.empty:
        return {
            "source": source,
            "rows": 0,
            "sessions": 0,
            "clean_false_positive_rate": None,
            "session_clean_false_positive_rate": None,
            "temporal_probability_span_p95": None,
            "maximum_temporal_probability_span": None,
            "per_version_clean_false_positive_rate": {},
            "per_mask_clean_false_positive_rate": {},
        }
    if len(selected) != len(subset):
        raise AssertionError("clean Camera probability/frame alignment failed")
    working = subset.copy()
    working["p_structural"] = 1.0 - selected[:, 0]
    working["predicted_nonclean"] = selected.argmax(axis=1) != 0
    partner_column = "paired_group" if "paired_group" in working else "group_id"
    session_rows = []
    for partner, indices in working.groupby(partner_column).groups.items():
        positions = np.asarray(list(indices), dtype=int)
        mean_probability = selected[positions].mean(axis=0)
        values = working.iloc[positions].p_structural.to_numpy(dtype=float)
        session_rows.append(
            {
                "paired_group": str(partner),
                "predicted_nonclean": bool(mean_probability.argmax() != 0),
                "probability_span": float(values.max() - values.min()),
            }
        )
    session_frame = pd.DataFrame(session_rows)

    def rates(column: str) -> dict[str, float]:
        if column not in working:
            return {}
        return {
            str(key): float(part.predicted_nonclean.mean())
            for key, part in working.groupby(column, dropna=False)
        }

    spans = session_frame.probability_span.to_numpy(dtype=float)
    return {
        "source": source,
        "rows": int(len(working)),
        "sessions": int(len(session_frame)),
        "clean_false_positive_rate": float(working.predicted_nonclean.mean()),
        "session_clean_false_positive_rate": float(
            session_frame.predicted_nonclean.mean()
        ),
        "temporal_probability_span_p95": float(np.percentile(spans, 95)),
        "maximum_temporal_probability_span": float(spans.max()),
        "per_version_clean_false_positive_rate": rates("qr_version"),
        "per_mask_clean_false_positive_rate": rates("mask_pattern"),
    }


def _verified_attack_fit_metrics(
    frame: pd.DataFrame, probabilities: np.ndarray
) -> dict:
    """Measure fit on consumed attacks without treating them as holdout evidence."""

    if len(frame) != len(probabilities):
        raise AssertionError("verified attack probability/frame alignment failed")
    if frame.empty:
        return {
            "evidence_role": "development_train_fit_only",
            "rows": 0,
            "sessions": 0,
            "adversarial_class_recall": None,
            "nonclean_recall": None,
            "session_nonclean_recall": None,
        }
    predictions = probabilities.argmax(axis=1)
    partner_column = "paired_group" if "paired_group" in frame else "group_id"
    session_nonclean = []
    groups = frame.reset_index(drop=True).groupby(partner_column).groups
    for indices in groups.values():
        positions = np.asarray(list(indices), dtype=int)
        session_prediction = probabilities[positions].mean(axis=0).argmax()
        session_nonclean.append(bool(session_prediction != 0))
    return {
        "evidence_role": "development_train_fit_only",
        "promotion_eligible": False,
        "rows": len(frame),
        "sessions": len(session_nonclean),
        "adversarial_class_recall": float((predictions == 1).mean()),
        "nonclean_recall": float((predictions != 0).mean()),
        "session_nonclean_recall": float(np.mean(session_nonclean)),
    }


def _checkpoint_constraint_status(
    values: dict[str, float | None], constraints: dict | None
) -> dict:
    """Return a deterministic feasibility summary for checkpoint ranking."""
    failures = []
    total_excess = 0.0
    for name, rule in (constraints or {}).items():
        if not isinstance(rule, dict):
            raise ValueError(f"checkpoint constraint must be an object: {name}")
        value = values.get(name)
        if value is None or not np.isfinite(float(value)):
            failures.append(f"{name}:missing")
            total_excess += 1.0
            continue
        numeric = float(value)
        if "maximum" in rule:
            maximum = float(rule["maximum"])
            if numeric > maximum:
                failures.append(f"{name}:{numeric:.6f}>{maximum:.6f}")
                total_excess += numeric - maximum
        if "minimum" in rule:
            minimum = float(rule["minimum"])
            if numeric < minimum:
                failures.append(f"{name}:{numeric:.6f}<{minimum:.6f}")
                total_excess += minimum - numeric
        if "maximum" not in rule and "minimum" not in rule:
            raise ValueError(f"checkpoint constraint has no bound: {name}")
    return {
        "passed": not failures,
        "violation_count": len(failures),
        "total_excess": float(total_excess),
        "failures": failures,
    }


def _checkpoint_selection_rank(row: dict) -> tuple[int, int, float, float]:
    """Prefer feasible checkpoints, then the least-bad infeasible frontier."""
    return (
        1 if row.get("selection_constraints_passed", True) else 0,
        -int(row.get("selection_constraint_violation_count", 0)),
        -float(row.get("selection_constraint_total_excess", 0.0)),
        float(row["selection_score"]),
    )


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


def _cpu_byte_rng_state(state: object) -> torch.Tensor:
    """Normalise a deserialised RNG state for CPU/CUDA generator APIs.

    ``torch.load(..., map_location=device)`` also moves the CPU sampler and
    global RNG state tensors to CUDA.  PyTorch's generator state setters
    require CPU ``torch.uint8`` tensors, so move and normalise them explicitly.
    This also keeps checkpoints portable across CPU-only and CUDA runtimes.
    """
    if isinstance(state, torch.Tensor):
        return state.detach().to(device="cpu", dtype=torch.uint8).contiguous()
    return torch.as_tensor(state, dtype=torch.uint8, device="cpu").contiguous()


def _restore_rng_state(state: dict) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(_cpu_byte_rng_state(state["torch"]))
    if torch.cuda.is_available() and "cuda" in state:
        torch.cuda.set_rng_state_all(
            [_cpu_byte_rng_state(item) for item in state["cuda"]]
        )


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


def _validate_candidate_manifest_contract(
    manifest_path: Path, config: dict
) -> None:
    """Refuse training when a locked candidate dataset is incomplete or stale."""
    contract = config.get("candidate_manifest")
    if not contract:
        return
    expected_rows = int(contract["rows"])
    expected_hash = str(contract["sha256"]).lower()
    actual_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        actual_rows = sum(1 for _ in csv.DictReader(handle))
    failures = []
    if actual_rows != expected_rows:
        failures.append(f"rows {actual_rows} != locked {expected_rows}")
    if actual_hash != expected_hash:
        failures.append(f"sha256 {actual_hash} != locked {expected_hash}")
    if failures:
        raise ValueError(
            "candidate manifest contract failed: " + "; ".join(failures)
        )


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
    parser.add_argument(
        "--initial-weights",
        type=Path,
        help="optional locked Structural state_dict used to initialise a fresh run",
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
    _validate_candidate_manifest_contract(MANIFEST, RUN_CONFIG)
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
    verified_attack_frame = train_frame[
        train_frame.source.astype(str) == CONSUMED_BLIND_ATTACK_SOURCE
    ].reset_index(drop=True)
    pd.crosstab(frame.split, [frame.label, frame.source]).to_csv(
        PERFORMANCE / "dataset_composition.csv"
    )

    sampler_generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(
        ManifestDataset(
            train_frame,
            _transforms(True),
            paired_transform=(
                _transforms(True, exposure_variant=True)
                if EXPOSURE_CONFIG.enabled
                else None
            ),
        ),
        batch_size=BATCH_SIZE,
        sampler=_sampler(
            train_frame,
            sampler_generator,
            TRAINING_CONFIG.get("sampling"),
        ),
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
    verified_attack_loader = (
        DataLoader(
            ManifestDataset(verified_attack_frame, _transforms(False)),
            batch_size=BATCH_SIZE,
            shuffle=False,
            num_workers=0,
        )
        if not verified_attack_frame.empty
        else None
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(
        "Structural device:",
        torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
    )
    model = _model().to(device)
    initial_weights = None
    configured_initial = TRAINING_CONFIG.get("initial_checkpoint")
    requested_initial = args.initial_weights
    if requested_initial is None and args.mode == "fresh" and configured_initial:
        requested_initial = ROOT / str(configured_initial)
    if requested_initial is not None:
        if args.mode != "fresh":
            raise ValueError("--initial-weights is valid only in fresh mode")
        initial_weights = requested_initial.expanduser().resolve(strict=True)
        expected_hash = str(
            TRAINING_CONFIG.get("initial_checkpoint_sha256", "")
        ).lower()
        actual_hash = hashlib.sha256(initial_weights.read_bytes()).hexdigest()
        if not expected_hash or actual_hash != expected_hash:
            raise ValueError(
                "initial checkpoint does not match the hash locked in the config"
            )
        model.load_state_dict(
            torch.load(initial_weights, map_location=device, weights_only=True)
        )
        print(f"Initialised from locked Structural checkpoint {actual_hash}")
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    history = []
    best_score = -float("inf")
    best_selection_rank: tuple[int, int, float, float] | None = None
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
        # Keep portable CPU/sampler RNG states on CPU while loading. Model and
        # optimizer state is moved to the parameter devices by their loaders.
        resume_checkpoint = torch.load(
            checkpoint_last, map_location="cpu", weights_only=False
        )
        validate_run_identity(identity, resume_checkpoint.get("identity", {}))
        model.load_state_dict(resume_checkpoint["model_state"])
        history = list(resume_checkpoint["history"])
        best_score = float(resume_checkpoint["best_score"])
        if history:
            best_selection_rank = max(
                _checkpoint_selection_rank(row) for row in history
            )
        global_epoch = int(resume_checkpoint["global_epoch"])
        sampler_generator.set_state(
            _cpu_byte_rng_state(resume_checkpoint["sampler_generator_state"])
        )
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
        ("head", HEAD_EPOCHS, HEAD_LEARNING_RATE),
        ("finetune", FINETUNE_EPOCHS, FINETUNE_LEARNING_RATE),
    )
    if args.mode in {"fresh", "resume"}:
        topology_consistency_multiplier = float(
            TRAINING_CONFIG.get("topology_consistency_multiplier", 1.0)
        )
        if not 1.0 <= topology_consistency_multiplier <= 5.0:
            raise ValueError(
                "topology_consistency_multiplier must be between 1 and 5"
            )
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
                running_loss, running_consistency, seen = 0.0, 0.0, 0
                if EXPOSURE_CONFIG.enabled:
                    for images, exposure_images, labels, row_indices in train_loader:
                        optimizer.zero_grad(set_to_none=True)
                        targets = labels.to(device)
                        logits = model(images.to(device))
                        exposure_logits = model(exposure_images.to(device))
                        classification_loss = 0.5 * (
                            criterion(logits, targets)
                            + criterion(exposure_logits, targets)
                        )
                        consistency_loss = symmetric_kl_loss(
                            logits, exposure_logits
                        )
                        loss = (
                            classification_loss
                            + EXPOSURE_CONFIG.consistency_weight * consistency_loss
                        )
                        if topology_consistency_multiplier > 1.0:
                            batch_sources = train_frame.iloc[
                                row_indices.detach().cpu().numpy()
                            ].source.astype(str).to_numpy()
                            topology_mask = torch.as_tensor(
                                batch_sources == TOPOLOGY_COUNTERFACTUAL_SOURCE,
                                dtype=torch.bool,
                                device=device,
                            )
                            if bool(topology_mask.any()):
                                topology_consistency = symmetric_kl_loss(
                                    logits[topology_mask],
                                    exposure_logits[topology_mask],
                                )
                                loss = loss + (
                                    EXPOSURE_CONFIG.consistency_weight
                                    * (topology_consistency_multiplier - 1.0)
                                    * topology_consistency
                                )
                        loss.backward()
                        optimizer.step()
                        running_loss += float(loss.item()) * len(labels)
                        running_consistency += float(consistency_loss.item()) * len(
                            labels
                        )
                        seen += len(labels)
                else:
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
                topology_validation = _topology_counterfactual_metrics(
                    validation_frame, validation_probabilities
                )
                consumed_blind_clean_validation = _clean_capture_stability_metrics(
                    validation_frame, validation_probabilities
                )
                if verified_attack_loader is None:
                    verified_attack_selection = _verified_attack_fit_metrics(
                        verified_attack_frame,
                        np.empty((0, len(CLASS_NAMES)), dtype=float),
                    )
                else:
                    verified_attack_logits, _, _ = _predict(
                        model, verified_attack_loader, device
                    )
                    verified_attack_selection = _verified_attack_fit_metrics(
                        verified_attack_frame,
                        _probabilities(verified_attack_logits, 1.0),
                    )
                procedural_clean_fpr = _source_clean_false_positive_rate(
                    validation_frame,
                    validation_probabilities,
                    "procedural_qrguard",
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
                exposure_validation = _evaluate_exposure_invariance(
                    model,
                    validation_frame,
                    device,
                    temperature=1.0,
                )
                exposure_agreement = exposure_validation.get(
                    "verdict_agreement_all_exposures", metrics["macro_f1"]
                )
                clean_exposure_span = exposure_validation.get(
                    "clean_structural_probability_span_p95"
                )
                camera_clean_fpr = deployment_validation.get(
                    "camera_clean_false_positive_rate"
                )
                selection_weights = TRAINING_CONFIG.get(
                    "checkpoint_selection_weights", {}
                )
                selection_score = (
                    float(selection_weights.get("global_macro_f1", 0.25))
                    * metrics["macro_f1"]
                    + float(
                        selection_weights.get("deployment_domain_macro_f1", 0.50)
                    )
                    * deployment_macro_f1
                    + float(
                        selection_weights.get(
                            "non_test_paired_verdict_agreement", 0.25
                        )
                    )
                    * paired_agreement
                    + float(
                        selection_weights.get("exposure_verdict_agreement", 0.0)
                    )
                    * exposure_agreement
                    - max(0, qrdn_fpr - 0.05) * 2
                )
                selection_penalties = TRAINING_CONFIG.get(
                    "checkpoint_selection_penalties", {}
                )
                camera_clean_penalty = selection_penalties.get(
                    "camera_clean_false_positive_rate", {}
                )
                if camera_clean_fpr is not None and camera_clean_penalty:
                    selection_score -= float(camera_clean_penalty.get("weight", 0)) * max(
                        0.0,
                        camera_clean_fpr
                        - float(camera_clean_penalty.get("maximum", 0.05)),
                    )
                exposure_span_penalty = selection_penalties.get(
                    "clean_exposure_probability_span_p95", {}
                )
                if clean_exposure_span is not None and exposure_span_penalty:
                    selection_score -= float(exposure_span_penalty.get("weight", 0)) * max(
                        0.0,
                        clean_exposure_span
                        - float(exposure_span_penalty.get("maximum", 0.15)),
                    )
                topology_fpr_penalty = selection_penalties.get(
                    "topology_counterfactual_clean_false_positive_rate", {}
                )
                topology_fpr = topology_validation.get("clean_false_positive_rate")
                if topology_fpr is not None and topology_fpr_penalty:
                    selection_score -= float(
                        topology_fpr_penalty.get("weight", 0)
                    ) * max(
                        0.0,
                        topology_fpr
                        - float(topology_fpr_penalty.get("maximum", 0.01)),
                    )
                topology_span_penalty = selection_penalties.get(
                    "topology_counterfactual_probability_span_p95", {}
                )
                topology_span = topology_validation.get(
                    "clean_structural_probability_span_p95"
                )
                if topology_span is not None and topology_span_penalty:
                    selection_score -= float(
                        topology_span_penalty.get("weight", 0)
                    ) * max(
                        0.0,
                        topology_span
                        - float(topology_span_penalty.get("maximum", 0.15)),
                    )
                procedural_clean_penalty = selection_penalties.get(
                    "procedural_clean_false_positive_rate", {}
                )
                if procedural_clean_fpr is not None and procedural_clean_penalty:
                    selection_score -= float(
                        procedural_clean_penalty.get("weight", 0)
                    ) * max(
                        0.0,
                        procedural_clean_fpr
                        - float(procedural_clean_penalty.get("maximum", 0.10)),
                    )
                selection_constraint_values = {
                    "camera_clean_false_positive_rate": camera_clean_fpr,
                    "topology_counterfactual_clean_false_positive_rate": (
                        topology_fpr
                    ),
                    "procedural_clean_false_positive_rate": procedural_clean_fpr,
                    "consumed_blind_clean_false_positive_rate": (
                        consumed_blind_clean_validation.get(
                            "clean_false_positive_rate"
                        )
                    ),
                    "consumed_blind_session_clean_false_positive_rate": (
                        consumed_blind_clean_validation.get(
                            "session_clean_false_positive_rate"
                        )
                    ),
                    "verified_attack_development_nonclean_recall": (
                        verified_attack_selection.get("nonclean_recall")
                    ),
                }
                selection_constraints = _checkpoint_constraint_status(
                    selection_constraint_values,
                    TRAINING_CONFIG.get("checkpoint_selection_constraints"),
                )
                row = {
                    "epoch": global_epoch,
                    "stage": stage,
                    "stage_epoch": stage_epoch + 1,
                    "train_loss": running_loss / seen,
                    "train_exposure_consistency_loss": (
                        running_consistency / seen
                        if EXPOSURE_CONFIG.enabled
                        else None
                    ),
                    "validation_macro_f1": metrics["macro_f1"],
                    "validation_deployment_macro_f1": deployment_macro_f1,
                    "validation_paired_groups": deployment_validation["paired_groups"],
                    "validation_paired_verdict_agreement": paired_agreement,
                    "validation_exposure_verdict_agreement": exposure_agreement,
                    "validation_exposure_probability_span_p95": exposure_validation.get(
                        "structural_probability_span_p95"
                    ),
                    "validation_clean_exposure_probability_span_p95": clean_exposure_span,
                    "validation_topology_clean_false_positive_rate": topology_fpr,
                    "validation_topology_probability_span_p95": topology_span,
                    "validation_procedural_clean_false_positive_rate": (
                        procedural_clean_fpr
                    ),
                    "validation_camera_clean_false_positive_rate": camera_clean_fpr,
                    "validation_consumed_blind_clean_false_positive_rate": (
                        consumed_blind_clean_validation.get(
                            "clean_false_positive_rate"
                        )
                    ),
                    "validation_consumed_blind_session_clean_false_positive_rate": (
                        consumed_blind_clean_validation.get(
                            "session_clean_false_positive_rate"
                        )
                    ),
                    "validation_consumed_blind_temporal_probability_span_p95": (
                        consumed_blind_clean_validation.get(
                            "temporal_probability_span_p95"
                        )
                    ),
                    "verified_attack_development_nonclean_train_fit_recall": (
                        verified_attack_selection.get("nonclean_recall")
                    ),
                    "verified_attack_development_session_train_fit_recall": (
                        verified_attack_selection.get("session_nonclean_recall")
                    ),
                    "validation_qrdn_clean_fpr": qrdn_fpr,
                    "selection_score": selection_score,
                    "selection_constraints_passed": selection_constraints["passed"],
                    "selection_constraint_violation_count": (
                        selection_constraints["violation_count"]
                    ),
                    "selection_constraint_total_excess": selection_constraints[
                        "total_excess"
                    ],
                    "selection_constraint_failures": selection_constraints[
                        "failures"
                    ],
                }
                history.append(row)
                print(json.dumps(row))
                selection_rank = _checkpoint_selection_rank(row)
                if best_selection_rank is None or selection_rank > best_selection_rank:
                    best_selection_rank = selection_rank
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
    uncalibrated_validation_probabilities = _probabilities(validation_logits, 1.0)
    validation_selection_metrics = _deployment_validation_metrics(
        validation_frame, uncalibrated_validation_probabilities
    )
    validation_selection_metrics["procedural_clean_false_positive_rate"] = (
        _source_clean_false_positive_rate(
            validation_frame,
            uncalibrated_validation_probabilities,
            "procedural_qrguard",
        )
    )
    validation_selection_metrics["consumed_blind_clean"] = (
        _clean_capture_stability_metrics(
            validation_frame, uncalibrated_validation_probabilities
        )
    )
    calibration_config = TRAINING_CONFIG.get("calibration", {})
    calibration_weights = None
    if calibration_config.get("source_family_weighted", False):
        calibration_weights = _sampling_weights(
            validation_frame,
            {
                "source_family_draw_fractions": calibration_config.get(
                    "source_family_draw_fractions",
                    TRAINING_CONFIG.get("sampling", {}).get(
                        "source_family_draw_fractions", {}
                    ),
                )
            },
        )
    temperature = _fit_temperature(
        validation_logits,
        validation_labels,
        calibration_weights,
    )
    validation_probabilities = _probabilities(validation_logits, temperature)
    topology_counterfactual_metrics = _topology_counterfactual_metrics(
        validation_frame, validation_probabilities
    )
    consumed_blind_clean_metrics = _clean_capture_stability_metrics(
        validation_frame, validation_probabilities
    )
    if verified_attack_loader is None:
        verified_attack_probabilities = np.empty((0, len(CLASS_NAMES)), dtype=float)
    else:
        verified_attack_logits, _, _ = _predict(
            model, verified_attack_loader, device
        )
        verified_attack_probabilities = _probabilities(
            verified_attack_logits, temperature
        )
    verified_attack_fit = _verified_attack_fit_metrics(
        verified_attack_frame, verified_attack_probabilities
    )
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
    exposure_evidence_frame = (
        runtime_frame if not runtime_frame.empty else validation_frame
    )
    final_exposure_metrics = _evaluate_exposure_invariance(
        model,
        exposure_evidence_frame,
        device,
        temperature=temperature,
    )
    final_exposure_metrics["evidence_scope"] = (
        "locked_runtime_holdout"
        if not runtime_frame.empty
        else "development_validation_fallback"
    )

    gate_failures = []
    performance_gates = RUN_CONFIG.get("deployment_gates", {})
    synthetic_macro_f1_min = float(
        performance_gates.get("synthetic_grouped_macro_f1_min", 0.85)
    )
    adversarial_recall_min = float(
        performance_gates.get("synthetic_adversarial_recall_min", 0.75)
    )
    tampered_recall_min = float(
        performance_gates.get("synthetic_tampered_recall_min", 0.90)
    )
    synthetic_clean_recall_min = performance_gates.get(
        "synthetic_clean_recall_min"
    )
    if test_metrics["macro_f1"] < synthetic_macro_f1_min:
        gate_failures.append(
            "synthetic grouped macro-F1 "
            f"{test_metrics['macro_f1']:.4f} < {synthetic_macro_f1_min:.4f}"
        )
    if (
        synthetic_clean_recall_min is not None
        and test_metrics["per_class"]["clean"]["recall"]
        < float(synthetic_clean_recall_min)
    ):
        gate_failures.append(
            "synthetic clean recall "
            f"{test_metrics['per_class']['clean']['recall']:.4f} < "
            f"{float(synthetic_clean_recall_min):.4f}"
        )
    if (
        test_metrics["per_class"]["adversarial"]["recall"]
        < adversarial_recall_min
    ):
        gate_failures.append(
            "adversarial recall "
            f"{test_metrics['per_class']['adversarial']['recall']:.4f} < "
            f"{adversarial_recall_min:.4f}"
        )
    if test_metrics["per_class"]["tampered"]["recall"] < tampered_recall_min:
        gate_failures.append(
            "tampered recall "
            f"{test_metrics['per_class']['tampered']['recall']:.4f} < "
            f"{tampered_recall_min:.4f}"
        )
    if external_metrics["false_positive_rate_at_0_5"] > 0.05:
        gate_failures.append(
            f"QR-DN clean FPR {external_metrics['false_positive_rate_at_0_5']:.4f} > 0.0500"
        )
    if test_metrics["ece"] > 0.05:
        gate_failures.append(f"synthetic test ECE {test_metrics['ece']:.4f} > 0.0500")
    if EXPOSURE_CONFIG.enabled:
        exposure_gates = RUN_CONFIG.get("deployment_gates", {})
        minimum_agreement = float(
            exposure_gates.get("exposure_verdict_agreement_min", 0.95)
        )
        maximum_clean_span = float(
            exposure_gates.get("clean_exposure_probability_span_p95_max", 0.15)
        )
        exposure_agreement = final_exposure_metrics.get(
            "verdict_agreement_all_exposures"
        )
        clean_span = final_exposure_metrics.get(
            "clean_structural_probability_span_p95"
        )
        if exposure_agreement is None or exposure_agreement < minimum_agreement:
            gate_failures.append(
                "exposure verdict agreement "
                f"{exposure_agreement}; require min {minimum_agreement:.2f}"
            )
        if clean_span is None or clean_span > maximum_clean_span:
            gate_failures.append(
                "clean exposure probability span P95 "
                f"{clean_span}; require max {maximum_clean_span:.2f}"
            )
    topology_recipe = RUN_CONFIG.get("topology_counterfactuals", {})
    if topology_recipe.get("enabled", False):
        topology_gates = RUN_CONFIG.get("deployment_gates", {})
        expected_versions = sorted(
            int(item["version"]) for item in topology_recipe.get("versions", [])
        )
        observed_versions = topology_counterfactual_metrics.get("versions", [])
        observed_masks = topology_counterfactual_metrics.get("masks", [])
        expected_validation_identities = int(
            topology_recipe.get("validation_identities_per_error_correction", 1)
        )
        expected_validation_groups = len(expected_versions) * len(
            topology_recipe.get("error_corrections", ("L", "M", "Q", "H"))
        ) * expected_validation_identities
        if observed_versions != expected_versions:
            gate_failures.append(
                "topology counterfactual Version coverage mismatch: "
                f"{observed_versions} != {expected_versions}"
            )
        if observed_masks != list(range(8)):
            gate_failures.append(
                f"topology counterfactual mask coverage {observed_masks}; require 0-7"
            )
        if topology_counterfactual_metrics.get("groups") != expected_validation_groups:
            gate_failures.append(
                "topology counterfactual validation groups "
                f"{topology_counterfactual_metrics.get('groups')}; require "
                f"{expected_validation_groups}"
            )
        topology_fpr_max = float(
            topology_gates.get(
                "topology_counterfactual_clean_false_positive_rate_max", 0.01
            )
        )
        topology_fpr = topology_counterfactual_metrics.get(
            "clean_false_positive_rate"
        )
        if topology_fpr is None or topology_fpr > topology_fpr_max:
            gate_failures.append(
                "topology counterfactual clean FPR "
                f"{topology_fpr}; require max {topology_fpr_max:.4f}"
            )
        topology_span_max = float(
            topology_gates.get(
                "topology_counterfactual_probability_span_p95_max", 0.15
            )
        )
        topology_span = topology_counterfactual_metrics.get(
            "clean_structural_probability_span_p95"
        )
        if topology_span is None or topology_span > topology_span_max:
            gate_failures.append(
                "topology counterfactual clean probability span P95 "
                f"{topology_span}; require max {topology_span_max:.4f}"
            )

    consumed_fpr_max = performance_gates.get(
        "consumed_blind_clean_development_fpr_max"
    )
    consumed_session_fpr_max = performance_gates.get(
        "consumed_blind_clean_development_session_fpr_max"
    )
    if consumed_fpr_max is not None:
        consumed_fpr = consumed_blind_clean_metrics.get(
            "clean_false_positive_rate"
        )
        if consumed_fpr is None or consumed_fpr > float(consumed_fpr_max):
            gate_failures.append(
                "consumed M8 clean development FPR "
                f"{consumed_fpr}; require max {float(consumed_fpr_max):.4f}"
            )
    if consumed_session_fpr_max is not None:
        consumed_session_fpr = consumed_blind_clean_metrics.get(
            "session_clean_false_positive_rate"
        )
        if consumed_session_fpr is None or consumed_session_fpr > float(
            consumed_session_fpr_max
        ):
            gate_failures.append(
                "consumed M8 clean development session FPR "
                f"{consumed_session_fpr}; require max "
                f"{float(consumed_session_fpr_max):.4f}"
            )

    verified_attack_recall_min = performance_gates.get(
        "verified_attack_development_nonclean_recall_min"
    )
    if verified_attack_recall_min is not None:
        value = verified_attack_fit.get("nonclean_recall")
        if value is None or value < float(verified_attack_recall_min):
            gate_failures.append(
                "consumed verified-attack development non-clean recall "
                f"{value}; require min {float(verified_attack_recall_min):.4f}"
            )
    verified_attack_session_min = performance_gates.get(
        "verified_attack_development_session_recall_min"
    )
    if verified_attack_session_min is not None:
        value = verified_attack_fit.get("session_nonclean_recall")
        if value is None or value < float(verified_attack_session_min):
            gate_failures.append(
                "consumed verified-attack development session recall "
                f"{value}; require min {float(verified_attack_session_min):.4f}"
            )

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
    if VERSION.startswith(
        ("structural-2026.03", "structural-2026.09", "structural-r07")
    ):
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
        "audit_v3.json"
        if VERSION.startswith(
            ("structural-2026.03", "structural-2026.09", "structural-r07")
        )
        else "audit.json"
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

    run_config = RUN_CONFIG
    blind_acceptance: dict | None = None
    if run_config.get("deployment_gates", {}).get("fresh_blind_holdout_required"):
        blind_acceptance_path = PERFORMANCE / "blind_holdout_acceptance.json"
        if blind_acceptance_path.is_file():
            blind_acceptance = json.loads(
                blind_acceptance_path.read_text(encoding="utf-8")
            )
        blind_matches = bool(
            blind_acceptance
            and blind_acceptance.get("gate_passed") is True
            and blind_acceptance.get("evidence_role") == "blind_holdout"
            and blind_acceptance.get("candidate_model_sha256") == export["sha256"]
        )
        if not blind_matches:
            deployment_failures.append(
                "fresh blinded Structural coverage holdout is missing or does not "
                "match this candidate model"
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
        "initial_checkpoint": (
            str(initial_weights.relative_to(ROOT)) if initial_weights else None
        ),
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
        "sampling": TRAINING_CONFIG.get(
            "sampling", {"strategy": "legacy_class_domain_balanced"}
        ),
        "calibration": {
            **calibration_config,
            "fitted_with_source_family_weights": calibration_weights is not None,
        },
        "validation_selection_contract": validation_selection_metrics,
        "topology_counterfactual_validation": topology_counterfactual_metrics,
        "consumed_blind_clean_development_validation": (
            consumed_blind_clean_metrics
        ),
        "consumed_verified_attack_development_train_fit": verified_attack_fit,
        "synthetic_grouped_test": test_metrics,
        "classification_report": classification,
        "qrdn_external_clean_holdout": external_metrics,
        "exact_app_runtime_holdout": runtime_metrics,
        "exact_app_gallery_holdout": gallery_metrics,
        "paired_gallery_camera_consistency": paired_metrics,
        "exposure_invariance": final_exposure_metrics,
        "exposure_training": {
            "enabled": EXPOSURE_CONFIG.enabled,
            "consistency_weight": EXPOSURE_CONFIG.consistency_weight,
            "ev_range": list(EXPOSURE_CONFIG.ev_range),
            "evaluation_ev": list(EXPOSURE_CONFIG.evaluation_ev),
        },
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
        "fresh_blind_holdout": blind_acceptance,
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
        "runtime_policy": run_config.get("runtime_policy", {}),
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
    exposure_verdict_agreement = final_exposure_metrics.get(
        "verdict_agreement_all_exposures", "not evaluated"
    )
    clean_exposure_span = final_exposure_metrics.get(
        "clean_structural_probability_span_p95", "not evaluated"
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
| Exposure-sweep verdict agreement | {exposure_verdict_agreement} |
| Clean exposure probability span P95 | {clean_exposure_span} |
| Consumed M8 clean development FPR | {consumed_blind_clean_metrics.get("clean_false_positive_rate", "not evaluated")} |
| Consumed M8 clean session FPR | {consumed_blind_clean_metrics.get("session_clean_false_positive_rate", "not evaluated")} |
| Consumed M8 temporal probability span P95 | {consumed_blind_clean_metrics.get("temporal_probability_span_p95", "not evaluated")} |
| Consumed verified-attack non-clean train-fit recall | {verified_attack_fit.get("nonclean_recall", "not evaluated")} |
| Consumed verified-attack session train-fit recall | {verified_attack_fit.get("session_nonclean_recall", "not evaluated")} |
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
        writer.writerow(["exposure_verdict_agreement", exposure_verdict_agreement])
        writer.writerow(["clean_exposure_probability_span_p95", clean_exposure_span])
        writer.writerow(
            [
                "consumed_blind_clean_development_fpr",
                consumed_blind_clean_metrics.get("clean_false_positive_rate"),
            ]
        )
        writer.writerow(
            [
                "consumed_verified_attack_development_nonclean_train_fit_recall",
                verified_attack_fit.get("nonclean_recall"),
            ]
        )
        writer.writerow(
            [
                "consumed_verified_attack_development_session_train_fit_recall",
                verified_attack_fit.get("session_nonclean_recall"),
            ]
        )
        writer.writerow(
            [
                "consumed_blind_clean_development_session_fpr",
                consumed_blind_clean_metrics.get(
                    "session_clean_false_positive_rate"
                ),
            ]
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
