import pandas as pd
import pytest

from ml_training.structural.src.evaluate_paired_consistency import evaluate


def _row(group, source, label, probabilities, predicted):
    return {
        "paired_group": group,
        "image_source": source,
        "label": label,
        "p_clean": probabilities[0],
        "p_adversarial": probabilities[1],
        "p_tampered": probabilities[2],
        "predicted_type": predicted,
        "is_authoritative": True,
    }


def test_pair_metrics_measure_probability_and_verdict_consistency():
    frame = pd.DataFrame(
        [
            _row("a", "gallery", "clean", (0.95, 0.03, 0.02), "clean"),
            _row("a", "camera", "clean", (0.90, 0.06, 0.04), "clean"),
            _row("b", "gallery", "tampered", (0.02, 0.03, 0.95), "tampered"),
            _row("b", "camera", "tampered", (0.08, 0.05, 0.87), "tampered"),
        ]
    )

    metrics, pairs = evaluate(frame)

    assert metrics["overall"]["n"] == 2
    assert metrics["overall"]["verdict_agreement"] == 1.0
    assert metrics["overall"]["class_agreement"] == 1.0
    assert len(pairs) == 2


def test_pair_evaluation_rejects_label_mismatch():
    frame = pd.DataFrame(
        [
            _row("a", "gallery", "clean", (0.9, 0.05, 0.05), "clean"),
            _row("a", "camera", "tampered", (0.1, 0.1, 0.8), "tampered"),
        ]
    )

    with pytest.raises(ValueError, match="label mismatch"):
        evaluate(frame)
