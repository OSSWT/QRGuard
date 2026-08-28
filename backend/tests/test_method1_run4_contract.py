"""Regression tests for the Semantic Training data and acceptance contract."""

import pandas as pd

from ml_training.semantic.src.contract import (
    acceptance_cases,
    canonical_url_key,
    clean_label_conflicts,
    evaluate_acceptance,
)


def test_canonical_key_normalises_host_default_port_and_fragment():
    left = canonical_url_key("HTTPS://PayPal.COM:443/signin#top")
    right = canonical_url_key("https://paypal.com/signin")

    assert left == right


def test_cleaning_removes_cross_source_label_conflicts():
    frame = pd.DataFrame(
        [
            {"url": "HTTPS://PayPal.COM:443/signin", "label": 0, "source": "a"},
            {"url": "https://paypal.com/signin#fragment", "label": 1, "source": "b"},
            {"url": "https://example.com/", "label": 0, "source": "a"},
            {"url": "https://example.com/", "label": 0, "source": "b"},
        ]
    )

    cleaned, report = clean_label_conflicts(frame)

    assert cleaned["url"].tolist() == ["https://example.com/"]
    assert report["conflict_keys"] == 1
    assert report["duplicate_rows"] == 1


def test_acceptance_gate_rejects_all_phishing_predictions():
    cases = acceptance_cases()
    result = evaluate_acceptance([0.99] * len(cases), cases)

    assert result["passed"] is False
    assert result["benign_false_positive_rate"] == 1.0
    assert any("official-brand" in failure for failure in result["failures"])


def test_acceptance_gate_passes_well_separated_predictions():
    cases = acceptance_cases()
    probabilities = [0.05 if case.label == 0 else 0.95 for case in cases]
    result = evaluate_acceptance(probabilities, cases)

    assert result["passed"] is True
    assert result["benign_false_positive_rate"] == 0.0
    assert result["phishing_recall"] == 1.0
