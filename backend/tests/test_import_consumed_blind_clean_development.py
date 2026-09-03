from scripts.analyze_live_camera_diagnostic import ValidatedFrame
from scripts.import_consumed_blind_clean_development import (
    _validate_development_rows,
    development_row,
)


def _frame(case_id: str, frame_index: int) -> ValidatedFrame:
    return ValidatedFrame(
        session_id=(case_id.replace("-", "").lower() + "0" * 24)[:24],
        case_id=case_id,
        ground_truth="clean",
        distance="screen-80",
        repeat_index=1,
        frame_index=frame_index,
        crop_name=f"{case_id}/crop_{frame_index:02d}.png",
        crop_sha256=f"{frame_index:02x}" * 32,
        crop_png=b"png",
        crop_width=300,
        crop_height=300,
        frame_width=960,
        frame_height=1280,
        corner_coordinates=(0, 0, 1, 0, 1, 1, 0, 1),
        qr_coverage=0.1,
        payload_sha256="b" * 64,
    )


def _plan_case(base_number: int) -> dict:
    if base_number <= 5:
        version, modules, band, payload_bytes = 3, 29, "low_v1_v3", 24
    elif base_number <= 10:
        version, modules, band, payload_bytes = 6, 41, "medium_v4_v6", 48
    else:
        version, modules, band, payload_bytes = 12, 65, "high_v7_plus", 132
    return {
        "metadata": {
            "base_identity": f"BLIND-BASE-{base_number:02d}",
            "qr_version": version,
            "module_count": modules,
            "mask_pattern": base_number % 8,
            "version_band": band,
            "payload_length_bin": (
                "short_1_32"
                if payload_bytes <= 32
                else "medium_33_96"
                if payload_bytes <= 96
                else "long_97_plus"
            ),
            "payload_utf8_bytes": payload_bytes,
            "qr_matrix_sha256": "c" * 64,
        }
    }


def test_consumed_blind_clean_rows_are_group_disjoint_and_non_promoting() -> None:
    rows = []
    for base_number in range(1, 17):
        case_id = f"BLD-CLEAN-{base_number:02d}"
        plan_case = _plan_case(base_number)
        for frame_index in range(5):
            rows.append(
                development_row(
                    _frame(case_id, frame_index),
                    plan_case,
                    f"data/example/{case_id}/crop_{frame_index:02d}.png",
                )
            )

    _validate_development_rows(rows)

    assert sum(row["split"] == "train" for row in rows) == 60
    assert sum(row["split"] == "validation" for row in rows) == 20
    assert {row["label"] for row in rows} == {"clean"}
    assert all(row["blind_holdout_consumed"] is True for row in rows)
    assert all(row["deployment_holdout_eligible"] is False for row in rows)
    assert all(row["promotion_eligible"] is False for row in rows)


def test_consumed_blind_import_rejects_attack_rows() -> None:
    frame = _frame("BLD-ATTACK", 0)
    object.__setattr__(frame, "ground_truth", "adversarial")

    try:
        development_row(frame, _plan_case(1), "data/example.png")
    except ValueError as error:
        assert "only clean M8 frames" in str(error)
    else:
        raise AssertionError("attack data must not enter the clean hard-negative set")
