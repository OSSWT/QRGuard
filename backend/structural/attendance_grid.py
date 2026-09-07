"""Conservative, payload-bound structural check for branded attendance QRs.

This is a deterministic design check, not token authentication or a replacement
CNN. Re-encode the decoded payload using the observed format bits and require
every module outside a bounded central logo to match. Unsupported encodings or
unreadable captures abstain. No reference image or attendance token is stored.
"""

from dataclasses import dataclass

import cv2
import numpy as np
import qrcode
from qrcode.util import BCH_type_info

from semantic.payload_router import route_payload
from structural.image_quality import assess_image_quality
from structural.qr_decoder import _rescue_views


@dataclass(frozen=True)
class AttendanceGridCheck:
    passed: bool = False
    central_logo: bool = False


def check_attendance_grid(image, payload: str) -> AttendanceGridCheck:
    """Accept only readable, sufficiently detailed, matching attendance images.

The logo allowance is at most the central 30% of the symbol side, rounded
outwards to module boundaries, and requires high error correction plus a
coloured central graphic. Even one changed module outside it rejects the
allowance. Adversarial CNN evidence is handled separately by the caller.
"""
    if route_payload(payload).payload_type != "attendance":
        return AttendanceGridCheck()
    if not assess_image_quality(image).usable:
        return AttendanceGridCheck()
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    decoded, points, straight = "", None, None
    detector = cv2.QRCodeDetector()
    for candidate, scale in _rescue_views(gray):
        try:
            decoded, points, straight = detector.detectAndDecode(candidate)
        except cv2.error:
            continue
        if decoded:
            points = points / scale if points is not None else None
            break
    if decoded != payload or points is None or straight is None:
        return AttendanceGridCheck()
    n = len(straight)
    if straight.shape != (n, n) or not 21 <= n <= 177 or (n - 17) % 4:
        return AttendanceGridCheck()
    corners = np.asarray(points, dtype=np.float32).reshape(4, 2)
    edges = np.linalg.norm(corners - np.roll(corners, -1, axis=0), axis=1)
    if np.min(edges) / n < 5:
        return AttendanceGridCheck()
    observed = straight < 128

    # Both redundant format strings must be intact. These positions mirror
    # qrcode.QRCode.setup_type_info; no guessed ECC/mask can authorize Safe.
    vertical = sum(
        int(observed[i if i < 6 else i + 1 if i < 8 else n - 15 + i, 8]) << i
        for i in range(15)
    )
    horizontal = sum(
        int(observed[8, n - i - 1 if i < 8 else 7 if i == 8 else 14 - i]) << i
        for i in range(15)
    )
    formats = [
        value for value in range(32)
        if BCH_type_info(value) == vertical == horizontal
    ]
    if len(formats) != 1:
        return AttendanceGridCheck()
    ecc, mask = formats[0] >> 3, formats[0] & 7
    qr = qrcode.QRCode(
        version=(n - 17) // 4, error_correction=ecc, border=0, mask_pattern=mask
    )
    qr.add_data(payload, optimize=0)
    try:
        qr.make(fit=False)
    except qrcode.exceptions.DataOverflowError:
        return AttendanceGridCheck()
    difference = observed != np.asarray(qr.get_matrix(), dtype=bool)
    lo, hi = int(n * 0.35), int(np.ceil(n * 0.65))
    outside = np.ones((n, n), dtype=bool)
    outside[lo:hi, lo:hi] = False
    if difference[outside].any():
        return AttendanceGridCheck()

    # Retain colour evidence: binarising a coloured overlay alone would hide it.
    side = n * 6
    destination = np.float32(
        [[0, 0], [side - 1, 0], [side - 1, side - 1], [0, side - 1]]
    )
    rectified = cv2.warpPerspective(
        rgb, cv2.getPerspectiveTransform(corners, destination), (side, side)
    )
    chroma = np.ptp(rectified.astype(np.int16), axis=2) > 40
    outside_pixels = np.repeat(np.repeat(outside, 6, axis=0), 6, axis=1)
    if float(chroma[outside_pixels].mean()) > 0.01:
        return AttendanceGridCheck()
    logo = bool(difference.any())
    if logo and (
        ecc != qrcode.constants.ERROR_CORRECT_H
        or float(chroma[~outside_pixels].mean()) < 0.10
    ):
        return AttendanceGridCheck()
    return AttendanceGridCheck(passed=True, central_logo=logo)
