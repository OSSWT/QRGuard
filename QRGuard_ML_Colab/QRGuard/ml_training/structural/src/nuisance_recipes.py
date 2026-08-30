"""Deterministic everyday capture-condition recipes for Structural v3.

These recipes create controlled training and evaluation slices. They never
change the Structural target by themselves. Digital adversarial examples are a
special case: transform-first/EOT generation or a real recapture must verify
that the attack survives. Do not blindly transform an existing FGSM/PGD image
and retain its adversarial label.
"""

from __future__ import annotations

import io
from typing import Final

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

CONDITIONS: Final = (
    "normal",
    "overexposure",
    "underexposure",
    "motion_blur",
    "defocus_blur",
    "far_distance",
    "perspective",
    "glare",
    "shadow",
    "screen_moire_or_compression",
)
SEVERITY_LEVELS: Final = {"mild": 1, "moderate": 2, "severe": 3}


def _rng(seed: int | str) -> np.random.Generator:
    if isinstance(seed, str):
        import hashlib

        seed = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big")
    return np.random.default_rng(seed)


def _rgb_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _motion_blur(image: Image.Image, level: int, rng: np.random.Generator) -> Image.Image:
    array = _rgb_array(image)
    length = (5, 9, 15)[level - 1]
    kernel = np.zeros((length, length), dtype=np.float32)
    if rng.random() < 0.5:
        kernel[length // 2, :] = 1.0
    else:
        kernel[:, length // 2] = 1.0
    kernel /= kernel.sum()
    return Image.fromarray(cv2.filter2D(array, -1, kernel), mode="RGB")


def _far_distance(image: Image.Image, level: int) -> Image.Image:
    source = image.convert("RGB")
    width, height = source.size
    scale = (0.72, 0.52, 0.35)[level - 1]
    small = source.resize(
        (max(8, round(width * scale)), max(8, round(height * scale))),
        Image.Resampling.BILINEAR,
    )
    return small.resize((width, height), Image.Resampling.BILINEAR)


def _perspective(
    image: Image.Image, level: int, rng: np.random.Generator
) -> Image.Image:
    array = _rgb_array(image)
    height, width = array.shape[:2]
    amount = (0.035, 0.07, 0.12)[level - 1] * min(width, height)
    source = np.float32(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
    )
    offsets = rng.uniform(-amount, amount, size=(4, 2)).astype(np.float32)
    destination = source + offsets
    matrix = cv2.getPerspectiveTransform(source, destination)
    warped = cv2.warpPerspective(
        array,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    return Image.fromarray(warped, mode="RGB")


def _glare(image: Image.Image, level: int, rng: np.random.Generator) -> Image.Image:
    array = _rgb_array(image).astype(np.float32)
    height, width = array.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    centre_x = rng.uniform(0.25, 0.75) * width
    centre_y = rng.uniform(0.20, 0.65) * height
    radius_x = (0.16, 0.23, 0.31)[level - 1] * width
    radius_y = radius_x * rng.uniform(0.45, 0.80)
    distance = ((xx - centre_x) / radius_x) ** 2 + ((yy - centre_y) / radius_y) ** 2
    alpha = np.clip(1.0 - distance, 0.0, 1.0)[..., None]
    strength = (0.25, 0.45, 0.68)[level - 1]
    output = array * (1.0 - alpha * strength) + 255.0 * alpha * strength
    return Image.fromarray(np.clip(output, 0, 255).astype(np.uint8), mode="RGB")


def _shadow(image: Image.Image, level: int, rng: np.random.Generator) -> Image.Image:
    array = _rgb_array(image).astype(np.float32)
    height, width = array.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    angle = rng.uniform(0, np.pi * 2)
    projection = np.cos(angle) * xx / max(width - 1, 1) + np.sin(angle) * yy / max(
        height - 1, 1
    )
    projection = (projection - projection.min()) / max(np.ptp(projection), 1e-6)
    darkness = (0.22, 0.38, 0.55)[level - 1]
    mask = 1.0 - darkness * projection[..., None]
    return Image.fromarray(np.clip(array * mask, 0, 255).astype(np.uint8), mode="RGB")


def _moire_and_compression(
    image: Image.Image, level: int, rng: np.random.Generator
) -> Image.Image:
    array = _rgb_array(image).astype(np.float32)
    _, width = array.shape[:2]
    xx = np.arange(width, dtype=np.float32)[None, :]
    frequency = rng.uniform(0.12, 0.25)
    amplitude = (3.0, 6.0, 10.0)[level - 1]
    pattern = np.sin(xx * frequency * np.pi * 2) * amplitude
    array = np.clip(array + pattern[..., None], 0, 255).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(array, mode="RGB").save(
        buffer, format="JPEG", quality=(82, 66, 48)[level - 1]
    )
    buffer.seek(0)
    with Image.open(buffer) as compressed:
        return compressed.convert("RGB").copy()


def apply_nuisance(
    image: Image.Image,
    condition: str,
    severity: str = "mild",
    seed: int | str = 42,
) -> Image.Image:
    """Return one deterministic condition variant with the original dimensions."""

    if condition not in CONDITIONS:
        raise ValueError(f"unknown quality condition: {condition}")
    if condition == "normal":
        return image.convert("RGB").copy()
    if severity not in SEVERITY_LEVELS:
        raise ValueError(f"unknown quality severity: {severity}")

    level = SEVERITY_LEVELS[severity]
    rng = _rng(seed)
    source = image.convert("RGB")
    if condition == "overexposure":
        result = ImageEnhance.Brightness(source).enhance((1.18, 1.38, 1.65)[level - 1])
        return ImageEnhance.Contrast(result).enhance((0.96, 0.88, 0.78)[level - 1])
    if condition == "underexposure":
        result = ImageEnhance.Brightness(source).enhance((0.78, 0.58, 0.38)[level - 1])
        return ImageEnhance.Contrast(result).enhance((0.96, 0.88, 0.78)[level - 1])
    if condition == "motion_blur":
        return _motion_blur(source, level, rng)
    if condition == "defocus_blur":
        return source.filter(ImageFilter.GaussianBlur((0.8, 1.7, 3.0)[level - 1]))
    if condition == "far_distance":
        return _far_distance(source, level)
    if condition == "perspective":
        return _perspective(source, level, rng)
    if condition == "glare":
        return _glare(source, level, rng)
    if condition == "shadow":
        return _shadow(source, level, rng)
    if condition == "screen_moire_or_compression":
        return _moire_and_compression(source, level, rng)
    raise AssertionError("unreachable condition")
