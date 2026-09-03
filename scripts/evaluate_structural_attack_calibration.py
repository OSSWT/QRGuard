"""Replay a Structural attack-calibration capture against a frozen candidate.

The calibration campaign is development evidence.  Clean cases are all scored,
while adversarial recall includes only attacks independently verified to survive
the display/camera path.  The report cannot promote or copy runtime artifacts.
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
from scripts.evaluate_live_camera_candidate import CandidateSession, _evaluate

DEFAULT_PLAN = ROOT / "app/assets/capture/structural_attack_calibration_plan.json"
DEFAULT_CONFIG = ROOT / "ml_training/configs/structural-r07-product-acceptance-v1.json"
DEFAULT_OUTPUT = (
    ROOT
    / "research_evidence/structural/performance/r07-corrective"
    / "ATTACK_CALIBRATION_V1_REPLAY"
)
BANDS = ("low_v1_v3", "medium_v4_v6", "high_v7_plus")


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


def _candidate_identity(artifacts: Path) -> dict[str, Any]:
    metadata_path = artifacts / "model_metadata.json"
    deploy_choice_path = artifacts / "deploy_choice.json"
    metadata = _load(metadata_path)
    deploy_choice = _load(deploy_choice_path)
    model_path = artifacts / str(deploy_choice["deploy_model"])
    model_sha256 = _sha256(model_path)
    if model_sha256 != metadata.get("artifact_sha256"):
        raise ValueError("Structural model hash does not match model_metadata.json")
    return {
        "version": metadata.get("version"),
        "model_sha256": model_sha256,
        "model_metadata_sha256": _sha256(metadata_path),
        "runtime_policy": metadata.get("runtime_policy", {}),
    }


def summarise_development_replay(
    *,
    plan: dict[str, Any],
    sessions: list[CandidateSession],
    survival: dict[str, Any],
    config: dict[str, Any],
    candidate: dict[str, Any],
    source_archive_sha256: str,
    survival_report_sha256: str,
) -> dict[str, Any]:
    """Apply pre-registered functional thresholds without granting promotion."""

    cases = {str(row["case_id"]): row for row in plan["cases"]}
    sessions_by_case = {row.case_id: row for row in sessions}
    survival_rows = {
        str(row["adversarial_case_id"]): row for row in survival.get("rows", [])
    }
    planned_attacks = {
        case_id
        for case_id, case in cases.items()
        if case.get("ground_truth") == "adversarial"
    }
    clean_cases = {
        case_id
        for case_id, case in cases.items()
        if case.get("ground_truth") == "clean"
    }
    verified_attacks = {
        case_id
        for case_id, row in survival_rows.items()
        if row.get("physical_attack_survival_verified") is True
    }
    expected_scored = clean_cases | verified_attacks

    integrity_failures: list[str] = []
    if survival.get("evaluation") != "paired_post_capture_adversarial_survival":
        integrity_failures.append("independent physical-survival evidence is invalid")
    if survival.get("campaign_id") != plan.get("campaign_id"):
        integrity_failures.append("survival campaign does not match the capture plan")
    if survival.get("source_archive_sha256") != source_archive_sha256:
        integrity_failures.append("survival evidence belongs to another capture archive")
    if set(survival_rows) != planned_attacks:
        integrity_failures.append("survival evidence does not cover every planned attack")
    if set(sessions_by_case) != expected_scored:
        integrity_failures.append("candidate replay did not score the locked eligible cases")

    minimum_survivors = int(config["minimum_verified_surviving_attacks_per_version_band"])
    maximum_clean_false_block = float(
        config["maximum_clean_camera_false_block_rate_per_version_band"]
    )
    minimum_attack_recall = float(
        config["minimum_adversarial_camera_block_recall_per_version_band"]
    )
    maximum_rescan = float(config["maximum_camera_rescan_rate_per_class_version_band"])

    functional_failures: list[str] = []
    performance: dict[str, dict[str, Any]] = {"clean": {}, "adversarial": {}}
    attack_case_diagnostics: dict[str, Any] = {}
    for label in ("clean", "adversarial"):
        for band in BANDS:
            selected_sessions = [
                row
                for case_id, row in sessions_by_case.items()
                if cases[case_id]["ground_truth"] == label
                and cases[case_id]["metadata"]["version_band"] == band
            ]
            grouped: dict[str, list[CandidateSession]] = {}
            for session in selected_sessions:
                base_identity = str(cases[session.case_id]["metadata"]["base_identity"])
                grouped.setdefault(base_identity, []).append(session)

            group_outcomes: list[str] = []
            for group_sessions in grouped.values():
                if any(
                    item.outcome in {"false_safe", "false_block"}
                    for item in group_sessions
                ):
                    group_outcomes.append("incorrect")
                elif any(item.outcome == "rescan" for item in group_sessions):
                    group_outcomes.append("rescan")
                elif label == "clean" or all(
                    item.verdict == "blocked"
                    and item.structural_type in {"adversarial", "tampered"}
                    for item in group_sessions
                ):
                    group_outcomes.append("correct")
                else:
                    group_outcomes.append("incorrect")

            count = len(group_outcomes)
            rescans = group_outcomes.count("rescan")
            rescan_rate = rescans / count if count else 1.0
            row: dict[str, Any] = {
                "independent_base_identities": count,
                "attack_case_sessions": len(selected_sessions),
                "rescans": rescans,
                "rescan_rate": rescan_rate,
                "group_outcomes": dict(Counter(group_outcomes)),
                "case_outcomes": dict(
                    Counter(item.outcome for item in selected_sessions)
                ),
                "case_verdicts": dict(
                    Counter(item.verdict for item in selected_sessions)
                ),
            }
            if rescan_rate > maximum_rescan:
                functional_failures.append(
                    f"{label}/{band}: rescan rate {rescan_rate:.4f} exceeds {maximum_rescan:.4f}"
                )
            if label == "clean":
                false_blocks = group_outcomes.count("incorrect")
                rate = false_blocks / count if count else 1.0
                row.update({"false_blocks": false_blocks, "false_block_rate": rate})
                if rate > maximum_clean_false_block:
                    functional_failures.append(
                        f"clean/{band}: false-Blocked rate {rate:.4f} exceeds "
                        f"{maximum_clean_false_block:.4f}"
                    )
            else:
                blocked = group_outcomes.count("correct")
                recall = blocked / count if count else 0.0
                row.update({"blocked": blocked, "block_recall": recall})
                if count < minimum_survivors:
                    functional_failures.append(
                        f"adversarial/{band}: {count} verified independent bases; "
                        f"require {minimum_survivors}"
                    )
                if recall < minimum_attack_recall:
                    functional_failures.append(
                        f"adversarial/{band}: block recall {recall:.4f} below "
                        f"{minimum_attack_recall:.4f}"
                    )
                case_count = len(selected_sessions)
                case_rescans = sum(
                    item.outcome == "rescan" for item in selected_sessions
                )
                case_blocks = sum(
                    item.verdict == "blocked"
                    and item.structural_type in {"adversarial", "tampered"}
                    for item in selected_sessions
                )
                attack_case_diagnostics[band] = {
                    "sessions": case_count,
                    "blocked": case_blocks,
                    "block_recall": case_blocks / case_count if case_count else 0.0,
                    "rescans": case_rescans,
                    "rescan_rate": case_rescans / case_count if case_count else 1.0,
                    "outcomes": dict(
                        Counter(item.outcome for item in selected_sessions)
                    ),
                }
            performance[label][band] = row

    clean_scores = [
        row.p_structural_raw
        for row in sessions
        if row.ground_truth == "clean" and row.p_structural_raw is not None
    ]
    clean_span = max(clean_scores) - min(clean_scores) if clean_scores else 1.0
    maximum_span = float(config["maximum_clean_layout_probability_span"])
    advisories = []
    if clean_span > maximum_span:
        advisories.append(
            f"clean layout probability span {clean_span:.4f} exceeds {maximum_span:.4f}"
        )

    all_failures = integrity_failures + functional_failures
    return {
        "schema_version": 1,
        "evaluation": "structural_attack_calibration_development_replay",
        "evidence_role": "development_only",
        "campaign_id": plan.get("campaign_id"),
        "source_archive_sha256": source_archive_sha256,
        "survival_report_sha256": survival_report_sha256,
        "candidate": candidate,
        "selection_contract": {
            "clean_cases": "all locked clean controls",
            "adversarial_cases": "independent post-capture survivors only",
            "frame_selection": "production pixel quality and exposure diversity",
            "maximum_geometry_ranked_frames": 3,
            "functional_gate_unit": "independent base_identity",
            "group_aggregation": (
                "conservative: any false result is incorrect; otherwise any rescan "
                "is rescan; all remaining attack variants must block"
            ),
            "planned_attack_cases": len(planned_attacks),
            "verified_surviving_attack_cases": len(verified_attacks),
            "excluded_non_surviving_attack_cases": len(planned_attacks - verified_attacks),
            "candidate_scored_only_for_verified_survivors_in_recall_metrics": True,
        },
        "integrity_gate_passed": not integrity_failures,
        "functional_gate_passed": not functional_failures,
        "development_gate_passed": not all_failures,
        "integrity_failures": integrity_failures,
        "functional_failures": functional_failures,
        "advisories": advisories,
        "performance_by_class_version_band": performance,
        "attack_case_diagnostics_by_version_band": attack_case_diagnostics,
        "clean_layout_probability_span": clean_span,
        "promotion_eligible": False,
        "production_mutation_performed": False,
        "next_action": (
            "retain_candidate_and_build_new_blind_campaign"
            if not all_failures
            else "correct_candidate_inside_r07_before_new_blind_campaign"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Structural attack calibration development replay",
        "",
        f"Development gate passed: **{report['development_gate_passed']}**",
        "",
        "This campaign is development-only and cannot approve deployment.",
        "Only independently verified post-capture attack survivors contribute to recall.",
        "",
        "| Class | Version band | Independent bases | Rescan | Functional metric |",
        "|---|---|---:|---:|---:|",
    ]
    for label, bands in report["performance_by_class_version_band"].items():
        for band, row in bands.items():
            metric = (
                row["false_block_rate"] if label == "clean" else row["block_recall"]
            )
            lines.append(
                f"| {label} | {band} | {row['independent_base_identities']} | "
                f"{row['rescan_rate']:.1%} | {metric:.1%} |"
            )
    lines.extend(
        [
            "",
            f"Clean raw-score span: {report['clean_layout_probability_span']:.4f}",
            "",
            f"Next action: `{report['next_action']}`",
            "",
        ]
    )
    if report["functional_failures"]:
        lines.extend(["Functional failures:", ""])
        lines.extend(f"- {value}" for value in report["functional_failures"])
        lines.append("")
    if report["advisories"]:
        lines.extend(["Advisories:", ""])
        lines.extend(f"- {value}" for value in report["advisories"])
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--survival", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive = args.archive.resolve(strict=True)
    plan_path = args.plan.resolve(strict=True)
    survival_path = args.survival.resolve(strict=True)
    artifacts = args.artifacts.resolve(strict=True)
    config_path = args.config.resolve(strict=True)
    plan = _load(plan_path)
    survival = _load(survival_path)
    archive_sha256 = _sha256(archive)
    if survival.get("source_archive_sha256") != archive_sha256:
        raise ValueError("physical-survival report belongs to another archive")

    all_frames = validate_archive(archive, plan_path)
    surviving_attacks = {
        str(row["adversarial_case_id"])
        for row in survival.get("rows", [])
        if row.get("physical_attack_survival_verified") is True
    }
    eligible_frames = [
        frame
        for frame in all_frames
        if frame.ground_truth == "clean" or frame.case_id in surviving_attacks
    ]
    sessions = _evaluate(eligible_frames, artifacts, maximum_frames=3)
    report = summarise_development_replay(
        plan=plan,
        sessions=sessions,
        survival=survival,
        config=_load(config_path),
        candidate=_candidate_identity(artifacts),
        source_archive_sha256=archive_sha256,
        survival_report_sha256=_sha256(survival_path),
    )
    report["source"] = {
        "filename": archive.name,
        "validated_sessions": len({frame.session_id for frame in all_frames}),
        "validated_frames": len(all_frames),
        "scored_sessions": len(sessions),
        "scored_frames_captured": sum(row.frames_captured for row in sessions),
        "raw_payload_stored": False,
    }

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = [asdict(row) for row in sessions]
    with (output / "SESSION_RESULTS.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "ANALYSIS.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "SUMMARY.md").write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "development_gate_passed": report["development_gate_passed"],
                "functional_failures": report["functional_failures"],
                "advisories": report["advisories"],
                "next_action": report["next_action"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
