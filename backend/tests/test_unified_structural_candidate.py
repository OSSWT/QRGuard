from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from app.main import _structural_health_status, _structural_startup_loaders
from app.pipeline import _analyse_images, run_scan
from PIL import Image
from structural.structural_service import StructuralResult


def _high_contrast_qr_like() -> Image.Image:
    values = np.indices((224, 224)).sum(axis=0) // 8 % 2 * 255
    rgb = np.repeat(values[:, :, None].astype(np.uint8), 3, axis=2)
    return Image.fromarray(rgb, mode="RGB")


def test_health_reports_unified_candidate(monkeypatch, tmp_path: Path) -> None:
    artifacts = tmp_path / "structural-2026.03-r01" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "model_metadata.json").write_text(
        json.dumps({"version": "structural-2026.03-r01"}),
        encoding="utf-8",
    )

    class CandidateAnalyzer:
        model_path = artifacts / "structural_fp32.onnx"

    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", str(artifacts))
    monkeypatch.setattr(
        "structural.structural_service.load_unified_candidate_analyzer",
        lambda _path: CandidateAnalyzer(),
    )

    assert _structural_health_status() == (
        "unified=structural-2026.03-r01/structural_fp32.onnx; "
        "sources=gallery,camera"
    )


def test_startup_loads_only_the_unified_candidate(monkeypatch) -> None:
    loaded_paths = []

    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "structural.structural_service.load_unified_candidate_analyzer",
        lambda path: loaded_paths.append(path),
    )

    loaders = _structural_startup_loaders()

    assert [name for name, _loader in loaders] == ["structural-unified"]
    loaders[0][1]()
    assert loaded_paths == ["candidate/artifacts"]


def test_opt_in_candidate_uses_one_analyzer_for_gallery_and_camera(monkeypatch) -> None:
    loaded_paths = []

    class CandidateAnalyzer:
        def predict(self, _image):
            return StructuralResult(
                p_structural=0.08,
                predicted_type="clean",
                probs={"clean": 0.92, "adversarial": 0.05, "tampered": 0.03},
            )

    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda path=None: loaded_paths.append(path) or CandidateAnalyzer(),
    )
    image = _high_contrast_qr_like()

    gallery = _analyse_images([image], "gallery")
    camera = _analyse_images([image], "camera")

    assert loaded_paths == ["candidate/artifacts", "candidate/artifacts"]
    assert gallery.effective == camera.effective == 0.08
    assert gallery.predicted_type == camera.predicted_type == "clean"
    assert gallery.quality_status == camera.quality_status == "usable"


def test_opt_in_candidate_abstains_on_unusable_pixels(monkeypatch) -> None:
    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: (_ for _ in ()).throw(AssertionError("model must not run")),
    )

    result = _analyse_images([Image.new("RGB", (224, 224), (120, 120, 120))], "camera")

    assert result.effective is None
    assert result.predicted_type is None
    assert result.quality_status == "unusable"
    assert result.rescan_reason


def test_quality_abstention_is_warning_not_malicious_for_both_sources(
    monkeypatch,
) -> None:
    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    unusable = Image.new("RGB", (224, 224), (120, 120, 120))

    for source in ("gallery", "camera"):
        result = run_scan(
            "https://www.google.com/",
            images=[unusable],
            image_source=source,
            image_expected=True,
        )

        assert result.verdict == "warning"
        assert result.branch_scores.structural_status == "inconclusive"
        assert result.branch_scores.p_structural is None
        assert result.branch_scores.structural_type is None
        assert result.branch_scores.structural_quality_status == "unusable"
        assert result.branch_scores.structural_rescan_reason
        assert result.partial_analysis is True


def test_confirmed_candidate_manipulation_blocks_for_both_sources(monkeypatch) -> None:
    class CandidateAnalyzer:
        def predict(self, _image):
            return StructuralResult(
                p_structural=0.55,
                predicted_type="tampered",
                probs={"clean": 0.40, "adversarial": 0.05, "tampered": 0.55},
            )

    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: CandidateAnalyzer(),
    )
    image = _high_contrast_qr_like()

    for source in ("gallery", "camera"):
        result = run_scan(
            "https://www.google.com/",
            images=[image],
            image_source=source,
            image_expected=True,
        )

        assert result.verdict == "blocked"
        assert result.branch_scores.structural_status == "completed"
        assert result.branch_scores.structural_type == "tampered"
        assert "Structural model confirmed QR manipulation" in result.reasons
