"""Evaluate and gate the fresh M8 physical Structural blind holdout.

This script is deliberately separate from training. It validates the complete
collector archive, replays the frozen candidate with the production three-frame
camera contract, and gates every class across Version, mask and payload bins.
It writes evidence only and never promotes or copies runtime artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_live_camera_diagnostic import validate_archive
from scripts.evaluate_live_camera_candidate import (
    CandidateSession,
    _evaluate,
    _markdown,
    _summary,
)

DEFAULT_PLAN = ROOT / "app/assets/capture/structural_r07_fresh_blind_plan.json"
DEFAULT_ARTIFACTS = (
    ROOT / "ml_training/structural/runs/structural-r07-corrective-v1/artifacts"
)
DEFAULT_CONFIG = ROOT / "ml_training/configs/structural-coverage-gates-2026.09-r01.json"
DEFAULT_DEMO_AUDIT = (
    ROOT / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r01/M7_POLICY_GATES/"
    "DEMO_BRANCH_AUDIT.json"
)
DEFAULT_DIGITAL_SEM11 = (
    ROOT / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r01/M7_POLICY_GATES/"
    "SEM11_DIGITAL_CANDIDATE.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r02/R07_FRESH_BLIND_HOLDOUT"
)
REQUIRED_CLASSES = ("clean", "adversarial", "tampered")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return document


def audit_sessions(
    plan: dict[str, Any],
    sessions: list[CandidateSession],
    config: dict[str, Any],
    demo_audit: dict[str, Any],
    digital_sem11: dict[str, Any],
    attack_survival: dict[str, Any],
    candidate_model_sha256: str,
    evidence_role: str = "blind_holdout",
) -> dict[str, Any]:
    """Apply the frozen coverage contract to already replayed session records."""

    failures: list[str] = []
    advisories: list[str] = []
    is_blind = evidence_role == "blind_holdout"
    cases = {str(row["case_id"]): row for row in plan.get("cases", [])}
    session_by_case = {row.case_id: row for row in sessions}
    required_case_count = config.get("required_case_count", 48)
    case_count_invalid = (
        isinstance(required_case_count, int) and len(cases) != required_case_count
    )
    if (
        case_count_invalid
        or len(session_by_case) != len(cases)
        or set(cases) != set(session_by_case)
    ):
        expected = (
            f"all {required_case_count} cases"
            if isinstance(required_case_count, int)
            else "every planned case"
        )
        failures.append(f"blind archive must contain exactly one session for {expected}")
    if not str(plan.get("campaign_id", "")).strip():
        failures.append("blind campaign identity is missing")
    if (
        plan.get("distances", [{}])[0].get("metadata", {}).get("role")
        != "blind_holdout"
    ):
        failures.append("capture plan is not marked blind_holdout")
    if any(
        case.get("metadata", {}).get("deployment_holdout_eligible") is not True
        for case in cases.values()
    ):
        failures.append("all blind cases must be deployment_holdout_eligible")
    if any(
        "generator_assigned_after_candidate_freeze"
        not in str(case.get("metadata", {}).get("case_identity_source", ""))
        for case in cases.values()
    ):
        failures.append(
            "blind cases were not generator-assigned after candidate freeze"
        )
    recorded_candidate_sha256 = str(plan.get("candidate_model_sha256", ""))
    if is_blind and recorded_candidate_sha256 != candidate_model_sha256:
        failures.append("blind capture plan is not bound to this candidate model")
    ineligible_campaigns = {
        str(value) for value in config.get("consumed_campaign_ids_not_eligible", [])
    }
    if is_blind and str(plan.get("campaign_id")) in ineligible_campaigns:
        failures.append(
            "campaign was consumed before this policy was frozen and is not eligible"
        )

    minimum_band = int(config["minimum_independent_test_groups_per_class_version_band"])
    minimum_mask = int(config["minimum_independent_test_groups_per_class_mask"])
    minimum_length = int(
        config["minimum_independent_test_groups_per_class_payload_length_bin"]
    )
    maximum_fbr = float(
        config["maximum_clean_camera_false_block_rate_per_version_band"]
    )
    minimum_recall = {
        "adversarial": float(
            config["minimum_adversarial_camera_block_recall_per_version_band"]
        ),
        "tampered": float(
            config["minimum_tampered_camera_block_recall_per_version_band"]
        ),
    }
    maximum_rescan = float(config["maximum_camera_rescan_rate_per_class_version_band"])
    minimum_surviving_attacks = int(
        config["minimum_verified_surviving_attacks_per_version_band"]
    )

    survival_rows = {
        str(row["adversarial_case_id"]): row for row in attack_survival.get("rows", [])
    }
    planned_adversarial = {
        case_id
        for case_id, case in cases.items()
        if case.get("ground_truth") == "adversarial"
    }
    if attack_survival.get("evaluation") != "paired_post_capture_adversarial_survival":
        failures.append("post-capture adversarial survival evidence is missing")
    if attack_survival.get("campaign_id") != plan.get("campaign_id"):
        failures.append("adversarial survival campaign does not match capture plan")
    if set(survival_rows) != planned_adversarial:
        failures.append(
            "adversarial survival evidence does not cover all planned attacks"
        )
    verified_adversarial = {
        case_id
        for case_id, row in survival_rows.items()
        if row.get("physical_attack_survival_verified") is True
    }

    coverage: dict[str, Any] = {}
    performance: dict[str, Any] = {}
    for label in REQUIRED_CLASSES:
        label_cases = [
            case for case in cases.values() if case.get("ground_truth") == label
        ]
        bands = Counter(case["metadata"]["version_band"] for case in label_cases)
        masks = Counter(int(case["metadata"]["mask_pattern"]) for case in label_cases)
        lengths = Counter(
            case["metadata"]["payload_length_bin"] for case in label_cases
        )
        coverage[label] = {
            "independent_cases": len(label_cases),
            "version_bands": dict(bands),
            "masks": dict(sorted(masks.items())),
            "payload_length_bins": dict(lengths),
        }
        for definition in config["version_bands"]:
            band = definition["id"]
            if bands[band] < minimum_band:
                failures.append(
                    f"{label}/{band}: {bands[band]} cases; require {minimum_band}"
                )
        for mask in range(8):
            if masks[mask] < minimum_mask:
                failures.append(
                    f"{label}/mask-{mask}: {masks[mask]} cases; require {minimum_mask}"
                )
        for definition in config["payload_length_bins"]:
            length_bin = definition["id"]
            if lengths[length_bin] < minimum_length:
                failures.append(
                    f"{label}/{length_bin}: {lengths[length_bin]} cases; "
                    f"require {minimum_length}"
                )

        performance[label] = {}
        for definition in config["version_bands"]:
            band = definition["id"]
            eligible_cases = [
                case
                for case in label_cases
                if label != "adversarial" or case["case_id"] in verified_adversarial
            ]
            selected = [
                session_by_case[case["case_id"]]
                for case in eligible_cases
                if case["case_id"] in session_by_case
                and case["metadata"]["version_band"] == band
            ]
            count = len(selected)
            if label == "adversarial" and count < minimum_surviving_attacks:
                failures.append(
                    f"adversarial/{band}: {count} verified surviving physical "
                    f"attacks; require {minimum_surviving_attacks}"
                )
            rescans = sum(row.outcome == "rescan" for row in selected)
            rescan_rate = rescans / count if count else 1.0
            row: dict[str, Any] = {
                "sessions": count,
                "rescans": rescans,
                "rescan_rate": rescan_rate,
            }
            if rescan_rate > maximum_rescan:
                failures.append(
                    f"{label}/{band}: rescan rate {rescan_rate:.4f} exceeds "
                    f"{maximum_rescan:.4f}"
                )
            if label == "clean":
                false_blocks = sum(row.outcome == "false_block" for row in selected)
                rate = false_blocks / count if count else 1.0
                row.update({"false_blocks": false_blocks, "false_block_rate": rate})
                if rate > maximum_fbr:
                    failures.append(
                        f"clean/{band}: false-Blocked rate {rate:.4f} exceeds "
                        f"{maximum_fbr:.4f}"
                    )
            else:
                blocked = sum(
                    row.verdict == "blocked"
                    and row.structural_type in {"adversarial", "tampered"}
                    for row in selected
                )
                recall = blocked / count if count else 0.0
                row.update({"blocked": blocked, "block_recall": recall})
                if recall < minimum_recall[label]:
                    failures.append(
                        f"{label}/{band}: block recall {recall:.4f} below "
                        f"{minimum_recall[label]:.4f}"
                    )
            performance[label][band] = row

    clean_scores = sorted(
        row.p_structural_raw
        for row in sessions
        if row.ground_truth == "clean" and row.p_structural_raw is not None
    )
    layout_span = max(clean_scores) - min(clean_scores) if clean_scores else 1.0
    maximum_span = float(config["maximum_clean_layout_probability_span"])
    if layout_span > maximum_span:
        message = (
            f"clean layout probability span {layout_span:.4f} exceeds {maximum_span:.4f}"
        )
        if config.get("clean_layout_probability_span_enforcement", "hard") == "advisory":
            advisories.append(message)
        else:
            failures.append(message)

    demo_summary = demo_audit.get("summary", {})
    masked_errors = int(demo_summary.get("masked_branch_errors", -1))
    maximum_masked = int(config["maximum_masked_demo_branch_errors"])
    if demo_summary.get("gate_passed") is not True or masked_errors > maximum_masked:
        failures.append("SEM-05-style demo branch audit is not clean")
    digital_summary = digital_sem11.get("summary", {})
    if digital_summary.get("gate_passed") is not True:
        failures.append("digital SEM-11 contract gate is not clean")

    band_survival = {
        definition["id"]: sum(
            case_id in verified_adversarial
            and cases[case_id]["metadata"]["version_band"] == definition["id"]
            for case_id in planned_adversarial
        )
        for definition in config["version_bands"]
    }
    physical_survival_gate_passed = (
        set(survival_rows) == planned_adversarial
        and all(
            count >= minimum_surviving_attacks for count in band_survival.values()
        )
    )
    promotion_eligible = is_blind and not failures
    release_tier = (
        "blocked"
        if not promotion_eligible
        else "controlled_pilot_with_documented_limitations"
        if advisories
        else "general_deployment"
    )
    return {
        "schema_version": int(config.get("schema_version", 1)),
        "policy_id": config["policy_id"],
        "evidence_role": evidence_role,
        "campaign_id": plan.get("campaign_id"),
        "candidate_model_sha256": candidate_model_sha256,
        "plan_candidate_model_sha256": recorded_candidate_sha256 or None,
        "candidate_binding_matches": (
            recorded_candidate_sha256 == candidate_model_sha256
        ),
        "gate_passed": not failures,
        "promotion_eligible": promotion_eligible,
        "promotion_blocked": bool(failures) or not is_blind,
        "gate_failures": failures,
        "hard_gate_failures": failures,
        "advisories": advisories,
        "release_tier": release_tier,
        "coverage": coverage,
        "performance_by_class_version_band": performance,
        "clean_layout_probability_span": layout_span,
        "demo_branch_audit": {
            "gate_passed": demo_summary.get("gate_passed"),
            "masked_branch_errors": masked_errors,
        },
        "digital_sem11_gate_passed": digital_summary.get("gate_passed"),
        "physical_attack_survival": {
            "gate_passed": physical_survival_gate_passed,
            "planned_attacks": len(planned_adversarial),
            "verified_surviving_attacks": len(verified_adversarial),
            "verified_surviving_attacks_by_version_band": band_survival,
            "verified_survival_rate": (
                len(verified_adversarial) / len(planned_adversarial)
                if planned_adversarial
                else 0.0
            ),
            "candidate_scored_only_for_verified_survivors_in_recall_gate": True,
        },
        "production_mutation_performed": False,
    }


def _acceptance_markdown(report: dict[str, Any]) -> str:
    title = (
        "M8 blinded Structural acceptance"
        if report["evidence_role"] == "blind_holdout"
        else "M8 consumed holdout development replay"
    )
    lines = [
        f"# {title}",
        "",
        f"Gate passed: **{report['gate_passed']}**",
        "",
        f"Candidate model SHA-256: `{report['candidate_model_sha256']}`",
        "",
        "## Per-class Version-band results",
        "",
        "| Class | Version band | Sessions | Rescan | Class metric |",
        "|---|---|---:|---:|---:|",
    ]
    for label, bands in report["performance_by_class_version_band"].items():
        for band, row in bands.items():
            metric = (
                row["false_block_rate"] if label == "clean" else row["block_recall"]
            )
            lines.append(
                f"| {label} | {band} | {row['sessions']} | "
                f"{row['rescan_rate']:.1%} | {metric:.1%} |"
            )
    lines.extend(["", "## Gate failures", ""])
    lines.extend(f"- {failure}" for failure in report["gate_failures"])
    if not report["gate_failures"]:
        lines.append("- None")
    lines.extend(["", "## Advisories", ""])
    lines.extend(f"- {advisory}" for advisory in report.get("advisories", []))
    if not report.get("advisories"):
        lines.append("- None")
    lines.extend(["", f"Release tier: `{report.get('release_tier', 'unknown')}`"])
    lines.extend(
        [
            "",
            "This audit never copies artifacts, changes production defaults, pushes, or deploys.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--demo-audit", type=Path, default=DEFAULT_DEMO_AUDIT)
    parser.add_argument("--digital-sem11", type=Path, default=DEFAULT_DIGITAL_SEM11)
    parser.add_argument("--attack-survival", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--evidence-role",
        choices=("blind_holdout", "development_replay"),
        default="blind_holdout",
    )
    parser.add_argument("--allow-fail", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive = args.archive.resolve(strict=True)
    plan_path = args.plan.resolve(strict=True)
    artifacts = args.artifacts.resolve(strict=True)
    output = args.output.resolve()
    frames = validate_archive(archive, plan_path)
    archive_sha256 = _sha256(archive)
    attack_survival = _load(args.attack_survival.resolve(strict=True))
    if attack_survival.get("source_archive_sha256") != archive_sha256:
        raise ValueError("attack survival evidence belongs to a different archive")
    sessions = _evaluate(frames, artifacts, maximum_frames=3)
    replay = _summary(archive, sessions, artifacts, maximum_frames=3)
    metadata = _load(artifacts / "model_metadata.json")
    model_path = artifacts / _load(artifacts / "deploy_choice.json")["deploy_model"]
    model_sha256 = _sha256(model_path)
    if model_sha256 != metadata.get("artifact_sha256"):
        raise ValueError("candidate model hash does not match its metadata")
    report = audit_sessions(
        _load(plan_path),
        sessions,
        _load(args.config.resolve(strict=True)),
        _load(args.demo_audit.resolve(strict=True)),
        _load(args.digital_sem11.resolve(strict=True)),
        attack_survival,
        model_sha256,
        evidence_role=args.evidence_role,
    )
    report["source_archive"] = {
        "filename": archive.name,
        "sha256": archive_sha256,
        "sessions": len(sessions),
        "frames": len(frames),
    }
    output.mkdir(parents=True, exist_ok=True)
    rows = [asdict(row) for row in sessions]
    with (output / "SESSION_RESULTS.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "REPLAY_ANALYSIS.json").write_text(
        json.dumps(replay, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "REPLAY_SUMMARY.md").write_text(_markdown(replay), encoding="utf-8")
    (output / "blind_holdout_acceptance.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "SUMMARY.md").write_text(_acceptance_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "gate_passed": report["gate_passed"],
                "failures": len(report["gate_failures"]),
            },
            indent=2,
        )
    )
    if not report["gate_passed"] and not args.allow_fail:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
