"""Print camera Structural scores under common acquisition conditions.

This is a deterministic local diagnostic. It does not write captures or contact
the deployed API, and it deliberately applies the same backend normalisation as
the live-camera path.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from importlib import import_module
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

_pipeline = import_module("app.pipeline")
_structural_service = import_module("structural.structural_service")
_normalize_camera_capture = _pipeline._normalize_camera_capture
load_analyzer = _structural_service.load_analyzer
load_camera_analyzer = _structural_service.load_camera_analyzer


def variants(image: Image.Image):
    rgb = image.convert("RGB")
    yield "normal", rgb
    yield "underexposed_045", ImageEnhance.Brightness(rgb).enhance(0.45)
    yield "underexposed_065", ImageEnhance.Brightness(rgb).enhance(0.65)
    yield "overexposed_135", ImageEnhance.Brightness(rgb).enhance(1.35)
    yield "overexposed_165", ImageEnhance.Brightness(rgb).enhance(1.65)
    yield "low_contrast_060", ImageEnhance.Contrast(rgb).enhance(0.60)
    yield "high_contrast_140", ImageEnhance.Contrast(rgb).enhance(1.40)
    yield "blur_080", rgb.filter(ImageFilter.GaussianBlur(0.80))
    yield "blur_150", rgb.filter(ImageFilter.GaussianBlur(1.50))


def _dataset_summary() -> None:
    analyzers = {
        "camera_candidate": load_camera_analyzer(),
        "gallery_stable": load_analyzer(),
    }
    datasets = {
        "synthetic_grouped_test": (
            ROOT
            / "ml_training/datasets/structural/processed/structural-2026.02/manifest.csv",
            "test",
        ),
        "qrdn_external_clean_holdout": (
            ROOT / "ml_training/datasets/structural/processed/qrdn/manifest.csv",
            "external_holdout_test",
        ),
    }
    if "--synthetic-only" in sys.argv:
        datasets = {"synthetic_grouped_test": datasets["synthetic_grouped_test"]}
    for dataset_name, (manifest, split) in datasets.items():
        rows = [
            row
            for row in csv.DictReader(manifest.open(newline="", encoding="utf-8"))
            if row["split"] == split
        ]
        totals = {"clean": 0, "attack": 0}
        positives = {
            "camera_candidate": {"clean": 0, "attack": 0},
            "gallery_stable": {"clean": 0, "attack": 0},
            "two_model_min": {"clean": 0, "attack": 0},
            "camera_tampered_or_consensus": {"clean": 0, "attack": 0},
        }
        disagreements = {"clean": 0, "attack": 0}
        disagreement_types: Counter[tuple[str, str, str]] = Counter()
        for row in rows:
            expected = "clean" if row["label"] == "clean" else "attack"
            totals[expected] += 1
            with Image.open(ROOT / row["path"]) as source:
                image = _normalize_camera_capture(source)
                results = {
                    name: analyzer.predict(image)
                    for name, analyzer in analyzers.items()
                }
                scores = {name: result.p_structural for name, result in results.items()}
            for name, score in scores.items():
                positives[name][expected] += int(score >= 0.5)
            positives["two_model_min"][expected] += int(min(scores.values()) >= 0.5)
            disagree = (scores["camera_candidate"] >= 0.5) != (
                scores["gallery_stable"] >= 0.5
            )
            disagreements[expected] += int(disagree)
            positives["camera_tampered_or_consensus"][expected] += int(
                results["camera_candidate"].predicted_type == "tampered"
                or min(scores.values()) >= 0.5
            )
            if disagree:
                disagreement_types[
                    (
                        row["label"],
                        results["camera_candidate"].predicted_type,
                        results["gallery_stable"].predicted_type,
                    )
                ] += 1

        print(dataset_name)
        print(f"  rows={len(rows)} clean={totals['clean']} attack={totals['attack']}")
        for name, counts in positives.items():
            clean_fpr = counts["clean"] / totals["clean"] if totals["clean"] else 0.0
            attack_recall = (
                counts["attack"] / totals["attack"] if totals["attack"] else 0.0
            )
            print(
                f"  {name}: clean_fpr={clean_fpr:.4f} attack_recall={attack_recall:.4f}"
            )
        print(
            "  disagreements: "
            f"clean={disagreements['clean']} attack={disagreements['attack']}"
        )
        for key, count in sorted(disagreement_types.items()):
            print(f"    {key[0]} camera={key[1]} gallery={key[2]}: {count}")


def _condition_matrix() -> None:
    analyzers = {
        "camera_candidate": load_camera_analyzer(),
        "gallery_stable": load_analyzer(),
    }
    samples = {
        "clean_google": ROOT / "data/test_qrs/01_safe_google.png",
        "clean_youtube": ROOT / "data/test_qrs/02_safe_youtube.png",
        "clean_utar": ROOT / "data/test_qrs/03_safe_utar.png",
        "adversarial": ROOT / "data/test_qrs/20_adversarial.png",
        "tampered_occlusion": ROOT / "data/test_qrs/08_tampered_occlusion.png",
    }
    print(
        "sample,condition,model,inference_view,p_structural,predicted_type,"
        "clean,adversarial,tampered"
    )
    for sample_name, path in samples.items():
        with Image.open(path) as source:
            for condition, image in variants(source):
                normalized = _normalize_camera_capture(image)
                inference_views = {
                    "preserving": normalized,
                    "softened_050": normalized.filter(ImageFilter.GaussianBlur(0.50)),
                    "softened_080": normalized.filter(ImageFilter.GaussianBlur(0.80)),
                }
                for model_name, analyzer in analyzers.items():
                    for view_name, inference_view in inference_views.items():
                        result = analyzer.predict(inference_view)
                        print(
                            f"{sample_name},{condition},{model_name},{view_name},"
                            f"{result.p_structural:.6f},{result.predicted_type},"
                            f"{result.probs['clean']:.6f},"
                            f"{result.probs['adversarial']:.6f},"
                            f"{result.probs['tampered']:.6f}"
                        )


if __name__ == "__main__":
    if "--dataset-summary" in sys.argv:
        _dataset_summary()
    else:
        _condition_matrix()
