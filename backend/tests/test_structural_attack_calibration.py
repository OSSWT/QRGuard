from collections import Counter

import pytest

from scripts.audit_physical_adversarial_survival import summarise_survival
from scripts.build_structural_attack_calibration_pack import (
    calibration_base_specs,
    calibration_case_specs,
)
from scripts.build_structural_coverage_development_pack import (
    _screen_camera_eot_views,
)


def test_calibration_pack_balances_version_bands_masks_and_attack_profiles() -> None:
    bases = calibration_base_specs()
    cases = calibration_case_specs()

    assert len(bases) == 24
    assert len(cases) == 72
    assert Counter(base.version_band for base in bases) == {
        "low_v1_v3": 8,
        "medium_v4_v6": 8,
        "high_v7_plus": 8,
    }
    assert Counter(base.mask_pattern for base in bases) == {
        mask: 3 for mask in range(8)
    }
    assert Counter(case.label for case in cases) == {
        "clean": 24,
        "adversarial": 48,
    }
    assert {
        case.attack_profile for case in cases if case.label == "adversarial"
    } == {
        "screen_camera_robust_v2_function",
        "screen_camera_robust_v2_alternate",
    }


def test_screen_camera_eot_suite_has_twelve_deterministic_views() -> None:
    torch = pytest.importorskip("torch")
    source = torch.full((1, 3, 224, 224), 0.5)

    first = _screen_camera_eot_views(source)
    second = _screen_camera_eot_views(source)

    assert first.shape == (12, 3, 224, 224)
    assert torch.equal(first, second)


def test_physical_survival_gate_is_stratified_and_planning_is_explicit() -> None:
    rows = []
    for band, verified in (
        ("low_v1_v3", 5),
        ("medium_v4_v6", 4),
        ("high_v7_plus", 5),
    ):
        for index in range(8):
            rows.append(
                {
                    "version_band": band,
                    "attack_profile": "screen_camera_robust_v2_function",
                    "physical_attack_survival_verified": index < verified,
                }
            )

    report = summarise_survival(rows, minimum_survivors_per_band=5)

    assert report["gate_passed"] is False
    assert report["by_version_band"]["low_v1_v3"]["gate_passed"] is True
    assert report["by_version_band"]["medium_v4_v6"]["gate_passed"] is False
    assert (
        report["by_version_band"]["medium_v4_v6"]
        ["planned_attacks_for_target_using_observed_rate"]
        >= 5
    )
