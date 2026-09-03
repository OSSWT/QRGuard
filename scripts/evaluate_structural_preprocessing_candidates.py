"""Screen source-neutral preprocessing candidates against old and new evidence.

This is a development experiment, not a runtime switch.  A transform must retain
the locked exact-app attack recalls while also removing the newly observed
low-Version clean false positives.  Results are written without QR payload text.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from structural.image_quality import assess_image_quality, normalize_measured_range
from structural.structural_service import StructuralAnalyzer

from scripts.analyze_live_camera_diagnostic import validate_archive
from scripts.audit_structural_qr_coverage import inspect_qr_reference

DEFAULT_ARCHIVE = ROOT / "QRGuard_Diagnostic_sem11_root_cause_screen_80.zip"
DEFAULT_PLAN = ROOT / "app/assets/capture/sem11_root_cause_capture_plan.json"
DEFAULT_MANIFEST = ROOT / "data/runtime_captures/manifest_v3.csv"
DEFAULT_RUNTIME_ROOT = ROOT / "data/runtime_captures"
DEFAULT_ARTIFACTS = ROOT / "training/artifacts/structural"
DEFAULT_OUTPUT = (
    ROOT
    / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r01/M4_PREPROCESSING_SCREEN"
)

Transform = Callable[[Image.Image, int], Image.Image]


def _identity(image: Image.Image, _: int) -> Image.Image:
    return image


def _grayscale(image: Image.Image, _: int) -> Image.Image:
    return ImageOps.grayscale(image).convert("RGB")


def _gaussian(radius: float) -> Transform:
    return lambda image, _: image.filter(ImageFilter.GaussianBlur(radius))


def _median(image: Image.Image, _: int) -> Image.Image:
    return image.filter(ImageFilter.MedianFilter(3))


def _lattice_box(image: Image.Image, module_count: int) -> Image.Image:
    # The app expands the detected QR boundary by 15% on every side.  Reducing
    # to about one sample per module plus that quiet zone tests whether averaging
    # screen subpixels removes moire.  Approximate alignment is deliberate: this
    # candidate must tolerate the real detector's corner error.
    side = round(module_count * 1.30)
    return image.resize((side, side), Image.Resampling.BOX).resize(
        image.size, Image.Resampling.BILINEAR
    )


def _gray_gaussian(image: Image.Image, _: int) -> Image.Image:
    return _grayscale(image, 0).filter(ImageFilter.GaussianBlur(0.75))


TRANSFORMS: dict[str, Transform] = {
    "baseline": _identity,
    "grayscale": _grayscale,
    "gaussian_0_75": _gaussian(0.75),
    "gaussian_1_25": _gaussian(1.25),
    "median_3": _median,
    "lattice_box": _lattice_box,
    "gray_gaussian_0_75": _gray_gaussian,
}


def apply_transform(
    image: Image.Image, module_count: int, transform: Transform
) -> Image.Image:
    quality = assess_image_quality(image)
    normalized = normalize_measured_range(image, quality)
    result = transform(normalized, module_count).convert("RGB")
    if result.size != image.size:
        raise ValueError("preprocessing candidate changed the deployment crop size")
    return result


def _runtime_rows(manifest: Path, runtime_root: Path) -> list[dict[str, Any]]:
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    test = [
        row
        for row in rows
        if row["split"] == "test" and row["is_authoritative"].lower() == "true"
    ]
    module_by_group: dict[str, int] = {}
    for row in test:
        if row["image_source"] != "gallery":
            continue
        module_by_group[row["paired_group"]] = inspect_qr_reference(
            runtime_root / row["sample_path"]
        )["module_count"]
    if len(module_by_group) != len([row for row in test if row["image_source"] == "gallery"]):
        raise ValueError("paired Gallery references are incomplete or duplicated")
    prepared = []
    for row in test:
        modules = module_by_group.get(row["paired_group"])
        if modules is None:
            raise ValueError(f"missing paired module count: {row['paired_group']}")
        prepared.append(
            {
                "sample_id": row["sample_path"],
                "label": row["label"],
                "image_source": row["image_source"],
                "module_count": modules,
                "image": Image.open(runtime_root / row["sample_path"]).convert("RGB"),
            }
        )
    return prepared


def _physical_rows(archive: Path, plan: Path) -> list[dict[str, Any]]:
    capture_plan = json.loads(plan.read_text(encoding="utf-8"))
    modules = {
        row["case_id"]: int(row["metadata"]["module_count"])
        for row in capture_plan["cases"]
    }
    masks = {
        row["case_id"]: int(row["metadata"]["mask_pattern"])
        for row in capture_plan["cases"]
    }
    families = {
        row["case_id"]: str(row["metadata"]["family"])
        for row in capture_plan["cases"]
    }
    return [
        {
            "sample_id": frame.crop_sha256,
            "case_id": frame.case_id,
            "label": "clean",
            "image_source": "camera",
            "module_count": modules[frame.case_id],
            "mask_pattern": masks[frame.case_id],
            "family": families[frame.case_id],
            "image": Image.open(io.BytesIO(frame.crop_png)).convert("RGB"),
        }
        for frame in validate_archive(archive, plan)
    ]


def _rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clean = [row for row in rows if row["label"] == "clean"]
    adversarial = [row for row in rows if row["label"] == "adversarial"]
    tampered = [row for row in rows if row["label"] == "tampered"]
    correct = sum(row["predicted_type"] == row["label"] for row in rows)
    return {
        "rows": len(rows),
        "accuracy": correct / len(rows) if rows else None,
        "clean_false_positive_rate": (
            sum(row["predicted_type"] != "clean" for row in clean) / len(clean)
            if clean
            else None
        ),
        "adversarial_recall": (
            sum(row["predicted_type"] == "adversarial" for row in adversarial)
            / len(adversarial)
            if adversarial
            else None
        ),
        "tampered_recall": (
            sum(row["predicted_type"] == "tampered" for row in tampered) / len(tampered)
            if tampered
            else None
        ),
        "predicted_types": dict(Counter(row["predicted_type"] for row in rows)),
    }


def evaluate(
    analyzer: StructuralAnalyzer,
    runtime: list[dict[str, Any]],
    physical: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates: dict[str, Any] = {}
    for name, transform in TRANSFORMS.items():
        scored_runtime = []
        scored_physical = []
        for source, destination in ((runtime, scored_runtime), (physical, scored_physical)):
            for row in source:
                prediction = analyzer.predict(
                    apply_transform(row["image"], row["module_count"], transform)
                )
                destination.append(
                    {
                        **{key: value for key, value in row.items() if key != "image"},
                        "predicted_type": prediction.predicted_type,
                        "p_structural": prediction.p_structural,
                    }
                )
        by_source = {
            source: _rates(
                [row for row in scored_runtime if row["image_source"] == source]
            )
            for source in ("camera", "gallery")
        }
        physical_scores = sorted(row["p_structural"] for row in scored_physical)
        case_scores: dict[str, list[float]] = defaultdict(list)
        for row in scored_physical:
            case_scores[row["case_id"]].append(float(row["p_structural"]))
        mask_medians = [
            statistics.median(values)
            for case_id, values in case_scores.items()
            if next(
                row["family"] for row in scored_physical if row["case_id"] == case_id
            )
            == "forced_mask"
        ]
        physical_fpr = sum(
            row["predicted_type"] != "clean" for row in scored_physical
        ) / len(scored_physical)
        passes = (
            by_source["camera"]["clean_false_positive_rate"] <= 0.05
            and by_source["camera"]["adversarial_recall"] >= 0.80
            and by_source["camera"]["tampered_recall"] >= 0.85
            and by_source["gallery"]["clean_false_positive_rate"] <= 0.05
            and by_source["gallery"]["adversarial_recall"] >= 0.80
            and by_source["gallery"]["tampered_recall"] >= 0.85
            and physical_fpr <= 0.05
            and max(mask_medians) - min(mask_medians) <= 0.15
        )
        candidates[name] = {
            "passes_all_screening_gates": passes,
            "locked_exact_app": {
                "overall": _rates(scored_runtime),
                "per_source": by_source,
            },
            "sem11_physical_clean": {
                "frames": len(scored_physical),
                "false_positive_rate": physical_fpr,
                "p_structural_median": statistics.median(physical_scores),
                "p_structural_p95": physical_scores[
                    max(0, (len(physical_scores) * 95 + 99) // 100 - 1)
                ],
                "forced_mask_case_median_span": max(mask_medians) - min(mask_medians),
            },
        }
        print(f"evaluated {name}", flush=True)
    return {
        "schema_version": 1,
        "evaluation": "development_preprocessing_screen",
        "runtime_rows": len(runtime),
        "physical_clean_frames": len(physical),
        "selection_gate": {
            "clean_false_positive_rate_max": 0.05,
            "camera_adversarial_recall_min": 0.80,
            "camera_tampered_recall_min": 0.85,
            "forced_mask_probability_span_max": 0.15,
        },
        "passing_candidates": [
            name
            for name, row in candidates.items()
            if row["passes_all_screening_gates"]
        ],
        "candidates": candidates,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Structural preprocessing candidate screen",
        "",
        (
            "No transform in this report changes the runtime. Promotion requires an "
            "independent holdout after any selected implementation."
        ),
        "",
        (
            "| Candidate | Physical clean FP | Physical mask span | Camera clean FP | "
            "Camera adv recall | Camera tamper recall | Pass |"
        ),
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, row in report["candidates"].items():
        physical = row["sem11_physical_clean"]
        camera = row["locked_exact_app"]["per_source"]["camera"]
        lines.append(
            f"| {name} | {physical['false_positive_rate']:.1%} | "
            f"{physical['forced_mask_case_median_span']:.3f} | "
            f"{camera['clean_false_positive_rate']:.1%} | "
            f"{camera['adversarial_recall']:.1%} | "
            f"{camera['tampered_recall']:.1%} | "
            f"{row['passes_all_screening_gates']} |"
        )
    lines.extend(
        [
            "",
            f"Passing candidates: `{report['passing_candidates']}`.",
            "",
            (
                "A transform that makes clean screen crops look normal but also removes "
                "adversarial or tampering evidence is rejected. If none passes, the next "
                "action is balanced retraining rather than a preprocessing override."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path, nargs="?", default=DEFAULT_ARCHIVE)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ["QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS"] = str(args.artifacts.resolve())
    runtime = _runtime_rows(args.manifest, args.runtime_root)
    physical = _physical_rows(args.archive, args.plan)
    report = evaluate(StructuralAnalyzer(args.artifacts), runtime, physical)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ANALYSIS.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "SUMMARY.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"passing_candidates": report["passing_candidates"]}, indent=2))


if __name__ == "__main__":
    main()
