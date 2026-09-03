from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
from structural.image_quality import assess_image_quality, normalize_measured_range
from structural.qr_decoder import estimate_qr_module_count

from app import pipeline


def _qr_like() -> Image.Image:
    image = Image.new("RGB", (224, 224), "white")
    pixels = image.load()
    for y in range(28, 196, 14):
        for x in range(28, 196, 14):
            if (x // 14 + y // 14) % 2:
                for yy in range(y, min(y + 14, 224)):
                    for xx in range(x, min(x + 14, 224)):
                        pixels[xx, yy] = (0, 0, 0)
    return image


def test_quality_measurement_never_returns_an_attack_label():
    report = assess_image_quality(_qr_like())

    assert report.status in {"usable", "marginal", "unusable"}
    assert not ({"adversarial", "tampered"} & set(report.conditions))


def test_blur_score_falls_for_a_blurred_qr():
    sharp = assess_image_quality(_qr_like())
    blurred = assess_image_quality(_qr_like().filter(ImageFilter.GaussianBlur(6)))

    assert blurred.laplacian_variance < sharp.laplacian_variance
    assert "blur" in blurred.conditions


def test_range_normalisation_is_source_neutral_and_improves_marginal_contrast():
    dim = ImageEnhance.Contrast(_qr_like()).enhance(0.35)
    before = assess_image_quality(dim)
    corrected = normalize_measured_range(dim, before)
    after = assess_image_quality(corrected)

    assert after.dynamic_range >= before.dynamic_range
    assert corrected.size == dim.size


def test_flat_image_requests_rescan_instead_of_calling_it_malicious():
    report = assess_image_quality(Image.new("RGB", (224, 224), (180, 180, 180)))

    assert report.status == "unusable"
    assert report.rescan_reason


def test_dense_but_full_range_qr_is_not_called_underexposed():
    image = Image.new("RGB", (224, 224), "black")
    for y in range(0, 224, 28):
        for x in range(0, 224, 28):
            if (x // 28 + y // 28) % 5 == 0:
                for yy in range(y, min(y + 28, 224)):
                    for xx in range(x, min(x + 28, 224)):
                        image.putpixel((xx, yy), (255, 255, 255))

    report = assess_image_quality(image)

    assert "underexposure" not in report.conditions


def test_decoded_straight_grid_reports_exact_qr_module_count():
    fixture = Path(__file__).parents[2] / "data" / "test_qrs" / "01_safe_google.png"

    assert estimate_qr_module_count(Image.open(fixture)) == 29


def test_flat_pixels_do_not_invent_a_qr_module_count():
    assert estimate_qr_module_count(Image.new("RGB", (300, 300), "white")) is None


def test_camera_module_scale_gate_is_version_aware(monkeypatch):
    monkeypatch.setattr(pipeline, "estimate_qr_module_count", lambda _: 73)
    frames = [Image.new("RGB", (400, 400), "white") for _ in range(3)]

    result = pipeline._analyse_images(
        frames,
        "camera",
        require_camera_consensus=True,
    )

    assert result.effective is None
    assert result.module_count == 73
    assert result.minimum_module_pixels is not None
    assert result.minimum_module_pixels < 5
    assert result.quality_conditions == ("insufficient_module_scale",)


def test_camera_module_scale_above_physical_floor_reaches_consensus(monkeypatch):
    monkeypatch.setattr(pipeline, "estimate_qr_module_count", lambda _: 73)
    monkeypatch.setattr(
        pipeline,
        "_analyse_one_image",
        lambda *_args, **_kwargs: pipeline.StructuralSignals(
            effective=0.01,
            raw_score=0.01,
            predicted_type="clean",
            manipulation_confidence=0.01,
            quality_status="usable",
            quality_conditions=("normal",),
            frames_received=1,
            frames_analyzed=1,
            consensus="single_frame",
        ),
    )
    frames = [Image.new("RGB", (480, 480), "white") for _ in range(3)]

    result = pipeline._analyse_images(
        frames,
        "camera",
        require_camera_consensus=True,
    )

    assert result.effective == 0.01
    assert result.module_count == 73
    assert result.minimum_module_pixels is not None
    assert result.minimum_module_pixels >= 5
