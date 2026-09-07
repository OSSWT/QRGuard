"""Conservative, payload-bound structural check for branded attendance QRs.

This is a deterministic design check, not token authentication or a replacement
CNN. Re-encode the decoded payload using the observed format bits and require
every module outside a bounded central logo to match. Unsupported encodings or
unreadable captures abstain. No reference image or attendance token is stored.
"""

from dataclasses import dataclass, replace
import os

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
    reason: str = "not_checked"
    payload_mismatch: bool = False
    module_count: int | None = None
    pixels_per_module: float | None = None
    outside_mismatches: int | None = None
    image_width: int | None = None
    image_height: int | None = None
    sampling_method: str = "decoder_grid"
    decoder_outside_mismatches: int | None = None
    decoder_format_uncertain: bool = False


def _format_value(observed):
    """Require both observed format copies to agree exactly; no guessed bits."""
    n = len(observed)
    vertical = sum(
        int(observed[i if i < 6 else i + 1 if i < 8 else n - 15 + i, 8]) << i
        for i in range(15)
    )
    horizontal = sum(
        int(observed[8, n - i - 1 if i < 8 else 7 if i == 8 else 14 - i]) << i
        for i in range(15)
    )
    formats = [value for value in range(32)
               if BCH_type_info(value) == vertical == horizontal]
    return formats[0] if len(formats) == 1 else None


def check_attendance_grid(image, payload: str) -> AttendanceGridCheck:
    result = _check_attendance_grid(image, payload)
    return replace(result, image_width=image.width, image_height=image.height)


def _check_attendance_grid(image, payload: str) -> AttendanceGridCheck:
    """Accept only readable, sufficiently detailed, matching attendance images.

The logo allowance is at most the central 30% of the symbol side, rounded
outwards to module boundaries, and requires high error correction plus a
coloured central graphic. Even one changed module outside it rejects the
allowance. Adversarial CNN evidence is handled separately by the caller.
"""
    if route_payload(payload).payload_type != "attendance":
        return AttendanceGridCheck(reason="unsupported_payload")
    if not assess_image_quality(image).usable:
        return AttendanceGridCheck(reason="image_quality")
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
    if decoded and decoded != payload:
        return AttendanceGridCheck(reason="payload_mismatch", payload_mismatch=True)
    if not decoded or points is None or straight is None:
        return AttendanceGridCheck(reason="decode_unavailable")
    n = len(straight)
    if straight.shape != (n, n) or not 21 <= n <= 177 or (n - 17) % 4:
        return AttendanceGridCheck(reason="grid_unavailable")
    corners = np.asarray(points, dtype=np.float32).reshape(4, 2)
    edges = np.linalg.norm(corners - np.roll(corners, -1, axis=0), axis=1)
    pixels_per_module = float(np.min(edges) / n)
    sampling_method = "decoder_grid"
    decoder_format_uncertain = False
    def uncertain(reason, mismatches=None):
        return AttendanceGridCheck(
            reason=reason, module_count=n, pixels_per_module=pixels_per_module,
            outside_mismatches=mismatches,
            sampling_method=sampling_method,
            decoder_format_uncertain=decoder_format_uncertain,
        )
    if pixels_per_module < 5:
        return uncertain("insufficient_module_scale")
    observed = straight < 128

    # Both redundant format strings must be intact. These positions mirror
    # qrcode.QRCode.setup_type_info; no guessed ECC/mask can authorize Safe.
    format_value = _format_value(observed)
    decoder_format_uncertain = format_value is None
    preview_registration = os.getenv("QRGUARD_ATTENDANCE_REGISTERED_SAMPLING") == "1"
    if decoder_format_uncertain and preview_registration:
        # Registration uses only standard fixed patterns, so it needs neither
        # the format value nor the payload. Read BOTH format copies again from
        # the physical image before proceeding to independent data comparison.
        from structural.registered_sampling import sample_registered_grid
        registered = sample_registered_grid(gray, corners, n)
        if registered is not None:
            observed = registered
            sampling_method = "fixed_pattern_registration_preview_v2"
            format_value = _format_value(observed)
    if format_value is None:
        return uncertain("format_uncertain")
    ecc, mask = format_value >> 3, format_value & 7
    qr = qrcode.QRCode(
        version=(n - 17) // 4, error_correction=ecc, border=0, mask_pattern=mask
    )
    qr.add_data(payload, optimize=0)
    try:
        qr.make(fit=False)
    except qrcode.exceptions.DataOverflowError:
        return uncertain("encoding_unsupported")
    difference = observed != np.asarray(qr.get_matrix(), dtype=bool)
    lo, hi = int(n * 0.35), int(np.ceil(n * 0.65))
    outside = np.ones((n, n), dtype=bool)
    outside[lo:hi, lo:hi] = False
    mismatch_count = int(difference[outside].sum())
    decoder_mismatches = None if decoder_format_uncertain else mismatch_count
    # Preview-only experiment. Production defaults to the unchanged verifier.
    if mismatch_count and preview_registration and sampling_method == "decoder_grid":
        from structural.registered_sampling import sample_registered_grid
        registered = sample_registered_grid(gray, corners, n)
        if registered is not None:
            difference = registered != np.asarray(qr.get_matrix(), dtype=bool)
            mismatch_count = int(difference[outside].sum())
            sampling_method = "fixed_pattern_registration_preview_v2"
    if mismatch_count:
        # Sampling errors and unsupported encoder segmentation also cause this.
        # A mismatch is not, by itself, proof of an attack.
        return replace(uncertain("outer_grid_difference", mismatch_count),
            sampling_method=sampling_method, decoder_outside_mismatches=decoder_mismatches)

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
        return uncertain("outer_colour_difference", 0)
    logo = bool(difference.any())
    if logo and (
        ecc != qrcode.constants.ERROR_CORRECT_H
        or float(chroma[~outside_pixels].mean()) < 0.10
    ):
        return uncertain("central_design_unsupported", 0)
    return AttendanceGridCheck(
        passed=True, central_logo=logo, reason="passed", module_count=n,
        pixels_per_module=pixels_per_module, outside_mismatches=0,
        sampling_method=sampling_method, decoder_outside_mismatches=decoder_mismatches,
        decoder_format_uncertain=decoder_format_uncertain,
    )
