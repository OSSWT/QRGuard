from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from ml_training.structural.src.evaluate_exported_v3 import score_manifest, summarize


def _checkerboard() -> Image.Image:
    values = np.indices((224, 224)).sum(axis=0) // 8 % 2 * 255
    rgb = np.repeat(values[:, :, None].astype(np.uint8), 3, axis=2)
    return Image.fromarray(rgb, mode="RGB")


def test_export_evaluation_abstains_before_model_and_keeps_pairs(tmp_path) -> None:
    _checkerboard().save(tmp_path / "gallery.png")
    _checkerboard().save(tmp_path / "camera.png")
    Image.new("RGB", (224, 224), (120, 120, 120)).save(tmp_path / "blurred.png")
    frame = pd.DataFrame(
        [
            {
                "sample_path": "gallery.png",
                "label": "clean",
                "quality_condition": "normal",
                "quality_severity": "none",
                "paired_group": "pair-a",
                "image_source": "gallery",
                "is_authoritative": True,
            },
            {
                "sample_path": "camera.png",
                "label": "clean",
                "quality_condition": "normal",
                "quality_severity": "none",
                "paired_group": "pair-a",
                "image_source": "camera",
                "is_authoritative": True,
            },
            {
                "sample_path": "blurred.png",
                "label": "clean",
                "quality_condition": "defocus_blur",
                "quality_severity": "severe",
                "paired_group": "pair-b",
                "image_source": "camera",
                "is_authoritative": True,
            },
        ]
    )

    class Analyzer:
        calls = 0

        def predict(self, _image):
            self.calls += 1
            return SimpleNamespace(
                p_structural=0.05,
                predicted_type="clean",
                probs={"clean": 0.95, "adversarial": 0.03, "tampered": 0.02},
            )

    analyzer = Analyzer()
    predictions = score_manifest(frame, tmp_path, analyzer)
    metrics, slices, pairs = summarize(predictions)

    assert analyzer.calls == 2
    assert predictions.predicted_type.tolist() == ["clean", "clean", "abstain"]
    assert metrics["overall"]["abstention_rate"] == pytest.approx(1 / 3)
    assert metrics["paired_gallery_camera"]["overall"]["verdict_agreement"] == 1.0
    assert len(pairs) == 1
    assert "quality_condition/defocus_blur" in set(slices["slice"])


def test_export_deployment_metrics_use_only_locked_test_split(tmp_path) -> None:
    _checkerboard().save(tmp_path / "train.png")
    _checkerboard().save(tmp_path / "test-gallery.png")
    _checkerboard().save(tmp_path / "test-camera.png")
    frame = pd.DataFrame(
        [
            {
                "sample_path": "train.png",
                "label": "clean",
                "quality_condition": "normal",
                "quality_severity": "none",
                "paired_group": "train-pair",
                "image_source": "camera",
                "is_authoritative": True,
                "split": "train",
            },
            {
                "sample_path": "test-gallery.png",
                "label": "clean",
                "quality_condition": "normal",
                "quality_severity": "none",
                "paired_group": "test-pair",
                "image_source": "gallery",
                "is_authoritative": True,
                "split": "test",
            },
            {
                "sample_path": "test-camera.png",
                "label": "clean",
                "quality_condition": "normal",
                "quality_severity": "none",
                "paired_group": "test-pair",
                "image_source": "camera",
                "is_authoritative": True,
                "split": "test",
            },
        ]
    )

    class Analyzer:
        calls = 0

        def predict(self, _image):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    p_structural=0.95,
                    predicted_type="tampered",
                    probs={"clean": 0.05, "adversarial": 0.05, "tampered": 0.90},
                )
            return SimpleNamespace(
                p_structural=0.05,
                predicted_type="clean",
                probs={"clean": 0.95, "adversarial": 0.03, "tampered": 0.02},
            )

    predictions = score_manifest(frame, tmp_path, Analyzer())
    metrics, slices, pairs = summarize(predictions)

    assert metrics["deployment_scope"] == "test"
    assert metrics["per_source"]["camera"]["clean_false_positive_rate"] == 0.0
    assert metrics["all_authoritative"]["overall"][
        "clean_false_positive_rate"
    ] == pytest.approx(1 / 3)
    assert metrics["paired_gallery_camera"]["overall"]["n"] == 1
    assert len(pairs) == 1
    assert set(slices["scope"]) == {"all_authoritative", "deployment_holdout"}
