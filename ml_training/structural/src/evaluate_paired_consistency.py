"""Evaluate one Structural artifact on paired Gallery and Camera predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {
    "paired_group",
    "image_source",
    "label",
    "p_clean",
    "p_adversarial",
    "p_tampered",
    "predicted_type",
}


def evaluate(frame: pd.DataFrame) -> tuple[dict[str, object], pd.DataFrame]:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"paired prediction columns missing: {', '.join(missing)}")
    if "is_authoritative" in frame:
        values = frame.is_authoritative
        if values.dtype == object:
            values = values.astype(str).str.lower().isin({"true", "1", "yes"})
        frame = frame[values.astype(bool)].copy()
    if not set(frame.image_source.unique()) <= {"gallery", "camera"}:
        raise ValueError("image_source must contain only gallery/camera")

    probabilities = frame[["p_clean", "p_adversarial", "p_tampered"]].to_numpy(
        dtype=float
    )
    if not np.isfinite(probabilities).all():
        raise ValueError("probabilities must be finite")
    if np.any(probabilities < 0) or np.any(probabilities > 1):
        raise ValueError("probabilities must be within [0, 1]")
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-4):
        raise ValueError("class probabilities must sum to one")

    duplicates = frame.duplicated(["paired_group", "image_source"], keep=False)
    if duplicates.any():
        groups = sorted(frame.loc[duplicates, "paired_group"].astype(str).unique())
        raise ValueError(f"multiple authoritative rows in paired groups: {groups[:3]}")

    gallery = frame[frame.image_source == "gallery"].set_index("paired_group")
    camera = frame[frame.image_source == "camera"].set_index("paired_group")
    common = sorted(set(gallery.index) & set(camera.index))
    if not common:
        raise ValueError("no complete Gallery/Camera pairs")

    rows = []
    for group in common:
        left = gallery.loc[group]
        right = camera.loc[group]
        if left.label != right.label:
            raise ValueError(f"paired label mismatch: {group}")
        gallery_score = 1.0 - float(left.p_clean)
        camera_score = 1.0 - float(right.p_clean)
        rows.append(
            {
                "paired_group": group,
                "label": left.label,
                "gallery_type": left.predicted_type,
                "camera_type": right.predicted_type,
                "gallery_p_structural": gallery_score,
                "camera_p_structural": camera_score,
                "absolute_probability_delta": abs(gallery_score - camera_score),
                "class_agreement": left.predicted_type == right.predicted_type,
                "verdict_agreement": (left.predicted_type == "clean")
                == (right.predicted_type == "clean"),
            }
        )
    paired = pd.DataFrame(rows)

    def block(part: pd.DataFrame) -> dict[str, object]:
        delta = part.absolute_probability_delta.to_numpy(dtype=float)
        return {
            "n": len(part),
            "class_agreement": float(part.class_agreement.mean()),
            "verdict_agreement": float(part.verdict_agreement.mean()),
            "mean_absolute_probability_delta": float(delta.mean()),
            "p95_absolute_probability_delta": float(np.percentile(delta, 95)),
        }

    metrics: dict[str, object] = {
        "overall": block(paired),
        "per_class": {
            label: block(part) for label, part in paired.groupby("label", sort=True)
        },
    }
    return metrics, paired


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    metrics, paired = evaluate(pd.read_csv(args.predictions))
    args.output.mkdir(parents=True, exist_ok=True)
    paired.to_csv(args.output / "gallery_camera_pairs.csv", index=False)
    (args.output / "gallery_camera_consistency.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
