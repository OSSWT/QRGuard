"""Tests for the FastAPI endpoints (in-process, no server needed)."""

import io
import json
from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient
from fusion.engine import load_engine
from fusion.features import BranchInputs
from structural.structural_service import StructuralResult

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def qr_png():
    qrcode = pytest.importorskip("qrcode")
    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data("https://www.google.com/maps")
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").convert("RGB").save(
        buf, "PNG"
    )
    return buf.getvalue()


@pytest.fixture(scope="module")
def tampered_png(qr_png):
    from PIL import Image, ImageDraw

    img = Image.open(io.BytesIO(qr_png)).convert("RGB").resize((224, 224))
    ImageDraw.Draw(img).rectangle([60, 60, 130, 130], fill=(220, 40, 40))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def camera_clean_png():
    """One held-out genuine camera-derived clean QR used by the camera model."""
    import csv

    manifest = ROOT / "ml_training/datasets/structural/processed/qrdn/manifest.csv"
    if not manifest.is_file():
        pytest.skip("QR-DN camera holdout is not installed")
    with manifest.open(newline="", encoding="utf-8") as source:
        row = next(
            (
                item
                for item in csv.DictReader(source)
                if item["split"] == "external_holdout_test"
            ),
            None,
        )
    if row is None:
        pytest.skip("QR-DN camera holdout has no test row")
    path = ROOT / row["path"]
    if not path.is_file():
        pytest.skip("QR-DN camera holdout images are not installed")
    return path.read_bytes()


@pytest.fixture(scope="module")
def adversarial_png():
    return (ROOT / "data/test_qrs/20_adversarial.png").read_bytes()


def _pixel_distinct_pngs(source: bytes, count: int) -> list[bytes]:
    """Camera-like independent frames with an irrelevant quiet-zone pixel change."""
    from PIL import Image

    variants = []
    for index in range(count):
        image = Image.open(io.BytesIO(source)).convert("RGB")
        image.putpixel((index, 0), (250 - index, 250 - index, 250 - index))
        output = io.BytesIO()
        image.save(output, "PNG")
        variants.append(output.getvalue())
    return variants


def _conditioned_fixture(
    filename: str, *, brightness: float = 1.0, blur: float = 0.0
) -> bytes:
    """Apply deterministic camera-like acquisition conditions to a fixture."""
    from PIL import Image, ImageEnhance, ImageFilter

    image = Image.open(ROOT / "data/test_qrs" / filename).convert("RGB")
    if brightness != 1.0:
        image = ImageEnhance.Brightness(image).enhance(brightness)
    if blur > 0:
        image = image.filter(ImageFilter.GaussianBlur(blur))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


class TestHealth:
    def test_health_reports_all_components(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert set(body["components"]) == {
            "structural",
            "semantic",
            "fusion",
            "domain_list",
            "deep_check",
        }

    def test_deep_check_absence_does_not_degrade_status(self, client):
        # Method 2 is optional by design (option E), so an unconfigured provider
        # must not make the whole service look unhealthy.
        body = client.get("/health").json()
        if any(
            v.startswith("unavailable")
            for k, v in body["components"].items()
            if k != "deep_check"
        ):
            pytest.skip("model artifacts not installed")
        assert body["status"] == "ok"

    def test_status_ok_when_artifacts_present(self, client):
        body = client.get("/health").json()
        if any(v.startswith("unavailable") for v in body["components"].values()):
            pytest.skip("model artifacts not installed")
        assert body["status"] == "ok"


class TestCors:
    def test_local_flutter_web_origin_is_allowed(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:53000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "http://127.0.0.1:53000"
        )


class TestAnalyzeUrl:
    def test_benign_url_is_safe(self, client):
        r = client.post("/analyze-url", json={"payload": "https://www.google.com/maps"})
        assert r.status_code == 200
        body = r.json()
        assert body["verdict"] == "safe"
        assert body["registered_domain"] == "google.com"
        assert body["branch_scores"]["domain_unknown"] == 0.0
        assert body["reasons"] == []

    def test_phishing_url_is_blocked_with_reasons(self, client):
        r = client.post(
            "/analyze-url",
            json={"payload": "http://maybank2u-verify.xyz/login/update.php"},
        )
        body = r.json()
        assert body["verdict"] == "blocked"
        assert body["risk_score"] >= 55
        assert body["reasons"]
        assert "suspicious_tld" in body["rule_flags"]
        assert body["branch_scores"]["domain_unknown"] == 1.0

    def test_semantic_only_endpoint_is_complete_for_its_declared_scope(self, client):
        body = client.post(
            "/analyze-url", json={"payload": "https://www.google.com/maps"}
        ).json()
        assert body["partial_analysis"] is False
        assert body["branch_scores"]["p_structural"] is None
        assert body["branch_scores"]["structural_status"] == "not_applicable"
        assert body["branch_scores"]["semantic_status"] == "completed"

    def test_non_url_payload_abstains_semantically(self, client):
        body = client.post(
            "/analyze-url", json={"payload": "WIFI:T:nopass;S:FreeWifi;;"}
        ).json()
        assert body["payload_type"] == "wifi"
        assert body["branch_scores"]["p_url"] is None
        assert "open_wifi_network" in body["rule_flags"]
        assert body["verdict"] == "warning"
        assert body["risk_score"] == load_engine().safe_max
        assert body["partial_analysis"] is False
        assert body["branch_scores"]["semantic_status"] == "not_applicable"

    def test_valid_duitnow_is_payment_not_partial(self, client):
        payload = (
            "00020201021126410014A000000615000101065016640209123456789"
            "520400005303458540510.005802MY5909AUSERNAME6005BANGI63043A23"
        )
        body = client.post("/analyze-url", json={"payload": payload}).json()
        assert body["payload_type"] == "payment"
        assert body["branch_scores"]["semantic_status"] == "not_applicable"
        assert body["partial_analysis"] is False

    def test_empty_payload_rejected(self, client):
        assert client.post("/analyze-url", json={"payload": "   "}).status_code == 422

    def test_deep_check_offered_only_when_not_safe(self, client):
        safe = client.post(
            "/analyze-url", json={"payload": "https://www.google.com/maps"}
        ).json()
        risky = client.post(
            "/analyze-url", json={"payload": "http://maybank2u-verify.xyz/login"}
        ).json()
        assert safe["deep_check_available"] is False
        assert risky["deep_check_available"] is True


class TestScan:
    def test_clean_image_benign_url_is_safe(self, client, qr_png):
        r = client.post(
            "/scan",
            data={"payload": "https://www.google.com/maps"},
            files={"image": ("qr.png", qr_png, "image/png")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["verdict"] == "safe"
        assert body["branch_scores"]["structural_type"] == "clean"
        assert body["partial_analysis"] is False

    def test_tampered_image_blocks_even_with_benign_url(self, client, tampered_png):
        # the semantic branch sees a perfectly good link; only the image betrays it
        body = client.post(
            "/scan",
            data={"payload": "https://www.google.com/maps"},
            files={"image": ("qr.png", tampered_png, "image/png")},
        ).json()
        assert body["verdict"] == "blocked"
        assert body["branch_scores"]["structural_type"] == "tampered"
        assert any("image" in reason.lower() for reason in body["reasons"])

    def test_camera_adversarial_score_enters_fusion(self, client, qr_png, monkeypatch):
        class BoundaryAnalyzer:
            def predict(self, _image):
                return StructuralResult(
                    p_structural=0.59,
                    predicted_type="adversarial",
                    probs={"clean": 0.41, "adversarial": 0.45, "tampered": 0.14},
                )

        monkeypatch.setattr(
            "app.pipeline.load_camera_structural", lambda: BoundaryAnalyzer()
        )
        monkeypatch.setattr("app.pipeline.load_structural", lambda: BoundaryAnalyzer())
        body = client.post(
            "/scan",
            data={
                "payload": "http://xn--pypal-4ve.com/signin",
                "image_source": "camera",
            },
            files=[
                ("images", (f"qr-{index}.png", frame, "image/png"))
                for index, frame in enumerate(_pixel_distinct_pngs(qr_png, 3))
            ],
        ).json()

        assert body["branch_scores"]["structural_type"] == "adversarial"
        assert body["branch_scores"]["p_structural_raw"] == pytest.approx(0.59)
        assert body["branch_scores"]["p_structural"] == pytest.approx(0.59)
        assert body["branch_scores"]["image_source"] == "camera"
        assert "structural_consensus" not in body["branch_scores"]
        assert body["verdict"] == "blocked"

    def test_camera_clean_class_uses_strongest_competing_score(
        self, client, qr_png, monkeypatch
    ):
        class BoundaryAnalyzer:
            def predict(self, _image):
                return StructuralResult(
                    p_structural=0.527,
                    predicted_type="clean",
                    probs={"clean": 0.473, "adversarial": 0.40, "tampered": 0.127},
                )

        monkeypatch.setattr(
            "app.pipeline.load_camera_structural", lambda: BoundaryAnalyzer()
        )
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files=[
                ("images", (f"qr-{index}.png", frame, "image/png"))
                for index, frame in enumerate(_pixel_distinct_pngs(qr_png, 3))
            ],
        ).json()

        assert body["branch_scores"]["p_structural_raw"] == pytest.approx(0.527)
        assert body["branch_scores"]["p_structural"] == pytest.approx(0.40)
        assert body["verdict"] == "safe"
        assert body["partial_analysis"] is False

    @pytest.mark.parametrize("source", ["camera", "gallery"])
    def test_image_scan_source_requires_image_evidence(self, client, source):
        response = client.post(
            "/scan",
            data={
                "payload": "https://www.utar.edu.my/",
                "image_source": source,
            },
        )

        assert response.status_code == 422
        assert "valid QR image evidence" in response.json()["detail"]

    def test_camera_rejects_an_unreadable_image_instead_of_returning_partial(
        self, client
    ):
        response = client.post(
            "/scan",
            data={
                "payload": "https://www.utar.edu.my/",
                "image_source": "camera",
            },
            files={"image": ("bad.jpg", b"not an image", "image/jpeg")},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "camera image could not be decoded"

    def test_gallery_keeps_continuous_structural_score(self, client, qr_png):
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "gallery",
            },
            files={"image": ("qr.png", qr_png, "image/png")},
        ).json()

        assert body["branch_scores"]["p_structural"] == pytest.approx(
            body["branch_scores"]["p_structural_raw"]
        )
        assert body["branch_scores"]["image_source"] == "gallery"

    def test_web_gallery_file_is_decoded_and_cropped_server_side(self, client, qr_png):
        from PIL import Image

        qr = Image.open(io.BytesIO(qr_png)).convert("RGB").resize((260, 260))
        selected = Image.new("RGB", (1000, 700), (225, 220, 210))
        selected.paste(qr, (610, 260))
        encoded = io.BytesIO()
        selected.save(encoded, "PNG")

        body = client.post(
            "/scan",
            data={"image_source": "gallery"},
            files={"image": ("selected.png", encoded.getvalue(), "image/png")},
        ).json()

        assert body["payload_source"] == "decoded"
        assert body["payload"] == "https://www.google.com/maps"
        assert body["registered_domain"] == "google.com"
        assert body["branch_scores"]["structural_type"] == "clean"
        assert body["verdict"] == "safe"
        assert body["partial_analysis"] is False

    def test_web_gallery_file_without_qr_returns_actionable_error(self, client):
        from PIL import Image

        selected = Image.new("RGB", (800, 600), (230, 230, 230))
        encoded = io.BytesIO()
        selected.save(encoded, "PNG")

        response = client.post(
            "/scan",
            data={"image_source": "gallery"},
            files={"image": ("blank.png", encoded.getvalue(), "image/png")},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == (
            "No readable QR code was found in that image"
        )

    def test_camera_disagreement_uses_stable_clean_second_opinion(
        self, client, qr_png, monkeypatch
    ):
        class GalleryAnalyzer:
            def predict(self, _image):
                return StructuralResult(
                    p_structural=0.05,
                    predicted_type="clean",
                    probs={"clean": 0.95, "adversarial": 0.03, "tampered": 0.02},
                )

        class CameraAnalyzer:
            def predict(self, _image):
                return StructuralResult(
                    p_structural=0.93,
                    predicted_type="tampered",
                    probs={"clean": 0.07, "adversarial": 0.03, "tampered": 0.90},
                )

        monkeypatch.setattr("app.pipeline.load_structural", lambda: GalleryAnalyzer())
        monkeypatch.setattr(
            "app.pipeline.load_camera_structural", lambda: CameraAnalyzer()
        )
        results = {}
        for source in ("gallery", "camera"):
            results[source] = client.post(
                "/scan",
                data={
                    "payload": "https://www.google.com/maps",
                    "image_source": source,
                },
                files={"image": ("qr.png", qr_png, "image/png")},
            ).json()

        assert results["gallery"]["branch_scores"]["p_structural"] == 0.05
        assert results["camera"]["branch_scores"]["p_structural_raw"] == 0.93
        assert results["camera"]["branch_scores"]["p_structural"] == 0.03
        assert results["camera"]["branch_scores"]["structural_type"] == "clean"
        assert results["gallery"]["verdict"] == "safe"
        assert results["camera"]["verdict"] == "safe"

    def test_camera_exposure_is_normalized_before_inference(
        self, client, qr_png, monkeypatch
    ):
        from PIL import ImageStat

        observed = {}

        class ExposureAnalyzer:
            def predict(self, image):
                observed["extrema"] = ImageStat.Stat(image.convert("L")).extrema[0]
                return StructuralResult(
                    p_structural=0.08,
                    predicted_type="clean",
                    probs={"clean": 0.92, "adversarial": 0.05, "tampered": 0.03},
                )

        from PIL import Image, ImageEnhance

        dim = ImageEnhance.Brightness(Image.open(io.BytesIO(qr_png))).enhance(0.5)
        encoded = io.BytesIO()
        dim.save(encoded, "PNG")
        monkeypatch.setattr(
            "app.pipeline.load_camera_structural", lambda: ExposureAnalyzer()
        )

        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files={"image": ("dim.png", encoded.getvalue(), "image/png")},
        ).json()

        assert observed["extrema"][0] <= 10
        assert observed["extrema"][1] >= 240
        assert body["verdict"] == "safe"

    def test_hihive_camera_token_is_warning_not_blocked(
        self, client, qr_png, monkeypatch
    ):
        class ProjectorLogoAnalyzer:
            def predict(self, _image):
                return StructuralResult(
                    p_structural=0.98,
                    predicted_type="tampered",
                    probs={"clean": 0.02, "adversarial": 0.01, "tampered": 0.97},
                )

        monkeypatch.setattr(
            "app.pipeline.load_camera_structural", lambda: ProjectorLogoAnalyzer()
        )
        token = (
            "Q01:*:PACkNWVoPGvQQJ0Htc32cjZdTi+na5wHs0CB9rCOeg34g41pKQdYzMgrwZOV"
            "qjZeYyQ4SLPlONzsyH+m6fku+yLQK1V/jFB4cQJp85G0JgI="
        )

        body = client.post(
            "/scan",
            data={"payload": token, "image_source": "camera"},
            files={"image": ("hihive.png", qr_png, "image/png")},
        ).json()

        assert body["payload_type"] == "attendance"
        assert body["verdict"] == "warning"
        assert body["risk_score"] == load_engine().safe_max
        assert body["partial_analysis"] is False
        assert any("official app" in reason for reason in body["reasons"])

    def test_camera_model_accepts_real_camera_clean_google(
        self, client, camera_clean_png
    ):
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files={"image": ("camera-clean.jpg", camera_clean_png, "image/jpeg")},
        ).json()

        assert body["branch_scores"]["structural_type"] == "clean"
        assert body["branch_scores"]["p_structural"] < 0.5
        assert body["verdict"] == "safe"

    @pytest.mark.parametrize(
        ("filename", "payload"),
        [
            ("01_safe_google.png", "https://www.google.com/maps"),
            (
                "02_safe_youtube.png",
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            ),
            ("03_safe_utar.png", "https://www.utar.edu.my/"),
            ("10_tampered_blur.png", "https://www.google.com/maps"),
        ],
    )
    def test_camera_reference_safe_cases(self, client, filename, payload):
        image = (ROOT / "data" / "test_qrs" / filename).read_bytes()
        body = client.post(
            "/scan",
            data={"payload": payload, "image_source": "camera"},
            files={"image": (filename, image, "image/png")},
        ).json()

        assert body["registered_domain"] in {
            "google.com",
            "youtube.com",
            "utar.edu.my",
        }
        assert body["branch_scores"]["structural_type"] == "clean"
        assert body["verdict"] == "safe"
        assert body["partial_analysis"] is False

    @pytest.mark.parametrize(
        ("filename", "payload", "brightness", "blur"),
        [
            ("01_safe_google.png", "https://www.google.com/maps", 1.35, 0.0),
            ("01_safe_google.png", "https://www.google.com/maps", 1.65, 0.0),
            ("01_safe_google.png", "https://www.google.com/maps", 1.00, 0.8),
            ("02_safe_youtube.png", "https://www.youtube.com/", 0.45, 0.0),
            ("02_safe_youtube.png", "https://www.youtube.com/", 1.65, 0.0),
            ("03_safe_utar.png", "https://www.utar.edu.my/", 0.65, 0.0),
            ("03_safe_utar.png", "https://www.utar.edu.my/", 1.65, 0.0),
        ],
    )
    def test_camera_environment_does_not_turn_clean_qr_into_warning(
        self, client, filename, payload, brightness, blur
    ):
        image = _conditioned_fixture(filename, brightness=brightness, blur=blur)
        body = client.post(
            "/scan",
            data={"payload": payload, "image_source": "camera"},
            files={"image": (filename, image, "image/png")},
        ).json()

        assert body["branch_scores"]["structural_type"] == "clean"
        assert body["verdict"] == "safe"
        assert body["partial_analysis"] is False

    @pytest.mark.parametrize(
        ("filename", "payload"),
        [
            ("07_tampered_sticker.png", "https://www.google.com/maps"),
            ("08_tampered_occlusion.png", "https://www.youtube.com/"),
            ("09_tampered_finder.png", "https://www.google.com/"),
            ("20_adversarial.png", "https://www.google.com/maps"),
        ],
    )
    @pytest.mark.parametrize("brightness", [1.0, 1.35])
    def test_camera_model_agreement_keeps_real_attacks_blocked(
        self, client, filename, payload, brightness
    ):
        image = _conditioned_fixture(filename, brightness=brightness)
        body = client.post(
            "/scan",
            data={"payload": payload, "image_source": "camera"},
            files={"image": (filename, image, "image/png")},
        ).json()

        assert body["branch_scores"]["structural_type"] in {
            "adversarial",
            "tampered",
        }
        assert body["branch_scores"]["p_structural"] > 0.5
        assert body["verdict"] == "blocked"

    def test_camera_model_keeps_verified_duitnow_complete(
        self, client, camera_clean_png
    ):
        payload = (
            "00020201021126410014A000000615000101065016640209123456789"
            "520400005303458540510.005802MY5909AUSERNAME6005BANGI63043A23"
        )
        body = client.post(
            "/scan",
            data={"payload": payload, "image_source": "camera"},
            files={"image": ("camera-clean.jpg", camera_clean_png, "image/jpeg")},
        ).json()

        assert body["payload_type"] == "payment"
        assert body["branch_scores"]["structural_type"] == "clean"
        assert body["branch_scores"]["semantic_status"] == "not_applicable"
        assert body["partial_analysis"] is False
        assert body["verdict"] != "blocked"

    def test_verified_duitnow_can_be_checked_when_camera_image_is_suspicious(
        self, client, qr_png, monkeypatch
    ):
        class NoisyPaymentAnalyzer:
            def predict(self, _image):
                return StructuralResult(
                    p_structural=0.99,
                    predicted_type="tampered",
                    probs={"clean": 0.01, "adversarial": 0.04, "tampered": 0.95},
                )

        monkeypatch.setattr(
            "app.pipeline.load_camera_structural", lambda: NoisyPaymentAnalyzer()
        )
        monkeypatch.setattr(
            "app.pipeline.load_structural", lambda: NoisyPaymentAnalyzer()
        )
        payload = (
            "00020201021126410014A000000615000101065016640209123456789"
            "520400005303458540510.005802MY5909AUSERNAME6005BANGI63043A23"
        )
        body = client.post(
            "/scan",
            data={"payload": payload, "image_source": "camera"},
            files={"image": ("payment.png", qr_png, "image/png")},
        ).json()

        assert body["payload_type"] == "payment"
        assert body["branch_scores"]["p_structural"] == pytest.approx(0.99)
        assert body["branch_scores"]["structural_type"] == "tampered"
        assert body["verdict"] == "warning"
        assert body["risk_score"] == load_engine().safe_max
        assert body["partial_analysis"] is False
        assert any("confirm the recipient" in reason for reason in body["reasons"])

        generic = client.post(
            "/scan",
            data={"payload": "upi://pay?pa=unknown@bank", "image_source": "camera"},
            files={"image": ("payment.png", qr_png, "image/png")},
        ).json()
        assert generic["payload_type"] == "payment"
        assert generic["verdict"] == "blocked"

    def test_camera_model_still_blocks_adversarial_google(
        self, client, adversarial_png
    ):
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files={"image": ("adversarial.png", adversarial_png, "image/png")},
        ).json()

        assert body["branch_scores"]["structural_type"] == "adversarial"
        assert body["branch_scores"]["p_structural"] > 0.9
        assert body["verdict"] == "blocked"

    def test_camera_single_attack_frame_blocks_like_gallery(self, client, tampered_png):
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files={"image": ("qr.png", tampered_png, "image/png")},
        ).json()

        assert body["branch_scores"]["structural_type"] == "tampered"
        assert body["branch_scores"]["p_structural"] > 0.9
        assert body["branch_scores"]["p_structural_raw"] > 0.9
        assert body["verdict"] == "blocked"

    def test_legacy_repeated_uploads_use_the_first_crop(self, client, tampered_png):
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files=[
                ("images", (f"replay-{index}.png", tampered_png, "image/png"))
                for index in range(3)
            ],
        ).json()

        assert "structural_consensus" not in body["branch_scores"]
        assert body["branch_scores"]["p_structural"] > 0.9
        assert body["branch_scores"]["p_structural_raw"] > 0.9
        assert body["verdict"] == "blocked"

    def test_repeated_stable_camera_tampering_can_block(self, client, tampered_png):
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files=[
                ("images", (f"qr-{index}.png", frame, "image/png"))
                for index, frame in enumerate(_pixel_distinct_pngs(tampered_png, 3))
            ],
        ).json()

        assert body["branch_scores"]["p_structural"] > 0.9
        assert body["branch_scores"]["p_structural_raw"] > 0.9
        assert body["verdict"] == "blocked"

    def test_repeated_stable_clean_camera_frames_are_accepted(
        self, client, qr_png, monkeypatch
    ):
        class CleanAnalyzer:
            def predict(self, _image):
                return StructuralResult(
                    p_structural=0.12,
                    predicted_type="clean",
                    probs={"clean": 0.88, "adversarial": 0.08, "tampered": 0.04},
                )

        monkeypatch.setattr(
            "app.pipeline.load_camera_structural", lambda: CleanAnalyzer()
        )
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files=[
                ("images", (f"qr-{index}.png", frame, "image/png"))
                for index, frame in enumerate(_pixel_distinct_pngs(qr_png, 3))
            ],
        ).json()

        assert body["branch_scores"]["p_structural_raw"] == pytest.approx(0.12)
        assert body["branch_scores"]["p_structural"] == pytest.approx(0.08)
        assert body["verdict"] == "safe"

    def test_legacy_multi_upload_does_not_average_scores(
        self, client, qr_png, monkeypatch
    ):
        class UnstableCleanAnalyzer:
            def __init__(self):
                self.scores = iter((0.05, 0.12, 0.40))

            def predict(self, _image):
                score = next(self.scores)
                return StructuralResult(
                    p_structural=score,
                    predicted_type="clean",
                    probs={
                        "clean": 1 - score,
                        "adversarial": score * 0.75,
                        "tampered": score * 0.25,
                    },
                )

        analyzer = UnstableCleanAnalyzer()
        monkeypatch.setattr("app.pipeline.load_camera_structural", lambda: analyzer)
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files=[
                ("images", (f"qr-{index}.png", frame, "image/png"))
                for index, frame in enumerate(_pixel_distinct_pngs(qr_png, 3))
            ],
        ).json()

        assert body["branch_scores"]["p_structural_raw"] == pytest.approx(0.05)
        assert body["branch_scores"]["p_structural"] == pytest.approx(0.0375)
        assert body["verdict"] == "safe"

    def test_corrupt_legacy_frames_do_not_replace_the_first_valid_crop(
        self, client, qr_png, monkeypatch
    ):
        class HighAnalyzer:
            def predict(self, _image):
                return StructuralResult(
                    p_structural=0.99,
                    predicted_type="tampered",
                    probs={"clean": 0.01, "adversarial": 0.0, "tampered": 0.99},
                )

        monkeypatch.setattr(
            "app.pipeline.load_camera_structural", lambda: HighAnalyzer()
        )
        monkeypatch.setattr("app.pipeline.load_structural", lambda: HighAnalyzer())
        files = [("images", ("valid.png", qr_png, "image/png"))]
        files.extend(
            ("images", (f"bad-{index}.png", b"not an image", "image/png"))
            for index in range(2)
        )
        body = client.post(
            "/scan",
            data={
                "payload": "https://www.google.com/maps",
                "image_source": "camera",
            },
            files=files,
        ).json()

        assert body["branch_scores"]["p_structural"] == pytest.approx(0.99)
        assert body["verdict"] == "blocked"

    def test_more_than_five_images_is_rejected(self, client, qr_png):
        response = client.post(
            "/scan",
            data={"payload": "https://www.google.com/maps", "image_source": "camera"},
            files=[
                ("images", (f"qr-{index}.png", qr_png, "image/png"))
                for index in range(6)
            ],
        )

        assert response.status_code == 413

    def test_opt_in_capture_dump_is_anonymised(
        self, client, qr_png, monkeypatch, tmp_path
    ):
        payload = "WIFI:T:nopass;S:PrivateCafeName;;"
        monkeypatch.setenv("QRGUARD_DUMP_SCANS", str(tmp_path))
        monkeypatch.setenv("QRGUARD_CAPTURE_LABEL", "clean")

        response = client.post(
            "/scan",
            data={"payload": payload, "image_source": "camera"},
            files=[
                ("images", (f"qr-{index}.png", frame, "image/png"))
                for index, frame in enumerate(_pixel_distinct_pngs(qr_png, 3))
            ],
        )

        assert response.status_code == 200
        sessions = list((tmp_path / "clean").glob("scan_*"))
        assert len(sessions) == 1
        metadata_path = sessions[0] / "metadata.json"
        metadata_text = metadata_path.read_text(encoding="utf-8")
        metadata = json.loads(metadata_text)
        assert payload not in metadata_text
        assert metadata["payload_sha256"]
        assert metadata["ground_truth"] == "clean"
        assert metadata["image_source"] == "camera"
        assert len(list(sessions[0].glob("crop_*.png"))) == 1

    @pytest.mark.parametrize("score", [0.799, 0.800, 0.801])
    def test_camera_boundary_uses_normal_fusion(
        self, client, qr_png, monkeypatch, score
    ):
        class BoundaryAnalyzer:
            def predict(self, _image):
                return StructuralResult(
                    p_structural=score,
                    predicted_type="tampered",
                    probs={"clean": 1 - score, "adversarial": 0.0, "tampered": score},
                )

        monkeypatch.setattr(
            "app.pipeline.load_camera_structural", lambda: BoundaryAnalyzer()
        )
        monkeypatch.setattr("app.pipeline.load_structural", lambda: BoundaryAnalyzer())
        body = client.post(
            "/scan",
            data={
                "payload": "WIFI:T:nopass;S:FreeCafeWifi;;",
                "image_source": "camera",
            },
            files=[
                ("images", (f"qr-{index}.png", frame, "image/png"))
                for index, frame in enumerate(_pixel_distinct_pngs(qr_png, 3))
            ],
        ).json()

        expected = load_engine().predict(
            BranchInputs(
                p_structural=score,
                p_url=None,
                llm_score=None,
                rule_flags=body["rule_flags"],
                domain_unknown=None,
            )
        )
        assert body["branch_scores"]["p_structural"] == pytest.approx(score)
        assert body["verdict"] == expected.verdict
        assert body["risk_score"] == expected.risk_score

    def test_clean_image_phishing_url_blocks(self, client, qr_png):
        # mirror case: the image is fine, only the payload betrays it
        body = client.post(
            "/scan",
            data={"payload": "http://maybank2u-verify.xyz/login/update.php"},
            files={"image": ("qr.png", qr_png, "image/png")},
        ).json()
        assert body["verdict"] == "blocked"
        assert body["branch_scores"]["structural_type"] == "clean"

    def test_scan_without_image_still_works(self, client):
        body = client.post(
            "/scan", data={"payload": "https://www.google.com/maps"}
        ).json()
        assert body["verdict"] == "safe"
        assert body["partial_analysis"] is False
        assert body["branch_scores"]["structural_status"] == "not_applicable"

    def test_corrupt_image_degrades_gracefully(self, client):
        body = client.post(
            "/scan",
            data={"payload": "https://www.google.com/maps"},
            files={"image": ("bad.png", b"not really an image", "image/png")},
        ).json()
        assert body["verdict"] == "safe"  # semantic branch still worked
        assert body["partial_analysis"] is True  # structural abstained
        assert body["branch_scores"]["structural_status"] == "unavailable"

    def test_image_only_scan_decodes_server_side(self, client, qr_png):
        # Swagger/curl users only have a picture; leaving payload empty must work.
        body = client.post(
            "/scan", files={"image": ("qr.png", qr_png, "image/png")}
        ).json()
        assert body["payload_source"] == "decoded"
        assert body["payload"] == "https://www.google.com/maps"
        assert body["branch_scores"]["p_url"] is not None
        assert body["verdict"] == "safe"

    def test_undecodable_image_abstains_but_still_judges_the_image(
        self, client, tampered_png
    ):
        # A sticker over a QR genuinely stops it decoding - that is the attack.
        body = client.post(
            "/scan", files={"image": ("qr.png", tampered_png, "image/png")}
        ).json()
        assert body["payload_source"] == "undecodable"
        assert body["payload"] is None
        assert body["branch_scores"]["p_url"] is None  # semantic abstained
        assert body["branch_scores"]["structural_type"] == "tampered"
        assert body["verdict"] == "blocked"

    def test_explicit_payload_is_not_overridden_by_decoding(self, client, qr_png):
        body = client.post(
            "/scan",
            data={"payload": "http://maybank2u-verify.xyz/login"},
            files={"image": ("qr.png", qr_png, "image/png")},
        ).json()
        assert body["payload_source"] == "provided"
        assert body["registered_domain"] == "maybank2u-verify.xyz"

    def test_neither_payload_nor_image_is_rejected(self, client):
        assert client.post("/scan", data={}).status_code == 422

    def test_response_reports_latency(self, client, qr_png):
        body = client.post(
            "/scan",
            data={"payload": "https://www.google.com/maps"},
            files={"image": ("qr.png", qr_png, "image/png")},
        ).json()
        assert 0 <= body["elapsed_ms"] < 2000
