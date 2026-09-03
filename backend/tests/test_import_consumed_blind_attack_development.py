from scripts.analyze_live_camera_diagnostic import ValidatedFrame
from scripts.import_consumed_blind_attack_development import (
    _validate_rows,
    development_row,
)


def _frame(case_id: str, frame_index: int) -> ValidatedFrame:
    return ValidatedFrame(
        session_id=(case_id.replace("-", "").lower() + "0" * 24)[:24],
        case_id=case_id,
        ground_truth="adversarial",
        distance="screen-80",
        repeat_index=1,
        frame_index=frame_index,
        crop_name=f"{case_id}/crop_{frame_index:02d}.png",
        crop_sha256=(f"{frame_index:02x}" + case_id[-2:].lower()) * 16,
        crop_png=b"png",
        crop_width=300,
        crop_height=300,
        frame_width=960,
        frame_height=1280,
        corner_coordinates=(0, 0, 1, 0, 1, 1, 0, 1),
        qr_coverage=0.1,
        payload_sha256="b" * 64,
    )


def _plan_case(base_id: str) -> dict:
    high = base_id == "BLIND-BASE-12"
    return {
        "metadata": {
            "base_identity": base_id,
            "attack_method": "eot_fgsm_qr_function_projection",
            "qr_version": 12 if high else 3,
            "module_count": 65 if high else 29,
            "mask_pattern": 4 if high else 7,
            "version_band": "high_v7_plus" if high else "low_v1_v3",
            "payload_length_bin": "long_97_plus" if high else "short_1_32",
            "payload_utf8_bytes": 132 if high else 24,
            "qr_matrix_sha256": "c" * 64,
        }
    }


def test_only_verified_surviving_attacks_are_non_promoting_train_rows() -> None:
    rows = []
    cases = (
        ("BLD-27-90C833", "BLIND-BASE-12"),
        ("BLD-39-5285E9", "BLIND-BASE-01"),
    )
    for case_id, base_id in cases:
        survival = {
            "physical_attack_survival_verified": True,
            "base_identity": base_id,
        }
        for frame_index in range(5):
            rows.append(
                development_row(
                    _frame(case_id, frame_index),
                    _plan_case(base_id),
                    survival,
                    f"data/example/{case_id}/crop_{frame_index:02d}.png",
                )
            )

    _validate_rows(rows)

    assert {row["label"] for row in rows} == {"adversarial"}
    assert {row["split"] for row in rows} == {"train"}
    assert all(row["physical_attack_survival_verified"] is True for row in rows)
    assert all(row["development_only"] is True for row in rows)
    assert all(row["promotion_eligible"] is False for row in rows)


def test_unverified_attack_is_rejected() -> None:
    try:
        development_row(
            _frame("BLD-27-90C833", 0),
            _plan_case("BLIND-BASE-12"),
            {
                "physical_attack_survival_verified": False,
                "base_identity": "BLIND-BASE-12",
            },
            "data/example.png",
        )
    except ValueError as error:
        assert "verified physical survival" in str(error)
    else:
        raise AssertionError("unverified attacks must remain quarantined")
