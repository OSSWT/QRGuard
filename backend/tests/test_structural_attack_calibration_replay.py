from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "evaluate_structural_attack_calibration.py"
spec = importlib.util.spec_from_file_location("attack_calibration_replay", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _session(case_id: str, label: str, outcome: str, verdict: str, kind: str):
    return module.CandidateSession(
        session_id=case_id.lower().replace("-", "")[:24].ljust(24, "0"),
        case_id=case_id,
        ground_truth=label,
        distance="screen_80",
        repeat_index=1,
        frames_captured=5,
        frames_received=3,
        frames_at_least_256px=3,
        frames_analyzed=3,
        minimum_crop_side=300,
        maximum_crop_side=320,
        consensus="strong",
        quality_status="usable",
        quality_conditions="",
        p_structural_raw=0.1 if label == "clean" else 0.9,
        p_structural_effective=0.1 if label == "clean" else 0.9,
        structural_type=kind,
        verdict=verdict,
        outcome=outcome,
        elapsed_ms=20,
    )


def _fixture():
    cases = []
    sessions = []
    survival_rows = []
    for band_index, band in enumerate(module.BANDS):
        for index in range(5):
            clean_id = f"C-{band_index}-{index}"
            attack_id = f"A-{band_index}-{index}"
            metadata = {
                "version_band": band,
                "base_identity": f"B-{band_index}-{index}",
            }
            cases.extend(
                [
                    {"case_id": clean_id, "ground_truth": "clean", "metadata": metadata},
                    {
                        "case_id": attack_id,
                        "ground_truth": "adversarial",
                        "metadata": metadata,
                    },
                ]
            )
            sessions.extend(
                [
                    _session(clean_id, "clean", "correct", "safe", "clean"),
                    _session(
                        attack_id,
                        "adversarial",
                        "correct",
                        "blocked",
                        "adversarial",
                    ),
                ]
            )
            survival_rows.append(
                {
                    "adversarial_case_id": attack_id,
                    "physical_attack_survival_verified": True,
                }
            )
    plan = {"campaign_id": "calibration", "cases": cases}
    survival = {
        "evaluation": "paired_post_capture_adversarial_survival",
        "campaign_id": "calibration",
        "source_archive_sha256": "capture",
        "rows": survival_rows,
    }
    config = {
        "minimum_verified_surviving_attacks_per_version_band": 5,
        "maximum_clean_camera_false_block_rate_per_version_band": 0.05,
        "minimum_adversarial_camera_block_recall_per_version_band": 0.8,
        "maximum_camera_rescan_rate_per_class_version_band": 0.2,
        "maximum_clean_layout_probability_span": 0.15,
    }
    return plan, sessions, survival, config


def _summarise(plan, sessions, survival, config):
    return module.summarise_development_replay(
        plan=plan,
        sessions=sessions,
        survival=survival,
        config=config,
        candidate={"model_sha256": "candidate"},
        source_archive_sha256="capture",
        survival_report_sha256="survival",
    )


def test_development_replay_passes_but_never_promotes() -> None:
    plan, sessions, survival, config = _fixture()
    report = _summarise(plan, sessions, survival, config)

    assert report["development_gate_passed"] is True
    assert report["promotion_eligible"] is False
    assert report["production_mutation_performed"] is False
    assert report["next_action"] == "retain_candidate_and_build_new_blind_campaign"


def test_non_survivor_is_excluded_from_attack_recall() -> None:
    plan, sessions, survival, config = _fixture()
    attack_case = next(row for row in plan["cases"] if row["ground_truth"] == "adversarial")
    extra_id = "A-extra"
    plan["cases"].append(
        {
            "case_id": extra_id,
            "ground_truth": "adversarial",
            "metadata": attack_case["metadata"],
        }
    )
    survival["rows"].append(
        {
            "adversarial_case_id": extra_id,
            "physical_attack_survival_verified": False,
        }
    )

    report = _summarise(plan, sessions, survival, config)

    assert report["development_gate_passed"] is True
    assert report["selection_contract"]["excluded_non_surviving_attack_cases"] == 1


def test_clean_false_block_fails_functional_gate() -> None:
    plan, sessions, survival, config = _fixture()
    clean_index = next(i for i, row in enumerate(sessions) if row.ground_truth == "clean")
    sessions[clean_index] = replace(
        sessions[clean_index], outcome="false_block", verdict="blocked", structural_type="tampered"
    )

    report = _summarise(plan, sessions, survival, config)

    assert report["functional_gate_passed"] is False
    assert any("false-Blocked rate" in value for value in report["functional_failures"])


def test_attack_variants_share_one_conservative_independent_group() -> None:
    plan, sessions, survival, config = _fixture()
    source_case = next(row for row in plan["cases"] if row["case_id"] == "A-2-0")
    variant_id = "A-2-0-variant"
    plan["cases"].append(
        {
            "case_id": variant_id,
            "ground_truth": "adversarial",
            "metadata": source_case["metadata"],
        }
    )
    sessions.append(
        _session(variant_id, "adversarial", "rescan", "warning", "abstained")
    )
    survival["rows"].append(
        {
            "adversarial_case_id": variant_id,
            "physical_attack_survival_verified": True,
        }
    )

    report = _summarise(plan, sessions, survival, config)
    high = report["performance_by_class_version_band"]["adversarial"][
        "high_v7_plus"
    ]

    assert report["development_gate_passed"] is True
    assert high["independent_base_identities"] == 5
    assert high["attack_case_sessions"] == 6
    assert high["rescans"] == 1
    assert high["block_recall"] == 0.8
