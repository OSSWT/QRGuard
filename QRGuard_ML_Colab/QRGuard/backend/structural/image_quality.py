"""Source-neutral image-quality measurements for Structural v3.

This module does not decide whether a QR is malicious. It measures whether the
pixels provide usable structural evidence and supplies a conservative,
explainable normalisation step. Gallery and Camera call the same functions; no
model or threshold is selected from the input source.

The initial thresholds are screening defaults. Structural v3 must calibrate and
freeze them on validation data before runtime promotion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image

_MEASURE_SIDE = 224


@dataclass(frozen=True)
class ImageQualityReport:
    width: int
    height: int
    mean_luminance: float
    p05_luminance: float
    p95_luminance: float
    dynamic_range: float
    laplacian_variance: float
    dark_fraction: float
    bright_fraction: float
    status: str
    conditions: tuple[str, ...]
    rescan_reason: str | None

    @property
    def usable(self) -> bool:
        return self.status != "unusable"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _luminance(image: Image.Image) -> np.ndarray:
    measured = image.convert("L").resize(
        (_MEASURE_SIDE, _MEASURE_SIDE), Image.Resampling.BILINEAR
    )
    return np.asarray(measured, dtype=np.float32)


def assess_image_quality(image: Image.Image) -> ImageQualityReport:
    """Measure acquisition quality without producing an attack label."""

    width, height = image.size
    gray = _luminance(image)
    p05, p95 = np.percentile(gray, (5, 95))
    mean = float(gray.mean())
    dynamic_range = float(p95 - p05)
    centre = gray[1:-1, 1:-1]
    laplacian = (
        -4.0 * centre
        + gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
    )
    focus = float(laplacian.var())
    dark_fraction = float((gray <= 24).mean())
    bright_fraction = float((gray >= 240).mean())

    conditions: list[str] = []
    # QR density changes the global mean dramatically. Exposure conditions use
    # the bright and dark percentiles instead, so a dense but correctly exposed
    # QR is not mistaken for an underexposed capture.
    if p95 < 145:
        conditions.append("underexposure")
    if p05 > 85:
        conditions.append("overexposure")
    if dynamic_range < 90:
        conditions.append("low_contrast")
    if focus < 55:
        conditions.append("blur")
    if min(width, height) < 48:
        conditions.append("small_input")

    severe_reason = None
    if min(width, height) < 24:
        severe_reason = "QR crop is too small for reliable structural analysis."
    elif dynamic_range < 35:
        severe_reason = "QR contrast is too low; improve lighting and scan again."
    elif focus < 10:
        severe_reason = "QR image is too blurred; hold the camera steady and scan again."
    elif p95 < 105:
        severe_reason = "QR image is too dark; add light and scan again."
    elif p05 > 145:
        severe_reason = "QR image is overexposed; reduce glare and scan again."

    if severe_reason:
        status = "unusable"
    elif conditions:
        status = "marginal"
    else:
        status = "usable"

    return ImageQualityReport(
        width=width,
        height=height,
        mean_luminance=mean,
        p05_luminance=float(p05),
        p95_luminance=float(p95),
        dynamic_range=dynamic_range,
        laplacian_variance=focus,
        dark_fraction=dark_fraction,
        bright_fraction=bright_fraction,
        status=status,
        conditions=tuple(conditions) if conditions else ("normal",),
        rescan_reason=severe_reason,
    )


def normalize_measured_range(
    image: Image.Image, report: ImageQualityReport | None = None
) -> Image.Image:
    """Apply conservative global range correction selected from pixel measures.

    Local chroma, overlays, damaged modules and attack evidence are preserved.
    An unusable image is returned unchanged because normalisation must not
    manufacture evidence that was absent from the capture.
    """

    report = report or assess_image_quality(image)
    rgb_image = image.convert("RGB")
    if not report.usable or report.status == "usable":
        return rgb_image
    if report.dynamic_range < 35:
        return rgb_image

    rgb = np.asarray(rgb_image, dtype=np.float32)
    black = report.p05_luminance
    white = report.p95_luminance
    gain = float(np.clip(239.0 / max(white - black, 1.0), 0.70, 2.20))
    corrected = np.clip(rgb * gain + (8.0 - black * gain), 0, 255).astype(np.uint8)
    return Image.fromarray(corrected, mode="RGB")
