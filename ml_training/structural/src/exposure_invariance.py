"""Exposure-invariance augmentation, consistency loss, and evaluation metrics."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
import torch.nn.functional as functional
from PIL import Image, ImageEnhance


def _range(value: Any, fallback: tuple[float, float]) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return fallback
    lower, upper = float(value[0]), float(value[1])
    if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
        raise ValueError(f"invalid augmentation range: {value!r}")
    return lower, upper


@dataclass(frozen=True)
class ExposureInvarianceConfig:
    enabled: bool = False
    consistency_weight: float = 0.0
    ev_range: tuple[float, float] = (-0.75, 0.75)
    contrast_range: tuple[float, float] = (0.8, 1.2)
    gamma_range: tuple[float, float] = (0.8, 1.25)
    evaluation_ev: tuple[float, ...] = (-0.67, 0.0, 0.67)

    @classmethod
    def from_mapping(cls, value: Any) -> ExposureInvarianceConfig:
        if not isinstance(value, dict):
            return cls()
        evaluation = tuple(
            float(item) for item in value.get("evaluation_ev", (-0.67, 0.0, 0.67))
        )
        if len(evaluation) < 2 or any(not math.isfinite(item) for item in evaluation):
            raise ValueError("evaluation_ev must contain at least two finite EV values")
        weight = float(value.get("consistency_weight", 0.0))
        if not 0.0 <= weight <= 2.0:
            raise ValueError("exposure consistency weight must be between 0 and 2")
        return cls(
            enabled=bool(value.get("enabled", False)),
            consistency_weight=weight,
            ev_range=_range(value.get("ev_range"), (-0.75, 0.75)),
            contrast_range=_range(value.get("contrast_range"), (0.8, 1.2)),
            gamma_range=_range(value.get("gamma_range"), (0.8, 1.25)),
            evaluation_ev=evaluation,
        )


def apply_exposure(
    image: Image.Image,
    *,
    ev: float,
    contrast: float = 1.0,
    gamma: float = 1.0,
) -> Image.Image:
    """Apply a bounded camera-like exposure change without altering geometry."""
    if contrast <= 0 or gamma <= 0:
        raise ValueError("contrast and gamma must be positive")
    rgb = image.convert("RGB")
    if gamma != 1.0:
        lookup = [
            min(255, max(0, round(255 * ((level / 255) ** gamma))))
            for level in range(256)
        ]
        rgb = rgb.point(lookup * 3)
    rgb = ImageEnhance.Brightness(rgb).enhance(2.0**float(ev))
    return ImageEnhance.Contrast(rgb).enhance(float(contrast))


class RandomExposureTransform:
    """Generate a moderate exposure view; severe unusable evidence is out of scope."""

    def __init__(self, config: ExposureInvarianceConfig) -> None:
        self.config = config

    def __call__(self, image: Image.Image) -> Image.Image:
        return apply_exposure(
            image,
            ev=random.uniform(*self.config.ev_range),
            contrast=random.uniform(*self.config.contrast_range),
            gamma=random.uniform(*self.config.gamma_range),
        )


class FixedExposureTransform:
    def __init__(self, ev: float) -> None:
        self.ev = float(ev)

    def __call__(self, image: Image.Image) -> Image.Image:
        return apply_exposure(image, ev=self.ev)


def symmetric_kl_loss(
    first_logits: torch.Tensor, second_logits: torch.Tensor
) -> torch.Tensor:
    """Penalise prediction drift while allowing gradients through both views."""
    first_log = functional.log_softmax(first_logits, dim=1)
    second_log = functional.log_softmax(second_logits, dim=1)
    first = first_log.exp()
    second = second_log.exp()
    return 0.5 * (
        functional.kl_div(first_log, second, reduction="batchmean")
        + functional.kl_div(second_log, first, reduction="batchmean")
    )


def exposure_consistency_metrics(
    probability_views: list[np.ndarray], labels: np.ndarray
) -> dict[str, Any]:
    """Summarise prediction stability across a deterministic exposure sweep."""
    if len(probability_views) < 2:
        raise ValueError("at least two probability views are required")
    stack = np.stack(probability_views, axis=0)
    if stack.ndim != 3 or stack.shape[1] != len(labels) or stack.shape[2] < 2:
        raise ValueError("probability views and labels have incompatible shapes")
    structural = 1.0 - stack[:, :, 0]
    verdicts = structural >= 0.5
    classes = stack.argmax(axis=2)
    spans = np.ptp(structural, axis=0)
    clean_spans = spans[np.asarray(labels) == 0]
    return {
        "views": int(stack.shape[0]),
        "rows": int(stack.shape[1]),
        "verdict_agreement_all_exposures": float(
            np.all(verdicts == verdicts[0:1], axis=0).mean()
        ),
        "class_agreement_all_exposures": float(
            np.all(classes == classes[0:1], axis=0).mean()
        ),
        "structural_probability_span_mean": float(spans.mean()),
        "structural_probability_span_p95": float(np.quantile(spans, 0.95)),
        "clean_structural_probability_span_p95": (
            float(np.quantile(clean_spans, 0.95)) if len(clean_spans) else None
        ),
        "clean_false_positive_rate_by_view": [
            float((view[np.asarray(labels) == 0] >= 0.5).mean())
            if np.any(np.asarray(labels) == 0)
            else None
            for view in structural
        ],
    }
