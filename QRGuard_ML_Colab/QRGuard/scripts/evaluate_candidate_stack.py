"""Run the accepted Structural and Decision candidates through the real pipeline.

This is a deployment-preparation smoke gate, not another model-training step.  It
loads the unified Structural v3 artifact and versioned Fusion weights via the
same backend code used by the API, evaluates only canonical locked-test crops,
and writes a self-contained result bundle without promoting runtime artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

CLASS_NAMES = ("clean", "adversarial", "tampered")
BENIGN_PROBE = "https://www.google.com/maps"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_fingerprint(directory: Path) -> dict:
    temperature = directory / "temperature.json"
    metadata = directory / "model_metadata.json"
    return {
        "temperature": (
            json.loads(temperature.read_text(encoding="utf-8"))["temperature"]
            if temperature.is_file()
            else None
        ),
        "onnx_bytes": {
            path.name: path.stat().st_size for path in sorted(directory.glob("*.onnx"))
        },
        "joblib_sha256": {},
        "metadata_sha256": (
            hashlib.sha256(metadata.read_bytes()).hexdigest()[:16]
            if metadata.is_file()
            else None
        ),
    }


def _rate(rows: list[dict], label: str, predicate) -> float | None:
    selected = [row for row in rows if row["label"] == label]
    return (
        sum(bool(predicate(row)) for row in selected) / len(selected)
        if selected
        else None
    )


def summarise(rows: list[dict]) -> dict:
    per_source = {}
    for source in ("camera", "gallery"):
        selected = [row for row in rows if row["image_source"] == source]
        per_source[source] = {
            "rows": len(selected),
            "usable_rows": sum(
                row["structural_status"] == "completed" for row in selected
            ),
            "clean_false_block_rate": _rate(
                selected, "clean", lambda row: row["verdict"] == "blocked"
            ),
            "adversarial_block_recall": _rate(
                selected, "adversarial", lambda row: row["verdict"] == "blocked"
            ),
            "tampered_block_recall": _rate(
                selected, "tampered", lambda row: row["verdict"] == "blocked"
            ),
        }

    pairs = defaultdict(dict)
    for row in rows:
        pairs[row["paired_group"]][row["image_source"]] = row
    complete_pairs = [
        pair for pair in pairs.values() if set(pair) == {"camera", "gallery"}
    ]
    exact_agreement = sum(
        pair["camera"]["verdict"] == pair["gallery"]["verdict"]
        for pair in complete_pairs
    )
    blocked_agreement = sum(
        (pair["camera"]["verdict"] == "blocked")
        == (pair["gallery"]["verdict"] == "blocked")
        for pair in complete_pairs
    )
    paired = {
        "complete_pairs": len(complete_pairs),
        "exact_verdict_agreement": (
            exact_agreement / len(complete_pairs) if complete_pairs else None
        ),
        "blocked_verdict_agreement": (
            blocked_agreement / len(complete_pairs) if complete_pairs else None
        ),
    }
    return {"rows": len(rows), "per_source": per_source, "paired": paired}


def evaluate(
    structural_artifacts: Path,
    fusion_weights: Path,
    manifest_path: Path,
    capture_root: Path,
    output: Path,
) -> dict:
    structural_artifacts = structural_artifacts.resolve()
    fusion_weights = fusion_weights.resolve()
    manifest_path = manifest_path.resolve()
    capture_root = capture_root.resolve()
    output = output.resolve()

    structural_metadata_path = structural_artifacts / "model_metadata.json"
    structural_metadata = json.loads(
        structural_metadata_path.read_text(encoding="utf-8")
    )
    fusion_blob = json.loads(fusion_weights.read_text(encoding="utf-8"))
    if not structural_metadata.get("deployment_gates_passed"):
        raise ValueError("Structural candidate is not deployment approved")
    if not fusion_blob.get("metadata", {}).get("deployment_gates_passed"):
        raise ValueError("Decision candidate is not deployment approved")
    expected_fingerprint = (
        fusion_blob.get("metadata", {}).get("model_fingerprint", {}).get("structural")
    )
    actual_fingerprint = _artifact_fingerprint(structural_artifacts)
    if expected_fingerprint != actual_fingerprint:
        raise ValueError(
            "Decision candidate fingerprint does not match Structural artifact"
        )

    os.environ["QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS"] = str(structural_artifacts)
    os.environ["QRGUARD_FUSION_WEIGHTS"] = str(fusion_weights)
    from app.pipeline import run_scan
    from fusion.engine import load_engine
    from structural.structural_service import (
        load_analyzer,
        load_unified_candidate_analyzer,
    )

    load_engine.cache_clear()
    load_analyzer.cache_clear()
    load_unified_candidate_analyzer.cache_clear()

    manifest_rows = list(
        csv.DictReader(manifest_path.open(encoding="utf-8", newline=""))
    )
    selected = [
        row
        for row in manifest_rows
        if row.get("split") == "test"
        and row.get("label") in CLASS_NAMES
        and row.get("image_source") in {"camera", "gallery"}
        and str(row.get("is_authoritative", "")).lower() == "true"
    ]
    results = []
    from PIL import Image

    for row in selected:
        image_path = (capture_root / row["sample_path"]).resolve()
        try:
            image_path.relative_to(capture_root)
        except ValueError as error:
            raise ValueError(
                f"sample path escapes capture root: {image_path}"
            ) from error
        with Image.open(image_path) as image:
            response = run_scan(
                BENIGN_PROBE,
                images=[image.convert("RGB")],
                image_source=row["image_source"],
                image_expected=True,
            )
        results.append(
            {
                "sample_path": row["sample_path"],
                "sha256": row["sha256"],
                "label": row["label"],
                "image_source": row["image_source"],
                "paired_group": row["paired_group"],
                "quality_condition": row["quality_condition"],
                "quality_severity": row["quality_severity"],
                "structural_status": response.branch_scores.structural_status,
                "structural_type": response.branch_scores.structural_type,
                "p_structural": response.branch_scores.p_structural,
                "verdict": response.verdict,
                "risk_score": response.risk_score,
            }
        )

    metrics = summarise(results)
    camera = metrics["per_source"]["camera"]
    paired = metrics["paired"]
    failures = []
    for name, value, threshold, direction in (
        (
            "camera clean false-block rate",
            camera["clean_false_block_rate"],
            0.05,
            "max",
        ),
        (
            "camera adversarial block recall",
            camera["adversarial_block_recall"],
            0.80,
            "min",
        ),
        ("camera tampered block recall", camera["tampered_block_recall"], 0.85, "min"),
        (
            "paired exact verdict agreement",
            paired["exact_verdict_agreement"],
            0.95,
            "min",
        ),
    ):
        failed = value is None or (
            value > threshold if direction == "max" else value < threshold
        )
        if failed:
            failures.append(f"{name}={value}; requires {direction} {threshold}")

    output.mkdir(parents=True, exist_ok=True)
    predictions_path = output / "candidate_stack_predictions.csv"
    with predictions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    report = {
        "schema_version": 1,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "canonical authoritative locked test; full backend candidate stack",
        "probe_payload": BENIGN_PROBE,
        "structural_version": structural_metadata.get("version"),
        "structural_artifact_sha256": structural_metadata.get("artifact_sha256"),
        "decision_version": fusion_blob.get("metadata", {}).get("version"),
        "fusion_weights_sha256": _sha256(fusion_weights),
        "manifest_sha256": _sha256(manifest_path),
        "metrics": metrics,
        "gates_passed": not failures,
        "gate_failures": failures,
        "predictions_sha256": _sha256(predictions_path),
    }
    (output / "candidate_stack_metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structural-artifacts", type=Path, required=True)
    parser.add_argument("--fusion-weights", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "data/runtime_captures/manifest_v3.csv"
    )
    parser.add_argument(
        "--capture-root", type=Path, default=ROOT / "data/runtime_captures"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(
        args.structural_artifacts,
        args.fusion_weights,
        args.manifest,
        args.capture_root,
        args.output,
    )
    print(json.dumps(report, indent=2))
    if not report["gates_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
