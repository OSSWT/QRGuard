import pandas as pd
import pytest

from ml_training.structural.src.train_local import (
    CONSUMED_BLIND_CLEAN_SOURCE,
    _checkpoint_constraint_status,
    _checkpoint_selection_rank,
    _clean_capture_stability_metrics,
)


def test_feasible_checkpoint_outranks_higher_unconstrained_score() -> None:
    feasible = {
        "selection_score": 0.80,
        "selection_constraints_passed": True,
        "selection_constraint_violation_count": 0,
        "selection_constraint_total_excess": 0.0,
    }
    unstable = {
        "selection_score": 0.99,
        "selection_constraints_passed": False,
        "selection_constraint_violation_count": 1,
        "selection_constraint_total_excess": 0.01,
    }

    assert _checkpoint_selection_rank(feasible) > _checkpoint_selection_rank(unstable)


def test_constraint_status_reports_missing_and_out_of_bounds_metrics() -> None:
    status = _checkpoint_constraint_status(
        {"clean_fpr": 0.1, "agreement": None},
        {
            "clean_fpr": {"maximum": 0.05},
            "agreement": {"minimum": 0.95},
        },
    )

    assert status["passed"] is False
    assert status["violation_count"] == 2
    assert any("clean_fpr" in failure for failure in status["failures"])
    assert any("agreement:missing" == failure for failure in status["failures"])


def test_clean_camera_stability_aggregates_temporal_frames_by_session() -> None:
    frame = pd.DataFrame(
        {
            "source": [CONSUMED_BLIND_CLEAN_SOURCE] * 4,
            "class_id": [0] * 4,
            "paired_group": ["a", "a", "b", "b"],
            "group_id": ["ga", "ga", "gb", "gb"],
            "qr_version": [12] * 4,
            "mask_pattern": [1, 1, 4, 4],
        }
    )
    probabilities = __import__("numpy").array(
        [
            [0.9, 0.08, 0.02],
            [0.8, 0.15, 0.05],
            [0.4, 0.5, 0.1],
            [0.3, 0.6, 0.1],
        ]
    )

    metrics = _clean_capture_stability_metrics(frame, probabilities)

    assert metrics["rows"] == 4
    assert metrics["sessions"] == 2
    assert metrics["clean_false_positive_rate"] == 0.5
    assert metrics["session_clean_false_positive_rate"] == 0.5
    assert metrics["maximum_temporal_probability_span"] == pytest.approx(0.1)
