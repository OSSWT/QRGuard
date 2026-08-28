"""Regression tests for the app-equivalent real-photo preprocessing path."""

import cv2
import numpy as np
import pytest

from scripts.real_photo_eval import _correct_global_camera_cast, crop_to_code


def test_crop_to_code_rectifies_detected_perspective_qr():
    qrcode = pytest.importorskip("qrcode")
    qr = qrcode.QRCode(box_size=10, border=4)
    payload = "WIFI:T:nopass;S:RuntimeContractTest;;"
    qr.add_data(payload)
    qr.make(fit=True)
    rgb = np.asarray(
        qr.make_image(fill_color="black", back_color="white").convert("RGB")
    )
    bgr = rgb[:, :, ::-1]

    height, width = bgr.shape[:2]
    source = np.float32(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
    )
    target = np.float32([[90, 70], [455, 35], [500, 410], [55, 445]])
    projected = cv2.warpPerspective(
        bgr,
        cv2.getPerspectiveTransform(source, target),
        (560, 500),
        borderValue=(255, 255, 255),
    )

    crop, how = crop_to_code(projected)

    assert crop is not None
    assert how == "detected+rectified"
    assert crop.shape[0] == crop.shape[1]
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(crop)
    assert decoded == payload


def test_crop_to_code_never_guesses_a_centre_crop():
    crop, how = crop_to_code(np.full((400, 600, 3), 220, dtype=np.uint8))

    assert crop is None
    assert how == "not-detected"


def test_global_cast_correction_neutralises_bright_paper():
    cast_bgr = np.empty((80, 80, 3), dtype=np.uint8)
    cast_bgr[:] = (210, 180, 130)

    corrected = _correct_global_camera_cast(cast_bgr)
    means = corrected.mean(axis=(0, 1))

    assert float(means.max() - means.min()) <= 1.0
