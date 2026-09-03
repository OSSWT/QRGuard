"""Server-side QR decoding.

The production flow decodes on the phone (fast, works offline) and sends the text
alongside the image crop. This module is the fallback for everything else: the Swagger
UI, curl, evaluation scripts, and any client that only has a picture.

A failed decode is not an error. Heavily tampered QR codes genuinely do not decode --
that is what a sticker over a payment code does in real life -- so the caller gets
`None`, the semantic branch abstains, and the structural branch still reports what it
sees. `partial_analysis` then tells the user the verdict rests on one branch.
"""

from __future__ import annotations

import numpy as np


def decode_qr(image) -> str | None:
    """Decode a PIL image. Returns the payload text, or None if unreadable."""
    detections = decode_and_crop_qrs(image)
    return detections[0][0] if detections else None


def estimate_qr_module_count(image) -> int | None:
    """Return the decoded QR grid side (21, 25, ..., 177) when observable.

    OpenCV's ``straight_qrcode`` is a one-pixel-per-module canonical grid. This
    gives acquisition scale a QR-version-aware denominator without guessing the
    version from payload length. Failure is expected for severely manipulated
    codes and must remain an unknown measurement, never a clean/attack label.
    """
    try:
        import cv2
    except ImportError:
        return None
    try:
        rgb = np.array(image.convert("RGB"))
    except (AttributeError, TypeError, ValueError):
        return None

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    detector = cv2.QRCodeDetector()
    for candidate, _ in _rescue_views(gray):
        try:
            data, _, straight = detector.detectAndDecode(candidate)
        except cv2.error:
            continue
        if not data or straight is None or getattr(straight, "ndim", 0) < 2:
            continue
        height, width = straight.shape[:2]
        if height == width and 21 <= width <= 177 and (width - 21) % 4 == 0:
            return int(width)
    return None


def decode_and_crop_qrs(image) -> list[tuple[str, object]]:
    """Decode and rectify every readable QR in one selected image.

    Desktop browsers cannot use ``mobile_scanner.analyzeImage``. They upload the
    chosen file instead, so the backend performs the same essential operation as
    the native client: locate the QR, preserve a quiet-zone margin and send only
    that rectified region to Structural inference. The first successful rescue
    view is authoritative; results are not accumulated across transforms.
    """
    try:
        import cv2
    except ImportError:  # opencv is optional for the pure-semantic path
        return []

    try:
        rgb = np.array(image.convert("RGB"))
    except (AttributeError, TypeError, ValueError):
        return []

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    detector = cv2.QRCodeDetector()

    # QR Reed-Solomon validation still decides whether a payload is valid. These
    # views only recover detector contrast lost to low exposure, screen moire or
    # a small camera crop; no guessed payload is ever returned.
    for candidate, scale in _rescue_views(gray):
        multi = _decode_multi(detector, candidate)
        if multi:
            return [
                (payload, crop)
                for payload, points in multi
                if (crop := _rectify(rgb, points / scale)) is not None
            ]
        try:
            data, points, _ = detector.detectAndDecode(candidate)
        except cv2.error:
            continue
        if data and points is not None:
            crop = _rectify(rgb, np.asarray(points, dtype=np.float32) / scale)
            if crop is not None:
                return [(data, crop)]
    return []


def _decode_multi(detector, candidate) -> list[tuple[str, np.ndarray]]:
    import cv2

    try:
        found, payloads, points, _ = detector.detectAndDecodeMulti(candidate)
    except (AttributeError, ValueError, cv2.error):
        return []
    if not found or points is None:
        return []
    return [
        (payload, np.asarray(corners, dtype=np.float32))
        for payload, corners in zip(payloads, points)
        if payload
    ]


def _rectify(rgb: np.ndarray, points: np.ndarray):
    """Perspective-correct one QR while retaining its surrounding quiet zone."""
    import cv2
    from PIL import Image

    corners = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if corners.shape != (4, 2) or not np.isfinite(corners).all():
        return None
    centre = corners.mean(axis=0)
    expanded = centre + (corners - centre) * 1.30
    expanded[:, 0] = np.clip(expanded[:, 0], 0, rgb.shape[1] - 1)
    expanded[:, 1] = np.clip(expanded[:, 1], 0, rgb.shape[0] - 1)
    edges = np.linalg.norm(expanded - np.roll(expanded, -1, axis=0), axis=1)
    side = round(float(edges.mean()))
    if side < 24:
        return None
    side = min(side, max(rgb.shape[0], rgb.shape[1]))
    destination = np.array(
        [[0, 0], [side - 1, 0], [side - 1, side - 1], [0, side - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(expanded.astype(np.float32), destination)
    crop = cv2.warpPerspective(
        rgb,
        matrix,
        (side, side),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    return Image.fromarray(crop, mode="RGB")


def _upscale(gray: np.ndarray, factor: int) -> np.ndarray:
    import cv2

    return cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def _binarise(gray: np.ndarray) -> np.ndarray:
    import cv2

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _local_contrast(gray: np.ndarray) -> np.ndarray:
    import cv2

    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)


def _adaptive_binarise(gray: np.ndarray) -> np.ndarray:
    import cv2

    side = min(gray.shape[:2])
    block_size = min(51, max(15, (side // 12) | 1))
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        5,
    )


def _rescue_views(gray: np.ndarray) -> tuple[tuple[np.ndarray, float], ...]:
    """Return bounded detector views with coordinates mapped to the source."""

    contrast = _local_contrast(gray)
    adaptive = _adaptive_binarise(gray)
    return (
        (gray, 1.0),
        (_upscale(gray, 2), 2.0),
        (contrast, 1.0),
        (_upscale(contrast, 2), 2.0),
        (_binarise(gray), 1.0),
        (adaptive, 1.0),
        (_upscale(adaptive, 2), 2.0),
    )
