"""Attendance logo policy: real decoding, independent identities, negative cases."""

import base64
import hashlib

import numpy as np
import pytest
import qrcode
from PIL import Image, ImageDraw, ImageEnhance

from app.pipeline import run_scan
from semantic.payload_router import route_payload
from structural.attendance_grid import check_attendance_grid
from structural.structural_service import StructuralResult


def attendance_image(identity=0, *, logo=True, mask=7, ecc=qrcode.constants.ERROR_CORRECT_H):
    # Synthetic opaque data, never a student's real attendance token.
    payload = "Q01:*:" + base64.b64encode(
        hashlib.sha256(str(identity).encode()).digest() * 3
    ).decode()
    qr = qrcode.QRCode(version=11, error_correction=ecc, box_size=8, border=4, mask_pattern=mask)
    qr.add_data(payload, optimize=0)
    qr.make(fit=False)
    image = qr.make_image().convert("RGB")
    if logo:
        ImageDraw.Draw(image).rectangle((208, 208, 343, 343), fill=(35, 18, 90))
    return payload, image


@pytest.mark.parametrize("identity,mask", [(0, 0), (1, 3), (2, 7)])
@pytest.mark.parametrize("capture", ["original", "rotation", "exposure", "perspective"])
def test_independent_branded_attendance_images(identity, mask, capture):
    payload, image = attendance_image(identity, mask=mask)
    if capture == "rotation":
        image = image.rotate(90)
    elif capture == "exposure":
        image = ImageEnhance.Brightness(image).enhance(0.8)
    elif capture == "perspective":
        import cv2

        source = np.float32([[0, 0], [551, 0], [551, 551], [0, 551]])
        target = np.float32([[12, 18], [535, 8], [546, 535], [8, 545]])
        image = Image.fromarray(cv2.warpPerspective(
            np.asarray(image), cv2.getPerspectiveTransform(source, target),
            (552, 552), borderValue=(255, 255, 255),
        ))
    result = check_attendance_grid(image, payload)
    assert result.passed
    assert result.central_logo


@pytest.mark.parametrize("attack", ["outside_module", "outside_colour", "oversize_logo", "mismatch", "small", "blank"])
def test_invalid_evidence_never_passes(attack):
    payload, image = attendance_image()
    if attack == "outside_module":
        # One flipped module still decodes through error correction, but must
        # not receive the benign central-logo allowance.
        x = y = (4 + 20) * 8
        colour = "white" if image.getpixel((x + 4, y + 4))[0] < 128 else "black"
        ImageDraw.Draw(image).rectangle((x, y, x + 7, y + 7), fill=colour)
    elif attack == "outside_colour":
        pixels = np.asarray(image).copy()
        region = pixels[104:176, 104:176]
        region[np.all(region < 128, axis=2)] = (90, 0, 0)
        image = Image.fromarray(pixels)
    elif attack == "oversize_logo":
        ImageDraw.Draw(image).rectangle((175, 175, 375, 375), fill=(35, 18, 90))
    elif attack == "mismatch":
        payload, _ = attendance_image(9)
    elif attack == "small":
        image = image.resize((220, 220))
    elif attack == "blank":
        image = Image.new("RGB", image.size, "white")
    assert not check_attendance_grid(image, payload).passed


def test_truncated_envelope_is_not_attendance():
    assert route_payload("Q01:*:" + "A" * 5000).payload_type == "text"


def fake_model(monkeypatch, label):
    class Analyzer:
        def predict(self, image):
            return StructuralResult(
                p_structural=0.999 if label != "clean" else 0.01,
                predicted_type=label,
                probs={"clean": 0.001, "tampered": 0.999 if label == "tampered" else 0.0,
                       "adversarial": 0.999 if label == "adversarial" else 0.0},
            )

    monkeypatch.delenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", raising=False)
    monkeypatch.setattr("app.pipeline.load_structural", Analyzer)
    monkeypatch.setattr("app.pipeline.load_camera_structural", Analyzer)


@pytest.mark.parametrize("source", ["gallery", "camera"])
def test_logo_false_positive_is_resolved_and_cnn_preserved(monkeypatch, source):
    fake_model(monkeypatch, "tampered")
    payload, image = attendance_image()
    frames = [image, image.rotate(90), image.rotate(180)] if source == "camera" else [image]
    result = run_scan(payload, images=frames, image_source=source, require_camera_consensus=source == "camera")
    assert result.verdict == "safe"
    assert result.risk_score < 26
    assert not result.partial_analysis
    assert result.branch_scores.structural_method == "attendance_grid_v1"
    assert result.branch_scores.structural_type == "clean"
    assert result.branch_scores.structural_raw_type == "tampered"
    assert result.branch_scores.p_structural_raw == 0.999
    assert not any("manipulat" in reason for reason in result.reasons)


@pytest.mark.parametrize("case", ["no_image", "mismatch", "one_camera_frame", "mixed_payloads", "adversarial", "tampered_without_logo"])
def test_attendance_never_blindly_overrides_risk(monkeypatch, case):
    fake_model(monkeypatch, "adversarial" if case == "adversarial" else "tampered")
    payload, image = attendance_image(logo=case != "tampered_without_logo")
    frames = [image]
    source = "gallery"
    consensus = False
    if case == "no_image":
        frames = []
        source = "unknown"
    elif case == "mismatch":
        payload, _ = attendance_image(8)
    elif case == "one_camera_frame":
        source, consensus = "camera", True
    elif case == "mixed_payloads":
        _, other = attendance_image(8)
        frames = [image, image, other]
        source, consensus = "camera", True
    result = run_scan(payload, images=frames, image_source=source, require_camera_consensus=consensus)
    assert result.verdict != "safe"
    assert result.branch_scores.structural_method == "cnn"


def test_clean_unbranded_attendance_passes(monkeypatch):
    fake_model(monkeypatch, "clean")
    payload, image = attendance_image(logo=False)
    assert run_scan(payload, image=image, image_source="gallery").verdict == "safe"


def test_outer_sampling_difference_is_inconclusive_not_confirmed_attack(monkeypatch):
    fake_model(monkeypatch, "tampered")
    payload, image = attendance_image()
    x = y = (4 + 20) * 8
    colour = "white" if image.getpixel((x + 4, y + 4))[0] < 128 else "black"
    ImageDraw.Draw(image).rectangle((x, y, x + 7, y + 7), fill=colour)
    result = run_scan(payload, image=image, image_source="gallery")
    assert result.verdict == "warning"
    assert result.partial_analysis
    assert result.branch_scores.structural_status == "inconclusive"
    assert result.branch_scores.p_structural is None
    assert result.branch_scores.p_structural_raw == 0.999
    assert result.branch_scores.structural_raw_type == "tampered"
    diagnostic = result.branch_scores.attendance_checks[0]
    assert diagnostic["reason"] == "outer_grid_difference"
    assert diagnostic["outside_mismatches"] == 1
    assert diagnostic["image_width"] == 552
    assert not any("confirmed QR manipulation" in reason for reason in result.reasons)


def test_unreadable_frame_abstains_with_specific_reason(monkeypatch):
    fake_model(monkeypatch, "tampered")
    payload, image = attendance_image()
    image = Image.new("RGB", image.size, "white")
    result = run_scan(payload, image=image, image_source="gallery")
    assert result.verdict == "warning"
    assert result.branch_scores.attendance_checks[0]["reason"] == "image_quality"


def test_content_mismatch_blocks_even_when_cnn_says_clean(monkeypatch):
    fake_model(monkeypatch, "clean")
    payload, _ = attendance_image(5)
    _, image = attendance_image(6)
    result = run_scan(payload, image=image, image_source="gallery")
    assert result.verdict == "blocked"
    assert result.branch_scores.attendance_checks[0]["reason"] == "payload_mismatch"


@pytest.mark.parametrize("source", ["gallery", "camera"])
def test_real_api_decodes_and_checks_attendance(monkeypatch, source):
    from io import BytesIO

    from fastapi.testclient import TestClient
    from app.main import app

    fake_model(monkeypatch, "tampered")
    payload, image = attendance_image()
    output = BytesIO()
    image.save(output, format="PNG")
    fields = {"image_source": source}
    files = [("image", ("qr.png", output.getvalue(), "image/png"))]
    if source == "camera":
        fields.update(payload=payload, camera_evidence_policy="temporal_consensus_v1")
        for angle in (90, 180):
            frame = BytesIO()
            image.rotate(angle).save(frame, format="PNG")
            files.append(("images", (f"frame{angle}.png", frame.getvalue(), "image/png")))
    with TestClient(app) as client:
        response = client.post("/scan", data=fields, files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "safe"
    assert body["payload"] == payload
    assert body["branch_scores"]["structural_method"] == "attendance_grid_v1"
