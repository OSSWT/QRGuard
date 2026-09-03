from scripts.diagnose_consumed_structural_holdout import _rank, build_report


def _frame(case_id: str, frame_index: int, score: float, verdict: str) -> dict:
    return {
        "case_id": case_id,
        "ground_truth": "clean",
        "frame_index": frame_index,
        "p_structural_raw": score,
        "verdict": verdict,
        "qr_version": 3 if case_id == "stable" else 10,
        "module_count": 29 if case_id == "stable" else 57,
        "mask_pattern": 0 if case_id == "stable" else 4,
        "version_band": "low_v1_v3" if case_id == "stable" else "high_v7_plus",
        "payload_length_bin": "short_1_32" if case_id == "stable" else "long_97_plus",
        "payload_utf8_bytes": 24 if case_id == "stable" else 97,
        "observed_pixels_per_module": 16.0 if case_id == "stable" else 10.0,
        "raw_mean_luminance": 150.0 + frame_index,
        "raw_p05_luminance": 40.0,
        "raw_p95_luminance": 220.0,
        "raw_dynamic_range": 180.0 - frame_index,
        "raw_laplacian_variance": 500.0 + frame_index,
        "raw_dark_fraction": 0.0,
        "raw_bright_fraction": 0.0,
        "qr_coverage": 0.16,
        "quadrilateral_side_ratio": 1.05,
    }


def test_average_ranks_handle_ties() -> None:
    assert _rank([10.0, 20.0, 20.0, 30.0]) == [1.0, 2.5, 2.5, 4.0]


def test_consumed_diagnosis_separates_frame_instability_from_session_outcome() -> None:
    rows = [
        _frame("stable", 0, 0.01, "safe"),
        _frame("stable", 1, 0.02, "safe"),
        _frame("stable", 2, 0.03, "safe"),
        _frame("variable", 0, 0.10, "safe"),
        _frame("variable", 1, 0.20, "safe"),
        _frame("variable", 2, 0.80, "blocked"),
    ]
    sessions = [
        {"case_id": "stable", "ground_truth": "clean", "median_risk_verdict": "safe"},
        {"case_id": "variable", "ground_truth": "clean", "median_risk_verdict": "safe"},
    ]

    report = build_report(rows, sessions, reference_span_limit=0.15)

    assert report["promotion_eligible"] is False
    assert report["threshold_or_model_mutation_performed"] is False
    assert report["clean_frame_false_blocks"] == 1
    assert report["clean_session_false_blocks"] == 0
    assert report["diagnostic_classification"] == (
        "single_frame_instability_rescued_by_temporal_consensus"
    )
    assert [row["case_id"] for row in report["elevated_clean_layouts"]] == [
        "variable"
    ]
