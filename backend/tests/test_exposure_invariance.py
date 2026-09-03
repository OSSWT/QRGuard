import numpy as np
import pytest
import torch
from PIL import Image

from ml_training.structural.src.exposure_invariance import (
    ExposureInvarianceConfig,
    apply_exposure,
    exposure_consistency_metrics,
    symmetric_kl_loss,
)


def test_exposure_config_reads_locked_ranges() -> None:
    config = ExposureInvarianceConfig.from_mapping(
        {
            "enabled": True,
            "consistency_weight": 0.2,
            "ev_range": [-0.75, 0.75],
            "contrast_range": [0.8, 1.2],
            "gamma_range": [0.8, 1.25],
            "evaluation_ev": [-0.67, 0.0, 0.67],
        }
    )

    assert config.enabled is True
    assert config.consistency_weight == 0.2
    assert config.evaluation_ev == (-0.67, 0.0, 0.67)


def test_exposure_adjustment_preserves_geometry_and_changes_luminance() -> None:
    image = Image.new("RGB", (29, 29), color=(100, 100, 100))

    darker = apply_exposure(image, ev=-0.67)
    brighter = apply_exposure(image, ev=0.67)

    assert darker.size == image.size == brighter.size
    assert np.asarray(darker).mean() < 100 < np.asarray(brighter).mean()


def test_symmetric_kl_is_zero_for_equal_logits_and_positive_for_drift() -> None:
    first = torch.tensor([[3.0, 0.5, -1.0], [0.0, 1.0, 2.0]])
    shifted = torch.tensor([[-1.0, 0.5, 3.0], [2.0, 1.0, 0.0]])

    assert symmetric_kl_loss(first, first).item() == pytest.approx(0.0, abs=1e-7)
    assert symmetric_kl_loss(first, shifted).item() > 0.1


def test_consistency_metrics_separate_verdict_and_probability_drift() -> None:
    labels = np.asarray([0, 1])
    views = [
        np.asarray([[0.90, 0.05, 0.05], [0.20, 0.70, 0.10]]),
        np.asarray([[0.80, 0.10, 0.10], [0.25, 0.65, 0.10]]),
        np.asarray([[0.70, 0.15, 0.15], [0.30, 0.60, 0.10]]),
    ]

    metrics = exposure_consistency_metrics(views, labels)

    assert metrics["verdict_agreement_all_exposures"] == 1.0
    assert metrics["clean_structural_probability_span_p95"] == pytest.approx(0.2)


def test_consistency_metrics_detect_exposure_induced_verdict_flip() -> None:
    labels = np.asarray([0])
    views = [
        np.asarray([[0.80, 0.10, 0.10]]),
        np.asarray([[0.40, 0.30, 0.30]]),
    ]

    metrics = exposure_consistency_metrics(views, labels)

    assert metrics["verdict_agreement_all_exposures"] == 0.0
