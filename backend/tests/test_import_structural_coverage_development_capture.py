from scripts.analyze_live_camera_diagnostic import ValidatedFrame
from scripts.import_structural_coverage_development_capture import (
    _validate_development_rows,
    development_row,
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
        crop_width=280,
        crop_height=280,
        frame_width=960,
        frame_height=1280,
        corner_coordinates=(0, 0, 1, 0, 1, 1, 0, 1),
        qr_coverage=0.1,
        payload_sha256="b" * 64,
    )


def _plan_case(base_id: str, split: str, mask: int) -> dict:
    return {
        "metadata": {
            "base_identity": base_id,
            "development_split": split,
            "deployment_holdout_eligible": False,
            "qr_version": 3,
            "module_count": 29,
            "mask_pattern": mask,
            "version_band": "low_v1_v3",
            "payload_length_bin": "short_1_32",
            "payload_utf8_bytes": 24,
            "qr_matrix_sha256": "c" * 64,
        }
    }


def test_development_row_keeps_base_group_and_never_becomes_holdout() -> None:
    row = development_row(
        _frame("CVG-ADV-V03-M0-01", "adversarial"),
        _plan_case("CVG-BASE-01", "train", 0),
        {
            "attack_method": "eot_pgd_qr_function_projection",
            "manipulation_method": "none",
        },
        "data/example.png",
    )

    assert row["split"] == "train"
    assert row["group_id"] == "coverage_dev_2026_09:CVG-BASE-01"
    assert row["paired_group"] == "coverage_dev_2026_09:CVG-ADV-V03-M0-01"
    assert row["attack_recipe"] == "eot_pgd_qr_function_projection"
    assert row["deployment_holdout_eligible"] is False
    assert row["is_exact_app_crop"] is True


def test_development_row_validation_rejects_incomplete_capture() -> None:
    row = development_row(
        _frame("CVG-CLN-V03-M0-01", "clean"),
        _plan_case("CVG-BASE-01", "train", 0),
        {"attack_method": "none", "manipulation_method": "none"},
        "data/example.png",
    )

    try:
        _validate_development_rows([row])
    except ValueError as error:
        assert "expected 240 M5 frames" in str(error)
    else:
        raise AssertionError("incomplete M5 capture should be rejected")
