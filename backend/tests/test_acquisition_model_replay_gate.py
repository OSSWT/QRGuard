from scripts.evaluate_acquisition_model_replay import build_evaluation


def _frame(
    case_id: str,
    ground_truth: str,
    condition: str,
    *,
    structural_type: str,
    probability: float,
    verdict: str,
    decoded: bool = False,
    semantic_status: str = "not_applicable",
) -> dict[str, str]:
    return {
        "case_id": case_id,
        "ground_truth": ground_truth,
        "distance": condition,
        "structural_type": structural_type,
        "p_structural_effective": str(probability),
        "verdict": verdict,
        "payload_hash_matches": str(decoded),
        "semantic_status": semantic_status,
    }


def _session(
    case_id: str, ground_truth: str, condition: str, verdict: str, probability: float
) -> dict[str, str]:
    return {
        "case_id": case_id,
        "ground_truth": ground_truth,
        "distance": condition,
        "majority_verdict": verdict,
        "median_p_structural": str(probability),
    }


def test_gate_keeps_semantic_and_structural_correctness_separate() -> None:
    conditions = ["normal", "dark"]
    plan = {
        "distances": [{"id": value} for value in conditions],
        "cases": [
            {
                "case_id": "SEM-05-USERINFO",
                "ground_truth": "clean",
                "metadata": {"intended_app_verdict": "BLOCKED"},
            },
            {"case_id": "SEM-11-PLAIN-TEXT", "ground_truth": "clean"},
            {"case_id": "ATTACK", "ground_truth": "adversarial"},
        ],
    }
    frames = [
        _frame(
            "SEM-05-USERINFO",
            "clean",
            condition,
            structural_type="clean" if condition == "normal" else "adversarial",
            probability=0.1 if condition == "normal" else 0.8,
            verdict="blocked",
            decoded=True,
            semantic_status="completed",
        )
        for condition in conditions
    ]
    frames.extend(
        _frame(
            "SEM-11-PLAIN-TEXT",
            "clean",
            condition,
            structural_type="clean",
            probability=0.1,
            verdict="safe",
        )
        for condition in conditions
    )
    frames.extend(
        _frame(
            "ATTACK",
            "adversarial",
            condition,
            structural_type="adversarial",
            probability=0.9,
            verdict="blocked",
        )
        for condition in conditions
    )
    sessions = [
        _session(case_id, truth, condition, verdict, probability)
        for case_id, truth, verdict, probability in (
            ("SEM-05-USERINFO", "clean", "blocked", 0.1),
            ("SEM-11-PLAIN-TEXT", "clean", "safe", 0.1),
            ("ATTACK", "adversarial", "blocked", 0.9),
        )
        for condition in conditions
    ]
    report = build_evaluation(
        acquisition={
            "acquisition_gate_passed": True,
            "source": {"sha256": "archive"},
            "telemetry": {
                "minimum_observed_pixels_per_module": 6.0,
                "structural_quality_statuses": {"usable": 6},
            },
        },
        replay={
            "source": {"sha256": "archive"},
            "model": {"version": "r01", "artifact_sha256": "model"},
        },
        plan=plan,
        config={
            "runtime_policy": {"camera_definitive_manipulation_floor": 0.7},
            "deployment_gates": {
                "real_clean_false_positive_rate_max": 0.05,
                "real_adversarial_recall_min": 0.8,
                "real_tampered_recall_min": 0.8,
                "exposure_verdict_agreement_min": 0.95,
                "clean_exposure_probability_span_p95_max": 0.15,
                "sem05_style_masked_branch_errors_max": 0,
            },
        },
        frames=frames,
        sessions=sessions,
    )

    assert report["final_verdict"]["frame_intended_accuracy"] == 1.0
    assert report["structural"]["clean_false_positive_frames"] == 1
    assert report["sentinels"]["sem05"]["semantic_misses_on_payload_matched_frames"] == 0
    assert report["sentinels"]["sem05"]["masked_structural_branch_errors"] == 1
    assert report["gates"]["sem05_style_masked_branch_errors"] is False


def test_warning_is_reported_as_inexact_but_safety_preserving() -> None:
    conditions = ["normal", "dark"]
    plan = {
        "distances": [{"id": value} for value in conditions],
        "cases": [
            {
                "case_id": "SEM-05-USERINFO",
                "ground_truth": "clean",
                "metadata": {"intended_app_verdict": "BLOCKED"},
            }
        ],
    }
    frames = [
        _frame(
            "SEM-05-USERINFO",
            "clean",
            "normal",
            structural_type="clean",
            probability=0.1,
            verdict="blocked",
            decoded=True,
            semantic_status="completed",
        ),
        _frame(
            "SEM-05-USERINFO",
            "clean",
            "dark",
            structural_type="clean",
            probability=0.1,
            verdict="warning",
        ),
    ]
    sessions = [
        _session("SEM-05-USERINFO", "clean", "normal", "blocked", 0.1),
        _session("SEM-05-USERINFO", "clean", "dark", "warning", 0.1),
    ]
    report = build_evaluation(
        acquisition={
            "acquisition_gate_passed": True,
            "source": {"sha256": "archive"},
            "telemetry": {
                "minimum_observed_pixels_per_module": 6.0,
                "structural_quality_statuses": {"usable": 2},
            },
        },
        replay={
            "source": {"sha256": "archive"},
            "model": {"version": "r07", "artifact_sha256": "model"},
        },
        plan=plan,
        config={
            "runtime_policy": {"camera_definitive_manipulation_floor": 0.7},
            "deployment_gates": {
                "real_clean_false_positive_rate_max": 0.05,
                "real_adversarial_recall_min": 0.8,
                "real_tampered_recall_min": 0.8,
                "exposure_verdict_agreement_min": 0.95,
                "clean_exposure_probability_span_p95_max": 0.15,
                "sem05_style_masked_branch_errors_max": 0,
            },
        },
        frames=frames,
        sessions=sessions,
    )

    assert report["exposure"]["verdict_agreement_rate"] == 0.0
    assert report["exposure"]["safety_preservation_rate"] == 1.0
    assert report["gates"]["exposure_safety_preservation"] is True
