"""Fast tests for the rebuilt ML/fusion data contracts."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.build_qrguard_mix import _payload, _target, make_qr
from scripts.train_fusion import (
    apply_runtime_policy,
    configure_candidate,
    fit_constrained,
    tune_thresholds,
)


def test_mix_v2_models_open_wifi_as_warning_not_fraud():
    risk_target, tier, dangerous = _target("clean", "wifi_open")

    assert risk_target == 0.40
    assert tier == "warning"
    assert dangerous == 0


def test_mix_v2_image_manipulation_always_targets_blocked():
    for image_class in ("tampered", "adversarial"):
        for payload_kind in ("benign_url", "wifi_open", "wifi_secure", "plain_text"):
            risk_target, tier, dangerous = _target(image_class, payload_kind)
            assert risk_target == 0.98
            assert tier == "blocked"
            assert dangerous == 1


def test_mix_v2_camera_evidence_modes_have_expected_targets():
    assert _target("camera_clean_consensus", "wifi_open") == (0.40, "warning", 0)
    assert _target("camera_uncertain_abstain", "wifi_secure") == (0.02, "safe", 0)
    assert _target("camera_tampered_consensus", "plain_text") == (0.98, "blocked", 1)


def test_non_url_payload_families_are_generated():
    benign = ["https://example.com/"]
    phishing = ["http://account-check.test/login"]

    assert _payload("wifi_open", 0, benign, phishing).startswith("WIFI:T:nopass")
    assert _payload("wifi_secure", 0, benign, phishing).startswith("WIFI:T:WPA")
    assert _payload("plain_text", 0, benign, phishing).startswith("QRGuard non-URL")
    assert _payload("executable_uri", 0, benign, phishing).startswith("javascript:")


def test_qr_generation_seed_is_stable_within_process():
    first = np.asarray(make_qr("WIFI:T:nopass;S:Stable;;"))
    second = np.asarray(make_qr("WIFI:T:nopass;S:Stable;;"))

    assert np.array_equal(first, second)


def test_constrained_fusion_fit_supports_fractional_warning_targets():
    features = np.asarray([[0.0], [1.0], [2.0]], dtype=float)
    targets = np.asarray([0.02, 0.40, 0.98], dtype=float)
    labels = np.asarray([0, 0, 1], dtype=int)

    coefficient, intercept = fit_constrained(
        features,
        targets,
        class_weight=False,
        bounds=[(0.0, None)],
        class_labels=labels,
    )
    probabilities = 1 / (1 + np.exp(-(features[:, 0] * coefficient[0] + intercept)))

    assert coefficient[0] >= 0
    assert probabilities[0] < probabilities[1] < probabilities[2]


def test_fusion_evaluation_applies_open_wifi_policy_floor():
    rows = pd.DataFrame(
        [
            {
                "rule_flags": "open_wifi_network",
                "evidence_mode": "camera_clean_consensus",
                "p_url": np.nan,
                "domain_unknown": np.nan,
            }
        ]
    )
    adjusted, tiers = apply_runtime_policy(
        np.asarray([3]), rows, safe_max=30, blocked_min=55
    )

    assert adjusted.tolist() == [30]
    assert tiers.tolist() == ["warning"]


def test_fusion_evaluation_mirrors_uncertain_camera_fail_closed_policy():
    rows = pd.DataFrame(
        [
            {
                "rule_flags": "",
                "evidence_mode": "camera_uncertain_abstain",
                "p_url": 0.02,
                "domain_unknown": 1.0,
            },
            {
                "rule_flags": "",
                "evidence_mode": "camera_uncertain_abstain",
                "p_url": 0.02,
                "domain_unknown": 0.0,
            },
        ]
    )
    adjusted, tiers = apply_runtime_policy(
        np.asarray([4, 4]), rows, safe_max=30, blocked_min=55
    )

    assert adjusted.tolist() == [30, 4]
    assert tiers.tolist() == ["warning", "safe"]


def test_uncertain_camera_moderate_semantic_score_cannot_hard_block():
    rows = pd.DataFrame(
        [
            {
                "rule_flags": "non_https",
                "evidence_mode": "camera_uncertain_abstain",
                "p_url": 0.69,
                "domain_unknown": 1.0,
            },
            {
                "rule_flags": "non_https",
                "evidence_mode": "camera_uncertain_abstain",
                "p_url": 0.91,
                "domain_unknown": 1.0,
            },
        ]
    )
    adjusted, tiers = apply_runtime_policy(
        np.asarray([79, 20]), rows, safe_max=45, blocked_min=55
    )

    assert adjusted.tolist() == [54, 55]
    assert tiers.tolist() == ["warning", "blocked"]


def test_threshold_tuning_enforces_open_wifi_cell_gate_on_training_rows():
    probabilities = np.asarray([0.05] * 20 + [0.58] * 5 + [0.90] * 100)
    labels = np.asarray([0] * 25 + [1] * 100)
    rows = pd.DataFrame(
        [
            {
                "cell": "gallery_clean_benign_url",
                "payload_kind": "benign_url",
                "evidence_mode": "gallery_clean",
                "target_tier": "safe",
                "rule_flags": "",
                "p_structural": 0.01,
                "p_url": 0.01,
                "domain_unknown": 0.0,
            }
        ]
        * 20
        + [
            {
                "cell": "gallery_clean_wifi_open",
                "payload_kind": "wifi_open",
                "evidence_mode": "gallery_clean",
                "target_tier": "warning",
                "rule_flags": "open_wifi_network",
                "p_structural": 0.2,
                "p_url": np.nan,
                "domain_unknown": np.nan,
            }
        ]
        * 5
        + [
            {
                "cell": "gallery_tampered_benign_url",
                "payload_kind": "benign_url",
                "evidence_mode": "gallery_tampered",
                "target_tier": "blocked",
                "rule_flags": "",
                "p_structural": 0.99,
                "p_url": 0.01,
                "domain_unknown": 0.0,
            }
        ]
        * 100
    )

    _, blocked_min = tune_thresholds(probabilities, labels, rows)

    assert blocked_min > 58


def test_decision_candidate_version_cannot_escape_its_run_folder():
    with pytest.raises(ValueError, match="invalid decision candidate version"):
        configure_candidate(Path("candidate"), "../deploy")
