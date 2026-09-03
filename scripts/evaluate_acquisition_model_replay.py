"""Evaluate an acquisition campaign replay without hiding branch-level errors.

The generic live-camera replay summary treats every structurally clean QR code as
having an intended final verdict of Safe.  That is deliberately not true for
semantic sentinels such as SEM-05.  This evaluator joins the capture plan,
acquisition audit, frame replay, and session replay so final-verdict correctness,
Structural correctness, and Semantic correctness remain separate.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPLAY = (
    ROOT
    / "research_evidence"
    / "structural"
    / "performance"
    / "screen-camera-robustness-2026-09-r02"
    / "MODEL_REPLAY_R01"
)
DEFAULT_ACQUISITION_AUDIT = (
    ROOT
    / "research_evidence"
    / "structural"
    / "performance"
    / "screen-camera-robustness-2026-09-r02"
    / "ACQUISITION_VALIDATION"
    / "ACQUISITION_AUDIT.json"
)
DEFAULT_PLAN = ROOT / "app" / "assets" / "capture" / "acquisition_validation_plan.json"
DEFAULT_CONFIG = ROOT / "ml_training" / "configs" / "structural-2026.09-r02.json"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _truth(value: str) -> bool:
    return value.strip().lower() == "true"


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _linear_quantile(values: list[float], quantile: float) -> float | None:
    """Match NumPy's default linear quantile without adding a runtime import."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def build_evaluation(
    *,
    acquisition: dict[str, Any],
    replay: dict[str, Any],
    plan: dict[str, Any],
    config: dict[str, Any],
    frames: list[dict[str, str]],
    sessions: list[dict[str, str]],
) -> dict[str, Any]:
    cases = {str(case["case_id"]): case for case in plan["cases"]}
    condition_ids = {str(item["id"]) for item in plan["distances"]}
    intended = {
        case_id: str(
            case.get("metadata", {}).get(
                "intended_app_verdict",
                "SAFE" if case["ground_truth"] == "clean" else "BLOCKED",
            )
        ).lower()
        for case_id, case in cases.items()
    }
    floor = float(config["runtime_policy"]["camera_definitive_manipulation_floor"])
    gates = config["deployment_gates"]

    clean_frames = [row for row in frames if row["ground_truth"] == "clean"]
    attack_frames = [row for row in frames if row["ground_truth"] != "clean"]
    nonclean_types = {"adversarial", "tampered"}
    clean_structural_fp = [
        row for row in clean_frames if row["structural_type"] in nonclean_types
    ]
    definitive_clean_fp = [
        row
        for row in clean_structural_fp
        if float(row["p_structural_effective"]) >= floor
    ]
    attack_detected = [
        row for row in attack_frames if row["structural_type"] in nonclean_types
    ]
    definitive_attack_detected = [
        row
        for row in attack_detected
        if float(row["p_structural_effective"]) >= floor
    ]

    class_metrics: dict[str, Any] = {}
    for class_name in ("adversarial", "tampered"):
        selected = [row for row in frames if row["ground_truth"] == class_name]
        detected = [row for row in selected if row["structural_type"] in nonclean_types]
        definitive = [
            row
            for row in detected
            if float(row["p_structural_effective"]) >= floor
        ]
        class_metrics[class_name] = {
            "frames": len(selected),
            "structural_recall": _rate(len(detected), len(selected)),
            "definitive_recall_at_camera_floor": _rate(len(definitive), len(selected)),
            "final_safe_escapes": sum(row["verdict"] == "safe" for row in selected),
        }

    frame_intended_matches = sum(
        row["verdict"] == intended[row["case_id"]] for row in frames
    )
    session_intended_matches = sum(
        row["majority_verdict"] == intended[row["case_id"]] for row in sessions
    )

    sessions_by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in sessions:
        sessions_by_case[row["case_id"]].append(row)

    case_rows: list[dict[str, Any]] = []
    clean_spans: list[float] = []
    exposure_agreeing_cases = 0
    exposure_correct_cases = 0
    exposure_safety_preserving_cases = 0
    for case_id in sorted(cases):
        selected = sessions_by_case[case_id]
        observed_conditions = {row["distance"] for row in selected}
        verdicts = {row["majority_verdict"] for row in selected}
        complete = observed_conditions == condition_ids and len(selected) == len(condition_ids)
        exposure_agrees = complete and len(verdicts) == 1
        correct_all_conditions = complete and all(
            row["majority_verdict"] == intended[case_id] for row in selected
        )
        # Warning is the deliberate fail-safe result when image quality or QR
        # decoding is inconclusive. It must remain visible in the exact-agreement
        # diagnostic, but it is not the unsafe opposite of Safe or Blocked.
        safety_preserving_all_conditions = complete and all(
            row["majority_verdict"] in {intended[case_id], "warning"}
            for row in selected
        )
        exposure_agreeing_cases += exposure_agrees
        exposure_correct_cases += correct_all_conditions
        exposure_safety_preserving_cases += safety_preserving_all_conditions
        probabilities = [float(row["median_p_structural"]) for row in selected]
        probability_span = max(probabilities) - min(probabilities)
        if cases[case_id]["ground_truth"] == "clean":
            clean_spans.append(probability_span)
        case_rows.append(
            {
                "case_id": case_id,
                "ground_truth": cases[case_id]["ground_truth"],
                "intended_app_verdict": intended[case_id],
                "session_majority_verdicts": dict(
                    sorted(Counter(row["majority_verdict"] for row in selected).items())
                ),
                "exposure_verdict_agreement": exposure_agrees,
                "correct_under_all_exposure_conditions": correct_all_conditions,
                "safety_preserving_under_all_exposure_conditions": (
                    safety_preserving_all_conditions
                ),
                "median_p_structural_span": probability_span,
            }
        )

    sem05_frames = [row for row in frames if row["case_id"] == "SEM-05-USERINFO"]
    sem05_decoded = [row for row in sem05_frames if _truth(row["payload_hash_matches"])]
    sem05_semantic_misses = [
        row
        for row in sem05_decoded
        if row["semantic_status"] != "completed"
        or row["verdict"] != intended["SEM-05-USERINFO"]
    ]
    sem05_masked = [
        row
        for row in sem05_decoded
        if row["verdict"] == intended["SEM-05-USERINFO"]
        and row["structural_type"] != "clean"
    ]
    sem05_sessions = sessions_by_case["SEM-05-USERINFO"]
    sem11_frames = [row for row in frames if row["case_id"] == "SEM-11-PLAIN-TEXT"]
    sem11_sessions = sessions_by_case["SEM-11-PLAIN-TEXT"]

    clean_fpr = _rate(len(clean_structural_fp), len(clean_frames))
    exposure_agreement = _rate(exposure_agreeing_cases, len(cases))
    exposure_correctness = _rate(exposure_correct_cases, len(cases))
    exposure_safety_preservation = _rate(
        exposure_safety_preserving_cases, len(cases)
    )
    clean_span_p95 = _linear_quantile(clean_spans, 0.95)
    gate_results = {
        "acquisition_gate": acquisition["acquisition_gate_passed"] is True,
        "archive_identity_matches": (
            acquisition["source"]["sha256"] == replay["source"]["sha256"]
        ),
        "real_clean_false_positive_rate": clean_fpr
        <= float(gates["real_clean_false_positive_rate_max"]),
        "real_adversarial_recall": class_metrics["adversarial"]["structural_recall"]
        >= float(gates["real_adversarial_recall_min"]),
        "real_tampered_recall": class_metrics["tampered"]["structural_recall"]
        >= float(gates["real_tampered_recall_min"]),
        "exposure_safety_preservation": exposure_safety_preservation
        >= float(gates["exposure_verdict_agreement_min"]),
        "clean_exposure_probability_span_p95": clean_span_p95 is not None
        and clean_span_p95 <= float(gates["clean_exposure_probability_span_p95_max"]),
        "sem05_style_masked_branch_errors": len(sem05_masked)
        <= int(gates["sem05_style_masked_branch_errors_max"]),
    }
    failed = [name for name, passed in gate_results.items() if not passed]

    return {
        "schema_version": 1,
        "audit": "qrguard_acquisition_model_replay_gate",
        "source": {
            "archive_sha256": replay["source"]["sha256"],
            "model_version": replay["model"]["version"],
            "model_artifact_sha256": replay["model"]["artifact_sha256"],
            "frames": len(frames),
            "sessions": len(sessions),
        },
        "acquisition": {
            "gate_passed": acquisition["acquisition_gate_passed"],
            "minimum_observed_pixels_per_module": acquisition["telemetry"][
                "minimum_observed_pixels_per_module"
            ],
            "quality_statuses": acquisition["telemetry"][
                "structural_quality_statuses"
            ],
        },
        "structural": {
            "clean_frames": len(clean_frames),
            "clean_false_positive_frames": len(clean_structural_fp),
            "clean_false_positive_rate": clean_fpr,
            "definitive_clean_false_positive_frames_at_camera_floor": len(
                definitive_clean_fp
            ),
            "definitive_clean_false_positive_rate_at_camera_floor": _rate(
                len(definitive_clean_fp), len(clean_frames)
            ),
            "attack_frames": len(attack_frames),
            "attack_detected_frames": len(attack_detected),
            "attack_recall": _rate(len(attack_detected), len(attack_frames)),
            "definitive_attack_recall_at_camera_floor": _rate(
                len(definitive_attack_detected), len(attack_frames)
            ),
            "classes": class_metrics,
        },
        "final_verdict": {
            "frame_intended_matches": frame_intended_matches,
            "frame_intended_accuracy": _rate(frame_intended_matches, len(frames)),
            "session_majority_intended_matches": session_intended_matches,
            "session_majority_intended_accuracy": _rate(
                session_intended_matches, len(sessions)
            ),
        },
        "exposure": {
            "agreeing_cases": exposure_agreeing_cases,
            "case_count": len(cases),
            "verdict_agreement_rate": exposure_agreement,
            "correct_under_all_conditions_cases": exposure_correct_cases,
            "correct_under_all_conditions_rate": exposure_correctness,
            "safety_preserving_cases": exposure_safety_preserving_cases,
            "safety_preservation_rate": exposure_safety_preservation,
            "clean_median_p_structural_spans": clean_spans,
            "clean_median_p_structural_span_p95": clean_span_p95,
        },
        "sentinels": {
            "sem11": {
                "frames": len(sem11_frames),
                "false_blocked_frames": sum(
                    row["verdict"] == "blocked" for row in sem11_frames
                ),
                "false_blocked_sessions": sum(
                    row["majority_verdict"] == "blocked" for row in sem11_sessions
                ),
                "sessions": len(sem11_sessions),
            },
            "sem05": {
                "frames": len(sem05_frames),
                "payload_hash_matched_frames": len(sem05_decoded),
                "semantic_misses_on_payload_matched_frames": len(
                    sem05_semantic_misses
                ),
                "masked_structural_branch_errors": len(sem05_masked),
                "intended_blocked_frames": sum(
                    row["verdict"] == "blocked" for row in sem05_frames
                ),
                "intended_blocked_sessions": sum(
                    row["majority_verdict"] == "blocked" for row in sem05_sessions
                ),
                "sessions": len(sem05_sessions),
            },
        },
        "cases": case_rows,
        "gates": gate_results,
        "failed_gates": failed,
        "model_replay_gate_passed": not failed,
        "promotion_eligible": False,
        "non_promotion_reasons": [
            f"{replay['model']['version']} fails development model replay gates"
            if failed
            else "this is development evidence, not an independent holdout",
            "this acquisition campaign is development evidence and cannot promote a model",
            "a fresh device/display/session blind holdout remains mandatory",
        ],
    }


def _markdown(report: dict[str, Any]) -> str:
    structural = report["structural"]
    exposure = report["exposure"]
    sem11 = report["sentinels"]["sem11"]
    sem05 = report["sentinels"]["sem05"]
    failures = ", ".join(report["failed_gates"]) or "none"
    return "\n".join(
        [
            "# Acquisition model replay gate",
            "",
            f"- Acquisition gate: **{report['acquisition']['gate_passed']}**",
            f"- Model replay gate: **{report['model_replay_gate_passed']}**",
            f"- Failed gates: {failures}",
            f"- Clean Structural FPR: {structural['clean_false_positive_frames']}/{structural['clean_frames']} ({structural['clean_false_positive_rate']:.3f})",
            f"- Attack Structural recall: {structural['attack_detected_frames']}/{structural['attack_frames']} ({structural['attack_recall']:.3f})",
            f"- Exposure verdict agreement: {exposure['agreeing_cases']}/{exposure['case_count']} ({exposure['verdict_agreement_rate']:.3f})",
            f"- Exposure safety preservation: {exposure['safety_preserving_cases']}/{exposure['case_count']} ({exposure['safety_preservation_rate']:.3f})",
            f"- Clean exposure probability-span p95: {exposure['clean_median_p_structural_span_p95']:.3f}",
            f"- SEM-11 false-blocked sessions: {sem11['false_blocked_sessions']}/{sem11['sessions']}",
            f"- SEM-05 intended-blocked sessions: {sem05['intended_blocked_sessions']}/{sem05['sessions']}",
            f"- SEM-05 payload-matched Semantic misses: {sem05['semantic_misses_on_payload_matched_frames']}",
            f"- SEM-05 masked Structural branch errors: {sem05['masked_structural_branch_errors']}",
            "",
            "This campaign is development evidence only and cannot promote a model.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--acquisition-audit", type=Path, default=DEFAULT_ACQUISITION_AUDIT)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    replay_dir = args.replay.resolve()
    report = build_evaluation(
        acquisition=_read_json(args.acquisition_audit.resolve()),
        replay=_read_json(replay_dir / "ANALYSIS.json"),
        plan=_read_json(args.plan.resolve()),
        config=_read_json(args.config.resolve()),
        frames=_read_csv(replay_dir / "FRAME_RESULTS.csv"),
        sessions=_read_csv(replay_dir / "SESSION_RESULTS.csv"),
    )
    (replay_dir / "VALIDATION_GATE.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (replay_dir / "VALIDATION_GATE.md").write_text(
        _markdown(report), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
