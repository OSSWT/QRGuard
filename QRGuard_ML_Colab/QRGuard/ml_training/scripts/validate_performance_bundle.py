"""Validate report completeness separately from deployment approval.

A rejected candidate can still have a complete, useful performance bundle. This
script never turns a missing real-world gate into a fabricated score: it reports
`report_complete` and `deployment_approved` as two independent facts.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {
    "structural": (
        "metrics.json",
        "metrics.csv",
        "dataset_composition.csv",
        "training_history.csv",
        "training_curves.png",
        "confusion_matrix.png",
        "roc_pr_curves.png",
        "calibration_curve.png",
        "per_source_results.csv",
        "per_device_results.csv",
        "gallery_camera_consistency.csv",
        "misclassified_samples.csv",
        "qrdn_clean_distribution.png",
        "STRUCTURAL_PERFORMANCE.md",
    ),
    "semantic": (
        "metrics.json",
        "metrics.csv",
        "dataset_composition.csv",
        "training_curves.png",
        "confusion_matrix.png",
        "roc_pr_curves.png",
        "calibration_curve.png",
        "threshold_analysis.csv",
        "per_source_results.csv",
        "hard_benign_results.csv",
        "behavioural_acceptance.csv",
        "SEMANTIC_PERFORMANCE.md",
    ),
}


def validate(branch: str, version: str) -> dict:
    performance = ROOT / "ml_training" / branch / "performance" / version
    required = REQUIRED[branch]
    missing = [
        name
        for name in required
        if not (performance / name).is_file()
        or (performance / name).stat().st_size == 0
    ]
    metrics_path = performance / "metrics.json"
    metrics = {}
    parse_error = None
    if metrics_path.is_file():
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parse_error = str(exc)
    gate_key = "deployment_gates_passed" if branch == "structural" else "gates_passed"
    failures_key = (
        "deployment_gate_failures" if branch == "structural" else "gate_failures"
    )
    return {
        "branch": branch,
        "version": version,
        "performance_directory": performance.relative_to(ROOT).as_posix(),
        "report_complete": not missing and parse_error is None,
        "missing_or_empty": missing,
        "metrics_parse_error": parse_error,
        "deployment_approved": bool(metrics.get(gate_key, False)),
        "deployment_gate_failures": metrics.get(failures_key, []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--branch",
        choices=("structural", "semantic", "all"),
        default="all",
    )
    parser.add_argument("--structural-version", default="structural-2026.02")
    parser.add_argument("--semantic-version", default="semantic-2026.02")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "ml_training/PERFORMANCE_VALIDATION.json",
    )
    args = parser.parse_args()
    branches = ("structural", "semantic") if args.branch == "all" else (args.branch,)
    versions = {
        "structural": args.structural_version,
        "semantic": args.semantic_version,
    }
    results = [validate(branch, versions[branch]) for branch in branches]
    report = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "all_reports_complete": all(result["report_complete"] for result in results),
        "all_deployment_approved": all(
            result["deployment_approved"] for result in results
        ),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["all_reports_complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
