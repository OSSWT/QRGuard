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

from typing import Optional

import numpy as np


def decode_qr(image) -> Optional[str]:
    """Decode a PIL image. Returns the payload text, or None if unreadable."""
    try:
        import cv2
    except ImportError:  # opencv is optional for the pure-semantic path
        return None

    try:
        rgb = np.array(image.convert("RGB"))
    except Exception:
        return None

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    detector = cv2.QRCodeDetector()

    # Try the image as-is, then a couple of cheap rescues. Camera crops are often
    # small or low-contrast, and upscaling alone recovers many of them.
    for candidate in (gray, _upscale(gray, 2), _binarise(gray)):
        try:
            data, _points, _ = detector.detectAndDecode(candidate)
        except cv2.error:
            continue
        if data:
            return data
    return None


def _upscale(gray: np.ndarray, factor: int) -> np.ndarray:
    import cv2

    return cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def _binarise(gray: np.ndarray) -> np.ndarray:
    import cv2

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary
