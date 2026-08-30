"""Tests for structural.structural_service (EfficientNet-B0 3-class inference).

QR images are generated in-test with the `qrcode` library, so the tests need no
fixture files. Skipped automatically when the exported artifacts are absent.
"""

import numpy as np
import pytest
from structural.structural_service import (
    CLASS_NAMES,
    IMG_SIZE,
    ArtifactsNotFound,
    StructuralAnalyzer,
    load_analyzer,
    load_camera_analyzer,
)


@pytest.fixture(scope="module")
def analyzer():
    try:
        return load_analyzer()
    except (ArtifactsNotFound, ImportError) as exc:
        pytest.skip(f"Structural artifacts unavailable: {exc}")


@pytest.fixture(scope="module")
def camera_analyzer():
    try:
        return load_camera_analyzer()
    except (ArtifactsNotFound, ImportError) as exc:
        pytest.skip(f"Camera Structural artifacts unavailable: {exc}")


@pytest.fixture(scope="module")
def clean_qr():
    qrcode = pytest.importorskip("qrcode")
    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data("https://example.com/structural-test")
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


@pytest.fixture(scope="module")
def tampered_qr(clean_qr):
    """Sticker-overlay tampering — the most common real-world QR fraud."""
    from PIL import ImageDraw

    img = clean_qr.copy().resize((IMG_SIZE, IMG_SIZE))
    ImageDraw.Draw(img).rectangle([60, 60, 130, 130], fill=(220, 40, 40))
    return img


class TestLoading:
    def test_loads_fp32_model(self, analyzer):
        # INT8 was rejected for this CNN during training (accuracy collapse);
        # FP32 must be the deployed export.
        assert analyzer.model_path.exists()
        assert "fp32" in analyzer.model_path.name

    def test_temperature_comes_from_the_artifact(self, analyzer):
        """The service must use the temperature the training run calibrated.

        This used to pin RUN 1's 1.3921 literally, which turned every retrain
        into a test failure that said nothing about correctness — RUN 2
        calibrated to 1.1664 and the suite went red for a model that was working
        as intended. What actually has to hold is that the deployed temperature
        is the one in the artifact, and that it is a plausible scaling factor.
        """
        import json

        recorded = json.loads((analyzer.dir / "temperature.json").read_text())[
            "temperature"
        ]
        assert analyzer.temperature == pytest.approx(recorded, abs=1e-6)
        assert 0.0 < analyzer.temperature < 10.0

    def test_missing_artifacts_raise_clear_error(self, tmp_path):
        with pytest.raises(ArtifactsNotFound):
            StructuralAnalyzer(tmp_path / "does_not_exist")

    def test_load_analyzer_is_cached(self, analyzer):
        assert load_analyzer() is analyzer

    def test_camera_model_is_separate_and_cached(self, analyzer, camera_analyzer):
        assert camera_analyzer is load_camera_analyzer()
        assert camera_analyzer is not analyzer
        assert "structural-2026.02" in camera_analyzer.dir.as_posix()

    def test_camera_model_records_camera_clean_gate_result(self, camera_analyzer):
        import json

        metrics_path = (
            camera_analyzer.dir.parents[1]
            / "performance"
            / "structural-2026.02"
            / "metrics.json"
        )
        if not metrics_path.is_file():
            metrics_path = (
                camera_analyzer.dir.parents[2]
                / "performance"
                / "structural-2026.02"
                / "metrics.json"
            )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        camera_clean = metrics["qrdn_external_clean_holdout"]
        assert camera_clean["false_positive_rate_at_0_5"] <= 0.05
        assert (
            metrics["synthetic_grouped_test"]["per_class"]["adversarial"]["recall"]
            >= 0.80
        )


class TestPreprocessing:
    def test_output_shape_and_dtype(self, clean_qr):
        arr = StructuralAnalyzer.preprocess(clean_qr)
        assert arr.shape == (1, 3, IMG_SIZE, IMG_SIZE)
        assert arr.dtype == np.float32

    def test_normalisation_applied(self, clean_qr):
        # After ImageNet normalisation values must leave the raw [0,1] range.
        arr = StructuralAnalyzer.preprocess(clean_qr)
        assert arr.min() < 0.0
        assert arr.max() > 1.0

    def test_accepts_any_input_size(self, clean_qr):
        for size in [(64, 64), (500, 500), (300, 180)]:
            arr = StructuralAnalyzer.preprocess(clean_qr.resize(size))
            assert arr.shape == (1, 3, IMG_SIZE, IMG_SIZE)


class TestPredictions:
    def test_clean_qr_detected_as_clean(self, analyzer, clean_qr):
        r = analyzer.predict(clean_qr)
        assert r.predicted_type == "clean"
        assert r.p_structural == pytest.approx(1.0 - r.probs["clean"], abs=1e-6)
        assert r.p_structural < 0.5
        assert not r.is_manipulated

    def test_sticker_tampering_detected(self, analyzer, tampered_qr):
        r = analyzer.predict(tampered_qr)
        assert r.predicted_type == "tampered"
        assert r.p_structural > 0.9
        assert r.is_manipulated

    def test_probs_sum_to_one_over_three_classes(self, analyzer, clean_qr):
        r = analyzer.predict(clean_qr)
        assert set(r.probs) == set(CLASS_NAMES)
        assert sum(r.probs.values()) == pytest.approx(1.0, abs=1e-5)

    def test_p_structural_is_one_minus_clean(self, analyzer, tampered_qr):
        r = analyzer.predict(tampered_qr)
        assert r.p_structural == pytest.approx(1.0 - r.probs["clean"], abs=1e-6)

    def test_deterministic(self, analyzer, clean_qr):
        assert analyzer.predict(clean_qr).p_structural == (
            analyzer.predict(clean_qr).p_structural
        )

    def test_accepts_path_input(self, analyzer, clean_qr, tmp_path):
        p = tmp_path / "qr.png"
        clean_qr.save(p)
        assert analyzer.predict(p).predicted_type == "clean"
