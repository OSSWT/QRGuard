from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from app.main import _structural_health_status, _structural_startup_loaders
from app.pipeline import _analyse_images, run_scan
from PIL import Image
from structural.structural_service import (
    _UNIFIED_CANDIDATE_VERSION_PREFIXES,
    StructuralResult,
    load_unified_candidate_analyzer,
)


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
        "unified=structural-2026.03-r01/structural_fp32.onnx; sources=gallery,camera"
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


def test_stable_r07_corrective_version_is_a_supported_unified_candidate() -> None:
    assert "structural-r07-corrective-v1".startswith(
        _UNIFIED_CANDIDATE_VERSION_PREFIXES
    )


def test_coverage_candidate_uses_the_existing_unified_contract(
    monkeypatch, tmp_path: Path
) -> None:
    artifacts = tmp_path / "structural-2026.09-r01" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "model_metadata.json").write_text(
        json.dumps({"version": "structural-2026.09-r01"}), encoding="utf-8"
    )
    sentinel = object()
    monkeypatch.setattr(
        "structural.structural_service.load_analyzer", lambda _path: sentinel
    )

    assert load_unified_candidate_analyzer(str(artifacts)) is sentinel


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


def test_clean_image_with_undecodable_payload_requests_rescan(monkeypatch) -> None:
    class CandidateAnalyzer:
        def predict(self, _image):
            return StructuralResult(
                p_structural=0.01,
                predicted_type="clean",
                probs={"clean": 0.99, "adversarial": 0.005, "tampered": 0.005},
            )

    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: CandidateAnalyzer(),
    )
    monkeypatch.setattr("structural.qr_decoder.decode_qr", lambda _image: None)

    for source in ("gallery", "camera"):
        result = run_scan(
            images=[_high_contrast_qr_like()],
            image_source=source,
            image_expected=True,
        )

        assert result.payload_source == "undecodable"
        assert result.branch_scores.structural_status == "completed"
        assert result.branch_scores.structural_type == "clean"
        assert result.verdict == "warning"
        assert result.partial_analysis is True
        assert any("could not be decoded" in reason for reason in result.reasons)


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


def test_candidate_camera_boundary_prediction_requests_rescan(monkeypatch) -> None:
    class CandidateAnalyzer:
        camera_definitive_manipulation_floor = 0.70

        def predict(self, _image):
            return StructuralResult(
                p_structural=0.62,
                predicted_type="adversarial",
                probs={"clean": 0.38, "adversarial": 0.60, "tampered": 0.02},
            )

    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: CandidateAnalyzer(),
    )
    images = [_high_contrast_qr_like().resize((300, 300)) for _ in range(3)]

    result = run_scan(
        "plain text",
        images=images,
        image_source="camera",
        image_expected=True,
        require_camera_consensus=True,
    )

    branch = result.branch_scores
    assert result.verdict == "warning"
    assert result.partial_analysis is True
    assert branch.structural_status == "inconclusive"
    assert branch.p_structural is None
    assert branch.p_structural_raw == 0.62
    assert branch.structural_type is None
    assert branch.structural_frames_analyzed == 3
    assert branch.structural_consensus == "insufficient_confidence"
    assert "uncertain_structural_prediction" in branch.structural_quality_conditions
    assert branch.structural_rescan_reason


def test_candidate_uncertainty_floor_does_not_weaken_gallery_or_clear_attack(
    monkeypatch,
) -> None:
    class CandidateAnalyzer:
        camera_definitive_manipulation_floor = 0.70

        def __init__(self, score: float):
            self.score = score

        def predict(self, _image):
            return StructuralResult(
                p_structural=self.score,
                predicted_type="tampered",
                probs={
                    "clean": 1 - self.score,
                    "adversarial": 0.01,
                    "tampered": self.score - 0.01,
                },
            )

    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    image = _high_contrast_qr_like().resize((300, 300))

    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: CandidateAnalyzer(0.62),
    )
    gallery = run_scan(
        "plain text", images=[image], image_source="gallery", image_expected=True
    )
    assert gallery.verdict == "blocked"
    assert gallery.branch_scores.structural_type == "tampered"

    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: CandidateAnalyzer(0.71),
    )
    camera = run_scan(
        "plain text",
        images=[image.copy() for _ in range(3)],
        image_source="camera",
        image_expected=True,
        require_camera_consensus=True,
    )
    assert camera.verdict == "blocked"
    assert camera.branch_scores.structural_status == "completed"
    assert camera.branch_scores.structural_type == "tampered"


def test_camera_consensus_rejects_two_manipulated_outliers(monkeypatch) -> None:
    class CandidateAnalyzer:
        def predict(self, image):
            marker = image.convert("RGB").getpixel((0, 0))[0]
            manipulated = marker in {249, 247}
            return StructuralResult(
                p_structural=0.95 if manipulated else 0.08,
                predicted_type="adversarial" if manipulated else "clean",
                probs={
                    "clean": 0.05 if manipulated else 0.92,
                    "adversarial": 0.93 if manipulated else 0.05,
                    "tampered": 0.02 if manipulated else 0.03,
                },
            )

    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: CandidateAnalyzer(),
    )
    images = []
    for index in range(5):
        image = _high_contrast_qr_like().resize((300, 300))
        image.putpixel((0, 0), (250 - index, 250 - index, 250 - index))
        images.append(image)

    result = _analyse_images(images, "camera")

    assert result.predicted_type == "clean"
    assert result.confirmed_manipulation is False
    assert result.effective == 0.08
    assert result.frames_received == 5
    assert result.frames_analyzed == 5
    assert result.consensus == "median_score_majority_class"


def test_camera_consensus_requires_three_deployment_scale_crops(monkeypatch) -> None:
    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: (_ for _ in ()).throw(AssertionError("model must not run")),
    )
    images = [_high_contrast_qr_like().resize((180, 180)) for _ in range(5)]

    result = _analyse_images(images, "camera")

    assert result.effective is None
    assert result.quality_status == "unusable"
    assert result.quality_conditions == ("small_camera_crop",)
    assert result.frames_received == 5
    assert result.frames_analyzed == 0
    assert result.consensus == "insufficient_quality"


def test_declared_temporal_camera_never_falls_back_to_one_frame(monkeypatch) -> None:
    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: (_ for _ in ()).throw(AssertionError("model must not run")),
    )

    result = run_scan(
        payload="plain text",
        images=[_high_contrast_qr_like().resize((320, 320))],
        image_source="camera",
        image_expected=True,
        require_camera_consensus=True,
    )

    assert result.verdict == "warning"
    assert result.branch_scores.p_structural is None
    assert result.branch_scores.structural_status == "inconclusive"
    assert result.branch_scores.structural_frames_received == 1
    assert result.branch_scores.structural_consensus == "insufficient_quality"


def test_declared_temporal_camera_with_no_frames_is_an_inconclusive_rescan() -> None:
    result = run_scan(
        payload="plain text",
        images=[],
        image_source="camera",
        image_expected=True,
        require_camera_consensus=True,
    )

    assert result.verdict == "warning"
    assert result.branch_scores.p_structural is None
    assert result.branch_scores.structural_status == "inconclusive"
    assert result.branch_scores.structural_frames_received == 0
    assert result.branch_scores.structural_consensus == "insufficient_quality"


def test_recoverable_camera_overexposure_is_range_corrected(monkeypatch) -> None:
    observed = {}

    class CandidateAnalyzer:
        def predict(self, image):
            values = np.asarray(image.convert("L"))
            observed["range"] = int(values.max()) - int(values.min())
            return StructuralResult(
                p_structural=0.04,
                predicted_type="clean",
                probs={"clean": 0.96, "adversarial": 0.03, "tampered": 0.01},
            )

    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "candidate/artifacts")
    monkeypatch.setattr(
        "app.pipeline.load_unified_candidate_analyzer",
        lambda _path=None: CandidateAnalyzer(),
    )
    source = np.asarray(_high_contrast_qr_like().resize((300, 300)), dtype=np.float32)
    overexposed = Image.fromarray(
        np.clip(source * 0.38 + 155, 0, 255).astype(np.uint8),
        mode="RGB",
    )

    result = _analyse_images([overexposed], "camera")

    assert result.effective == 0.04
    assert result.quality_status == "marginal"
    assert "overexposure" in result.quality_conditions
    assert "range_corrected" in result.quality_conditions
    assert observed["range"] >= 200
