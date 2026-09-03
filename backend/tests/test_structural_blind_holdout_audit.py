"""Acceptance gates for the post-freeze M8 Structural capture."""

import json
from pathlib import Path

from scripts.audit_structural_blind_holdout import audit_sessions
from scripts.evaluate_live_camera_candidate import CandidateSession

ROOT = Path(__file__).resolve().parents[2]


def _session(case: dict, outcome: str = "correct") -> CandidateSession:
    label = case["ground_truth"]
    attack = label != "clean"
    return CandidateSession(
        session_id=case["case_id"].lower().replace("-", "")[:24],
        case_id=case["case_id"],
        ground_truth=label,
        distance="screen-80",
        repeat_index=1,
        frames_captured=5,
        frames_received=3,
        frames_at_least_256px=3,
        frames_analyzed=3,
        minimum_crop_side=300,
        maximum_crop_side=320,
        consensus="median_score_majority_class",
        quality_status="usable",
        quality_conditions="",
        p_structural_raw=0.01 if not attack else 0.95,
        p_structural_effective=0.01 if not attack else 0.95,
        structural_type=label,
        verdict="safe" if not attack else "blocked",
        outcome=outcome,
        elapsed_ms=100,
    )


def _documents() -> tuple[dict, dict, dict, dict, dict]:
    plan = json.loads(
        (
            ROOT / "app/assets/capture/structural_coverage_blind_holdout_plan.json"
        ).read_text(encoding="utf-8")
    )
    plan["candidate_model_sha256"] = "a" * 64
    config = json.loads(
        (
            ROOT / "ml_training/configs/structural-coverage-gates-2026.09-r01.json"
        ).read_text(encoding="utf-8")
    )
    demo = {"summary": {"gate_passed": True, "masked_branch_errors": 0}}
    digital = {"summary": {"gate_passed": True}}
    survival = {
        "evaluation": "paired_post_capture_adversarial_survival",
        "campaign_id": plan["campaign_id"],
        "rows": [
            {
                "adversarial_case_id": case["case_id"],
                "physical_attack_survival_verified": True,
            }
            for case in plan["cases"]
            if case["ground_truth"] == "adversarial"
        ],
    }
    return plan, config, demo, digital, survival


def test_perfect_blind_matrix_passes_all_stratified_gates() -> None:
    plan, config, demo, digital, survival = _documents()
    sessions = [_session(case) for case in plan["cases"]]

    report = audit_sessions(plan, sessions, config, demo, digital, survival, "a" * 64)

    assert report["gate_passed"] is True
    assert report["gate_failures"] == []
    assert report["production_mutation_performed"] is False


def test_one_low_version_clean_false_block_fails_even_when_aggregate_looks_good() -> (
    None
):
    plan, config, demo, digital, survival = _documents()
    target = next(
        case
        for case in plan["cases"]
        if case["ground_truth"] == "clean"
        and case["metadata"]["version_band"] == "low_v1_v3"
    )
    sessions = [_session(case) for case in plan["cases"]]
    index = next(
        i for i, row in enumerate(sessions) if row.case_id == target["case_id"]
    )
    failed = _session(target, outcome="false_block")
    object.__setattr__(failed, "structural_type", "adversarial")
    object.__setattr__(failed, "verdict", "blocked")
    object.__setattr__(failed, "p_structural_raw", 0.8)
    object.__setattr__(failed, "p_structural_effective", 0.8)
    sessions[index] = failed

    report = audit_sessions(plan, sessions, config, demo, digital, survival, "a" * 64)

    assert report["gate_passed"] is False
    assert any(
        "clean/low_v1_v3: false-Blocked rate" in failure
        for failure in report["gate_failures"]
    )


def test_sem05_masked_branch_error_blocks_blind_promotion() -> None:
    plan, config, demo, digital, survival = _documents()
    demo["summary"] = {"gate_passed": False, "masked_branch_errors": 1}

    report = audit_sessions(
        plan,
        [_session(case) for case in plan["cases"]],
        config,
        demo,
        digital,
        survival,
        "a" * 64,
    )

    assert report["gate_passed"] is False
    assert "SEM-05-style demo branch audit is not clean" in report["gate_failures"]


def test_non_surviving_physical_attacks_cannot_count_toward_recall() -> None:
    plan, config, demo, digital, survival = _documents()
    survival["rows"] = [
        {**row, "physical_attack_survival_verified": False} for row in survival["rows"]
    ]

    report = audit_sessions(
        plan,
        [_session(case) for case in plan["cases"]],
        config,
        demo,
        digital,
        survival,
        "a" * 64,
    )

    assert report["gate_passed"] is False
    assert report["physical_attack_survival"]["verified_surviving_attacks"] == 0
    assert any(
        "verified surviving physical attacks" in failure
        for failure in report["gate_failures"]
    )


def test_consumed_holdout_can_only_be_a_non_promoting_development_replay() -> None:
    plan, config, demo, digital, survival = _documents()

    report = audit_sessions(
        plan,
        [_session(case) for case in plan["cases"]],
        config,
        demo,
        digital,
        survival,
        "a" * 64,
        evidence_role="development_replay",
    )

    assert report["gate_passed"] is True
    assert report["promotion_eligible"] is False
    assert report["promotion_blocked"] is True


def test_blind_plan_must_be_bound_to_the_scored_candidate() -> None:
    plan, config, demo, digital, survival = _documents()

    report = audit_sessions(
        plan,
        [_session(case) for case in plan["cases"]],
        config,
        demo,
        digital,
        survival,
        "b" * 64,
    )

    assert report["gate_passed"] is False
    assert report["candidate_binding_matches"] is False
    assert "blind capture plan is not bound to this candidate model" in report[
        "gate_failures"
    ]


def test_prospective_policy_cannot_reclassify_consumed_campaign() -> None:
    plan, _, demo, digital, survival = _documents()
    plan["campaign_id"] = "structural-r07-fresh-blind-v1"
    survival["campaign_id"] = plan["campaign_id"]
    config = json.loads(
        (
            ROOT / "ml_training/configs/structural-r07-product-acceptance-v1.json"
        ).read_text(encoding="utf-8")
    )

    report = audit_sessions(
        plan,
        [_session(case) for case in plan["cases"]],
        config,
        demo,
        digital,
        survival,
        "a" * 64,
    )

    assert report["gate_passed"] is False
    assert report["release_tier"] == "blocked"
    assert any("consumed before this policy" in row for row in report["gate_failures"])


def test_prospective_policy_makes_clean_score_span_advisory_not_hidden() -> None:
    plan, _, demo, digital, survival = _documents()
    plan["campaign_id"] = "structural-r07-prospective-blind-v1"
    survival["campaign_id"] = plan["campaign_id"]
    config = json.loads(
        (
            ROOT / "ml_training/configs/structural-r07-product-acceptance-v1.json"
        ).read_text(encoding="utf-8")
    )
    sessions = [_session(case) for case in plan["cases"]]
    clean = next(row for row in sessions if row.ground_truth == "clean")
    object.__setattr__(clean, "p_structural_raw", 0.20)

    report = audit_sessions(
        plan, sessions, config, demo, digital, survival, "a" * 64
    )

    assert report["gate_passed"] is True
    assert report["hard_gate_failures"] == []
    assert any("clean layout probability span" in row for row in report["advisories"])
    assert report["release_tier"] == "controlled_pilot_with_documented_limitations"
