"""Evaluate a Structural ONNX candidate on grouped clean QR mask families."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from structural.structural_service import StructuralAnalyzer  # noqa: E402

SOURCE = "procedural_qrguard_topology_counterfactual"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate(manifest: Path, artifacts: Path, split: str) -> dict:
    rows = [
        row
        for row in csv.DictReader(manifest.open(encoding="utf-8", newline=""))
        if row.get("source") == SOURCE and row.get("split") == split
    ]
    if not rows:
        raise ValueError(f"no {SOURCE} rows found in split {split!r}")
    if {row["label"] for row in rows} != {"clean"}:
        raise ValueError("topology counterfactual evaluation must remain clean-only")

    analyzer = StructuralAnalyzer(artifacts)
    predictions = []
    for index, row in enumerate(rows, start=1):
        result = analyzer.predict(ROOT / row["path"])
        predictions.append(
            {
                "group_id": row["group_id"],
                "qr_version": int(row["qr_version"]),
                "mask_pattern": int(row["mask_pattern"]),
                "quality_condition": row["quality_condition"],
                "p_structural": result.p_structural,
                "predicted_type": result.predicted_type,
            }
        )
        if index % 128 == 0 or index == len(rows):
            print(f"evaluated {index:,}/{len(rows):,}", flush=True)

    by_group: dict[str, list[dict]] = defaultdict(list)
    for row in predictions:
        by_group[row["group_id"]].append(row)
    group_summaries = []
    for group_id, group in by_group.items():
        probabilities = [row["p_structural"] for row in group]
        group_summaries.append(
            {
                "group_id": group_id,
                "qr_version": group[0]["qr_version"],
                "probability_min": min(probabilities),
                "probability_max": max(probabilities),
                "probability_span": max(probabilities) - min(probabilities),
            }
        )
    group_spans = [row["probability_span"] for row in group_summaries]

    def grouped_spans(keys: tuple[str, ...]) -> list[float]:
        buckets: dict[tuple[str, ...], list[float]] = defaultdict(list)
        for row in predictions:
            buckets[tuple(str(row[key]) for key in keys)].append(row["p_structural"])
        return [max(values) - min(values) for values in buckets.values()]

    within_condition_spans = grouped_spans(("group_id", "quality_condition"))
    within_mask_condition_spans = grouped_spans(("group_id", "mask_pattern"))

    def slice_fpr(key: str) -> dict[str, float]:
        buckets: dict[str, list[bool]] = defaultdict(list)
        for row in predictions:
            buckets[str(row[key])].append(row["predicted_type"] != "clean")
        return {
            name: float(np.mean(values))
            for name, values in sorted(buckets.items(), key=lambda item: item[0])
        }

    failures = [row for row in predictions if row["predicted_type"] != "clean"]
    model_path = artifacts / "structural_fp32.onnx"
    return {
        "schema_version": 1,
        "audit": "structural_topology_counterfactual_clean",
        "evidence_role": "development_counterfactual",
        "promotion_eligible": False,
        "manifest": manifest.relative_to(ROOT).as_posix(),
        "manifest_sha256": _sha256(manifest),
        "split": split,
        "model": {
            "version": analyzer.version,
            "artifact_sha256": _sha256(model_path),
            "temperature": analyzer.temperature,
        },
        "rows": len(predictions),
        "groups": len(by_group),
        "versions": sorted({row["qr_version"] for row in predictions}),
        "masks": sorted({row["mask_pattern"] for row in predictions}),
        "clean_false_positive_rate": float(len(failures) / len(predictions)),
        "clean_structural_probability_span_p95": float(
            np.percentile(group_spans, 95)
        ),
        "maximum_group_probability_span": float(max(group_spans)),
        "per_version_clean_false_positive_rate": slice_fpr("qr_version"),
        "per_mask_clean_false_positive_rate": slice_fpr("mask_pattern"),
        "per_condition_clean_false_positive_rate": slice_fpr("quality_condition"),
        "mask_probability_span_p95_within_condition": float(
            np.percentile(within_condition_spans, 95)
        ),
        "condition_probability_span_p95_within_mask": float(
            np.percentile(within_mask_condition_spans, 95)
        ),
        "worst_group_probability_spans": sorted(
            group_summaries,
            key=lambda row: row["probability_span"],
            reverse=True,
        )[:10],
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "validation"), default="validation")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate(
        args.manifest.resolve(strict=True),
        args.artifacts.resolve(strict=True),
        args.split,
    )
    rendered = json.dumps(report, indent=2)
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        print(f"wrote {output}")
    print(rendered)


if __name__ == "__main__":
    main()
