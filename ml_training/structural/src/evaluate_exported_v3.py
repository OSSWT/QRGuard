"""Evaluate the exported Structural v3 runtime contract on exact app crops."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from structural.image_quality import (
    assess_image_quality,
    normalize_measured_range,
)
from structural.structural_service import StructuralAnalyzer

from ml_training.structural.src.evaluate_paired_consistency import (
    evaluate as evaluate_paired_consistency,
)

CLASS_NAMES = ("clean", "adversarial", "tampered")


def _truthy(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        return series.astype(str).str.lower().isin({"true", "1", "yes"})
    return series.astype(bool)


def score_manifest(frame: pd.DataFrame, capture_root: Path, analyzer) -> pd.DataFrame:
    """Run quality gating and one exported artifact without source routing."""
    required = {
        "sample_path",
        "label",
        "quality_condition",
        "quality_severity",
        "paired_group",
        "image_source",
        "is_authoritative",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"v3 capture columns missing: {', '.join(missing)}")
    frame = frame[_truthy(frame.is_authoritative)].reset_index(drop=True)
    rows = []
    for row in frame.itertuples(index=False):
        path = capture_root / str(row.sample_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        quality = assess_image_quality(image)
        output = row._asdict()
        output.update(
            {
                "measured_quality_status": quality.status,
                "measured_quality_conditions": "|".join(quality.conditions),
                "rescan_reason": quality.rescan_reason,
                "p_clean": np.nan,
                "p_adversarial": np.nan,
                "p_tampered": np.nan,
                "p_structural": np.nan,
                "predicted_type": "abstain",
            }
        )
        if quality.usable:
            result = analyzer.predict(normalize_measured_range(image, quality))
            output.update(
                {
                    "p_clean": result.probs["clean"],
                    "p_adversarial": result.probs["adversarial"],
                    "p_tampered": result.probs["tampered"],
                    "p_structural": result.p_structural,
                    "predicted_type": result.predicted_type,
                }
            )
        rows.append(output)
    if rows:
        return pd.DataFrame(rows)
    for column in (
        "measured_quality_status",
        "measured_quality_conditions",
        "rescan_reason",
        "p_clean",
        "p_adversarial",
        "p_tampered",
        "p_structural",
        "predicted_type",
    ):
        frame[column] = pd.Series(dtype="object")
    return frame


def _slice_metrics(frame: pd.DataFrame) -> dict[str, object]:
    usable = frame[frame.predicted_type != "abstain"]
    metrics: dict[str, object] = {
        "rows": len(frame),
        "usable_rows": len(usable),
        "abstention_rate": float(1 - len(usable) / len(frame)) if len(frame) else None,
        "accuracy_on_usable": (
            float((usable.predicted_type == usable.label).mean())
            if len(usable)
            else None
        ),
    }
    for class_name in CLASS_NAMES:
        part = usable[usable.label == class_name]
        if part.empty:
            value = None
        elif class_name == "clean":
            value = float((part.predicted_type != "clean").mean())
        else:
            value = float((part.predicted_type == class_name).mean())
        key = (
            "clean_false_positive_rate"
            if class_name == "clean"
            else f"{class_name}_recall"
        )
        metrics[key] = value
    return metrics


def summarize(
    predictions: pd.DataFrame,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    def block(frame: pd.DataFrame) -> tuple[dict[str, object], pd.DataFrame]:
        by_source = {
            str(source): _slice_metrics(part)
            for source, part in frame.groupby("image_source", sort=True)
        }
        usable = frame[frame.predicted_type != "abstain"].copy()
        paired_metrics = None
        paired_rows = pd.DataFrame()
        if not usable.empty:
            try:
                paired_metrics, paired_rows = evaluate_paired_consistency(usable)
            except ValueError:
                pass
        return (
            {
                "overall": _slice_metrics(frame),
                "per_source": by_source,
                "paired_gallery_camera": paired_metrics,
            },
            paired_rows,
        )

    all_authoritative, _ = block(predictions)
    if "split" in predictions:
        deployment_frame = predictions[
            predictions["split"].astype(str).str.lower() == "test"
        ].copy()
        deployment_scope = "test"
    else:
        # Backwards compatibility for small unit fixtures and historical
        # manifests that pre-date the locked split column.
        deployment_frame = predictions.copy()
        deployment_scope = "all_rows_no_split_column"
    deployment_holdout, paired_rows = block(deployment_frame)

    slices = []
    for scope, frame in (
        ("all_authoritative", predictions),
        ("deployment_holdout", deployment_frame),
    ):
        slices.append(
            {"scope": scope, "slice": "overall", **_slice_metrics(frame)}
        )
        for column in ("image_source", "quality_condition", "quality_severity"):
            for value, part in frame.groupby(column, sort=True):
                slices.append(
                    {
                        "scope": scope,
                        "slice": f"{column}/{value}",
                        **_slice_metrics(part),
                    }
                )

    # The legacy top-level keys intentionally point to the deployment holdout.
    # This keeps callers safe while the explicit all-authoritative diagnostics
    # remain available for error analysis.
    metrics: dict[str, object] = {
        **deployment_holdout,
        "deployment_scope": deployment_scope,
        "deployment_holdout": {
            "scope": deployment_scope,
            **deployment_holdout,
        },
        "all_authoritative": all_authoritative,
    }
    return metrics, pd.DataFrame(slices), paired_rows


def evaluate_export(
    artifacts: Path, manifest: Path, capture_root: Path, output: Path
) -> dict[str, object]:
    analyzer = StructuralAnalyzer(artifacts)
    predictions = score_manifest(pd.read_csv(manifest), capture_root, analyzer)
    metrics, slices, pairs = summarize(predictions)
    output.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output / "exported_runtime_predictions.csv", index=False)
    slices.to_csv(output / "quality_abstention_results.csv", index=False)
    if not pairs.empty:
        pairs.to_csv(output / "exported_gallery_camera_pairs.csv", index=False)
    paired_metrics = metrics["paired_gallery_camera"]
    if paired_metrics:
        paired_summary = [
            {"slice": "overall", **paired_metrics["overall"]},
            *(
                {"slice": f"class/{label}", **values}
                for label, values in paired_metrics["per_class"].items()
            ),
        ]
    else:
        paired_summary = [
            {
                "slice": "overall",
                "status": "not_evaluated",
                "reason": "no complete usable Gallery/Camera pairs",
            }
        ]
    pd.DataFrame(paired_summary).to_csv(
        output / "exported_gallery_camera_consistency.csv", index=False
    )
    (output / "exported_runtime_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    metrics = evaluate_export(
        args.artifacts, args.manifest, args.capture_root, args.output
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
