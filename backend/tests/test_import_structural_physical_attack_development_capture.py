import pytest

from scripts.analyze_live_camera_diagnostic import ValidatedFrame
from scripts.import_structural_physical_attack_development_capture import (
    development_row,
    verified_attack_cases,
)


def _frame(case_id: str, label: str, frame_index: int = 0) -> ValidatedFrame:
    return ValidatedFrame(
        session_id="a" * 24,
        case_id=case_id,
        ground_truth=label,
        distance="screen-80",
        repeat_index=1,
        frame_index=frame_index,
        crop_name=f"{case_id}/crop_{frame_index:02d}.png",
        crop_sha256=f"{frame_index:064x}",
        crop_png=b"png",
        crop_width=320,
        crop_height=320,
        frame_width=960,
        frame_height=1280,
        corner_coordinates=(0, 0, 1, 0, 1, 1, 0, 1),
        qr_coverage=0.1,
        payload_sha256="b" * 64,
    )


def _plan_case(base_id: str, split: str) -> dict:
    return {
        "metadata": {
            "base_identity": base_id,
            "development_split": split,
            "deployment_holdout_eligible": False,
            "qr_version": 4,
            "module_count": 33,
            "mask_pattern": 2,
            "version_band": "medium_v4_v6",
            "payload_length_bin": "medium_33_96",
            "payload_utf8_bytes": 40,
            "qr_matrix_sha256": "c" * 64,
        }
    }


def test_survival_report_selects_only_explicitly_verified_attacks() -> None:
    rows = [
        {
            "adversarial_case_id": f"PHY-ADV-X-{index:02d}",
            "physical_attack_survival_verified": index <= 10,
        }
        for index in range(1, 33)
    ]
    report = {
        "campaign_id": "structural-physical-attack-development-2026-09-r02",
        "source_archive_sha256": "d" * 64,
        "adversarial_pairs": 32,
        "verified_surviving_attacks": 10,
        "rows": rows,
    }

    selected = verified_attack_cases(report, "d" * 64)

    assert selected == {f"PHY-ADV-X-{index:02d}" for index in range(1, 11)}


def test_survival_report_cannot_be_reused_for_another_archive() -> None:
    report = {
        "campaign_id": "structural-physical-attack-development-2026-09-r02",
        "source_archive_sha256": "d" * 64,
        "adversarial_pairs": 32,
        "verified_surviving_attacks": 10,
        "rows": [
            {
                "adversarial_case_id": f"PHY-ADV-X-{index:02d}",
                "physical_attack_survival_verified": index <= 10,
            }
            for index in range(1, 33)
        ],
    }

    with pytest.raises(ValueError, match="does not match"):
        verified_attack_cases(report, "e" * 64)


def test_physical_development_row_records_survival_and_parent_group() -> None:
    row = development_row(
        _frame("PHY-ADV-X-06", "adversarial"),
        _plan_case("PHY-R02-BASE-06", "train"),
        {"attack_method": "eot_pgd_qr_function_projection"},
        "data/example.png",
        True,
    )

    assert row["group_id"] == "physical_attack_dev_2026_09:PHY-R02-BASE-06"
    assert row["paired_group"] == "physical_attack_dev_2026_09:PHY-ADV-X-06"
    assert row["physical_attack_survival_verified"] is True
    assert row["deployment_holdout_eligible"] is False


def test_attack_row_never_infers_survival_from_the_adversarial_label() -> None:
    row = development_row(
        _frame("PHY-ADV-X-06", "adversarial"),
        _plan_case("PHY-R02-BASE-06", "train"),
        {"attack_method": "eot_pgd_qr_function_projection"},
        "data/example.png",
        False,
    )

    assert row["label"] == "adversarial"
    assert row["physical_attack_survival_verified"] is False
