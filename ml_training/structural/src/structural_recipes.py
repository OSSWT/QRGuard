"""Reproducible data recipes for the local Structural Training candidate."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from ml_training.structural.src.nuisance_recipes import CONDITIONS, apply_nuisance

ROOT = Path(__file__).resolve().parents[3]
VERSION = os.getenv("QRGUARD_STRUCTURAL_VERSION", "structural-r07-corrective-v1")
DATASET_VERSION = os.getenv("QRGUARD_STRUCTURAL_DATASET_VERSION", VERSION)
PROCESSED = ROOT / "ml_training/datasets/structural/processed" / DATASET_VERSION
IMAGES = PROCESSED / "images"
MANIFEST = PROCESSED / "manifest.csv"
IMG_SIZE = 224
SEED = 42
BASE_COUNTS = {"train": 900, "validation": 180, "test": 180}
CAMERA_FRACTION = 0.70
CLASS_NAMES = ("clean", "adversarial", "tampered")
IS_V3 = VERSION.startswith(
    ("structural-2026.03", "structural-2026.09", "structural-r07")
)
V3_CONDITION_CHOICES = ("normal", "normal", "normal", *CONDITIONS[1:])


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _add_logo(image: Image.Image, rng: random.Random) -> Image.Image:
    width, height = image.size
    side = int(width * rng.uniform(0.10, 0.16))
    ring = max(2, side // 8)
    centre_x, centre_y = width // 2, height // 2
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        [
            centre_x - side // 2 - ring,
            centre_y - side // 2 - ring,
            centre_x + side // 2 + ring,
            centre_y + side // 2 + ring,
        ],
        fill="white",
    )
    colour = rng.choice(
        [(20, 20, 20), (200, 30, 40), (30, 90, 200), (20, 140, 80), (240, 140, 20)]
    )
    inner = [
        centre_x - side // 2,
        centre_y - side // 2,
        centre_x + side // 2,
        centre_y + side // 2,
    ]
    shape = rng.choice(("circle", "rounded", "square"))
    if shape == "circle":
        draw.ellipse(inner, fill=colour)
    elif shape == "rounded":
        draw.rounded_rectangle(inner, radius=side // 4, fill=colour)
    else:
        draw.rectangle(inner, fill=colour)
    return image


def _content(index: int, rng: random.Random) -> str:
    token = "".join(
        rng.choice("abcdefghijklmnopqrstuvwxyz0123456789")
        for _ in range(rng.randint(6, 24))
    )
    kind = index % 5
    if kind == 0:
        return f"https://{token}.com/{rng.randint(1, 9999)}"
    if kind == 1:
        return f"https://sub.{token}.org/path/page?id={rng.randint(1, 9999)}"
    if kind == 2:
        return f"WIFI:T:WPA;S:{token};P:{token[:8]};;"
    if kind == 3:
        return f"mailto:{token}@example.test?subject=QRGuard"
    return f"QRGuard-{token}-{rng.randint(100000, 999999)}"


def _candidate_config() -> dict:
    path = ROOT / "ml_training/configs" / f"{VERSION}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _fixed_ascii_payload(identity: str, target_bytes: int) -> str:
    prefix = f"QRG-TCF-{identity}-"
    if len(prefix.encode("ascii")) > target_bytes:
        raise ValueError(
            f"topology counterfactual prefix exceeds {target_bytes} bytes: {identity}"
        )
    digest = hashlib.sha256(f"topology-counterfactual:{identity}".encode()).hexdigest()
    required = target_bytes - len(prefix)
    payload = prefix + (digest * math.ceil(required / len(digest)))[:required]
    if len(payload.encode("utf-8")) != target_bytes:
        raise AssertionError("topology counterfactual payload length drifted")
    return payload


def generate_topology_counterfactual_clean_rows(
    config: dict | None = None,
) -> list[dict]:
    """Generate clean QR families that differ only by standards-valid mask layout.

    Each logical payload is rendered with all configured mask patterns and two
    controlled acquisition conditions. The whole family shares a leakage group
    and consistency partner key, so the classifier is explicitly discouraged
    from treating a legal QR mask/topology as evidence of manipulation.

    This recipe is opt-in per candidate config. Frozen r01-r04 manifests remain
    byte-identical when their configs do not contain ``topology_counterfactuals``.
    """

    import qrcode

    recipe = config
    if recipe is None:
        recipe = _candidate_config().get("topology_counterfactuals", {})
    if not recipe or not recipe.get("enabled", False):
        return []

    masks = tuple(int(value) for value in recipe.get("mask_patterns", range(8)))
    if sorted(masks) != list(range(8)) or len(set(masks)) != 8:
        raise ValueError("topology counterfactuals require each mask pattern 0-7 once")
    versions = recipe.get("versions", [])
    if not versions:
        raise ValueError("topology counterfactual versions are required")
    conditions = tuple(recipe.get("conditions", ("normal",)))
    if not conditions or any(condition not in CONDITIONS for condition in conditions):
        raise ValueError("topology counterfactual condition is unsupported")
    explicit_train_identities = recipe.get("train_identities_per_error_correction")
    explicit_validation_identities = recipe.get(
        "validation_identities_per_error_correction"
    )
    if explicit_train_identities is None and explicit_validation_identities is None:
        identities_per_error_correction = int(
            recipe.get("identities_per_error_correction", 2)
        )
        if identities_per_error_correction != 2:
            raise ValueError(
                "legacy topology counterfactuals require two identities per error "
                "correction (one train and one validation)"
            )
        train_identities = 1
        validation_identities = 1
    else:
        if (
            explicit_train_identities is None
            or explicit_validation_identities is None
            or "identities_per_error_correction" in recipe
        ):
            raise ValueError(
                "topology counterfactual identity counts require separate positive "
                "train and validation values without the legacy combined value"
            )
        train_identities = int(explicit_train_identities)
        validation_identities = int(explicit_validation_identities)
        if train_identities < 1 or validation_identities < 1:
            raise ValueError(
                "topology counterfactual train and validation identity counts must "
                "both be positive"
            )
    identities_per_error_correction = train_identities + validation_identities
    error_corrections = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
    requested_corrections = tuple(
        str(value) for value in recipe.get("error_corrections", error_corrections)
    )
    if set(requested_corrections) != set(error_corrections):
        raise ValueError("topology counterfactuals require L/M/Q/H error correction")

    counterfactual_dir = IMAGES / "topology_counterfactual_clean"
    rows: list[dict] = []
    for version_spec in versions:
        version = int(version_spec["version"])
        target_bytes = int(version_spec["payload_utf8_bytes"])
        if version not in range(1, 41) or target_bytes < 1:
            raise ValueError(f"invalid topology counterfactual spec: {version_spec}")
        version_band = (
            "low_v1_v3"
            if version <= 3
            else "medium_v4_v6"
            if version <= 6
            else "high_v7_plus"
        )
        payload_bin = (
            "short_1_32"
            if target_bytes <= 32
            else "medium_33_96"
            if target_bytes <= 96
            else "long_97_plus"
        )
        for correction_name in requested_corrections:
            for identity_index in range(identities_per_error_correction):
                split = (
                    "train"
                    if identity_index < train_identities
                    else "validation"
                )
                identity = (
                    f"v{version:02d}-{correction_name.lower()}-{identity_index + 1}"
                )
                payload = _fixed_ascii_payload(identity, target_bytes)
                payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                group_id = f"synthetic_topology:{identity}"
                style_rng = random.Random(_seed(f"topology-style:{identity}"))
                if style_rng.random() < 0.35:
                    dark = tuple(style_rng.randint(0, 75) for _ in range(3))
                    light = tuple(style_rng.randint(215, 255) for _ in range(3))
                else:
                    dark, light = (0, 0, 0), (255, 255, 255)
                for mask in masks:
                    qr = qrcode.QRCode(
                        version=version,
                        error_correction=error_corrections[correction_name],
                        box_size=8,
                        border=4,
                        mask_pattern=mask,
                    )
                    qr.add_data(payload)
                    try:
                        qr.make(fit=False)
                    except qrcode.exceptions.DataOverflowError as error:
                        raise ValueError(
                            "topology payload does not fit fixed QR version: "
                            f"V{version}/{correction_name}/{target_bytes} bytes"
                        ) from error
                    if qr.version != version or qr.modules_count != 17 + 4 * version:
                        raise AssertionError("fixed QR version/module contract drifted")
                    matrix_bits = "".join(
                        "1" if value else "0" for row in qr.modules for value in row
                    )
                    matrix_sha256 = hashlib.sha256(matrix_bits.encode()).hexdigest()
                    pristine = qr.make_image(
                        fill_color=dark, back_color=light
                    ).convert("RGB")
                    pristine = pristine.resize(
                        (IMG_SIZE, IMG_SIZE), Image.Resampling.NEAREST
                    )
                    for condition in conditions:
                        severity = "none" if condition == "normal" else "moderate"
                        image = (
                            pristine.copy()
                            if condition == "normal"
                            else apply_nuisance(
                                pristine,
                                condition,
                                severity,
                                seed=f"topology:{identity}:m{mask}:{condition}",
                            )
                        )
                        destination = (
                            counterfactual_dir
                            / split
                            / f"{identity}_m{mask}_{condition}.png"
                        )
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        if not destination.is_file():
                            image.save(destination)
                        rows.append(
                            {
                                "path": destination.relative_to(ROOT).as_posix(),
                                "label": "clean",
                                "class_id": 0,
                                "split": split,
                                "group_id": group_id,
                                "session_id": group_id,
                                "source": "procedural_qrguard_topology_counterfactual",
                                "capture_kind": "standards_valid_mask_counterfactual",
                                "quality_condition": condition,
                                "quality_severity": severity,
                                "image_source": "not_annotated",
                                "paired_group": group_id,
                                "physical_qr": group_id,
                                "payload_hash": payload_hash,
                                "attack_recipe": "none",
                                "is_exact_app_crop": False,
                                "licence": "project_generated",
                                "case_id": (
                                    f"TCF-V{version:02d}-{correction_name}-"
                                    f"{identity_index + 1}-M{mask}-{condition}"
                                ),
                                "qr_version": version,
                                "module_count": qr.modules_count,
                                "mask_pattern": mask,
                                "version_band": version_band,
                                "payload_length_bin": payload_bin,
                                "payload_utf8_bytes": target_bytes,
                                "qr_matrix_sha256": matrix_sha256,
                                "development_campaign": (
                                    "procedural-topology-counterfactual-2026-09-r01"
                                ),
                                "deployment_holdout_eligible": False,
                                "development_only": True,
                            }
                        )
    return rows


def generate_base_qrs() -> list[dict]:
    import qrcode

    total = sum(BASE_COUNTS.values())
    indices = list(range(total))
    random.Random(SEED).shuffle(indices)
    split_by_index = {}
    cursor = 0
    for split, count in BASE_COUNTS.items():
        for index in indices[cursor : cursor + count]:
            split_by_index[index] = split
        cursor += count

    base_dir = IMAGES / "base"
    base_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(total):
        rng = random.Random(_seed(f"base:{SEED}:{index}"))
        error_correction = rng.choice(
            [
                qrcode.constants.ERROR_CORRECT_L,
                qrcode.constants.ERROR_CORRECT_M,
                qrcode.constants.ERROR_CORRECT_Q,
                qrcode.constants.ERROR_CORRECT_H,
            ]
        )
        qr = qrcode.QRCode(
            version=None,
            error_correction=error_correction,
            box_size=rng.randint(6, 12),
            border=rng.randint(2, 6),
        )
        qr.add_data(_content(index, rng))
        qr.make(fit=True)
        if rng.random() < 0.35:
            dark = tuple(rng.randint(0, 90) for _ in range(3))
            light = tuple(rng.randint(200, 255) for _ in range(3))
        else:
            dark, light = (0, 0, 0), (255, 255, 255)
        image = qr.make_image(fill_color=dark, back_color=light).convert("RGB")
        image = image.resize((IMG_SIZE, IMG_SIZE), Image.Resampling.NEAREST)
        if error_correction == qrcode.constants.ERROR_CORRECT_H and rng.random() < 0.55:
            image = _add_logo(image, rng)
        elif rng.random() < 0.20:
            image = _add_logo(image, rng)
        path = base_dir / f"base_{index:05d}.png"
        if not path.is_file():
            image.save(path)
        rows.append(
            {
                "base_index": index,
                "base_path": path,
                "split": split_by_index[index],
                "group_id": f"synthetic_base:{index:05d}",
            }
        )
    return rows


def make_tampered(image: Image.Image, rng: random.Random, np_rng) -> Image.Image:
    pixels = np.asarray(image.resize((IMG_SIZE, IMG_SIZE)).convert("RGB")).copy()
    height, width = pixels.shape[:2]
    operations = rng.sample(
        ["sticker", "occlude", "finder", "scratch"], k=rng.randint(1, 2)
    )
    for operation in operations:
        if operation == "sticker":
            patch_width = rng.randint(width // 12, width // 3)
            patch_height = rng.randint(height // 12, height // 3)
            x = rng.randint(0, width - patch_width)
            y = rng.randint(0, height - patch_height)
            pixels[y : y + patch_height, x : x + patch_width] = rng.choice(
                [(255, 255, 255), (0, 0, 0), (220, 40, 40), (40, 120, 220)]
            )
        elif operation == "occlude":
            patch_width = rng.randint(width // 10, width // 2)
            patch_height = rng.randint(height // 12, height // 4)
            x = rng.randint(0, width - patch_width)
            y = rng.randint(0, height - patch_height)
            pixels[y : y + patch_height, x : x + patch_width] = rng.choice([0, 255])
        elif operation == "finder":
            y, x = rng.choice(
                [(0, 0), (0, width - width // 4), (height - height // 4, 0)]
            )
            side = width // 4
            pixels[y : y + side, x : x + side] = np_rng.integers(
                0, 256, (side, side, 3), dtype=np.uint8
            )
        else:
            for _ in range(rng.randint(1, 5)):
                cv2.line(
                    pixels,
                    (rng.randint(0, width - 1), rng.randint(0, height - 1)),
                    (rng.randint(0, width - 1), rng.randint(0, height - 1)),
                    rng.choice([0, 255]),
                    rng.randint(1, 5),
                )
    return Image.fromarray(pixels)


def _random_background(rng: random.Random, np_rng, size: int) -> np.ndarray:
    height = width = size
    kind = rng.choice(["wall", "wood", "paper", "gradient", "concrete"])
    background = np.zeros((height, width, 3), np.float32)
    if kind == "wall":
        background[:] = [rng.uniform(150, 238) for _ in range(3)]
        background += cv2.GaussianBlur(
            np_rng.normal(0, 14, background.shape).astype(np.float32), (0, 0), 9
        )
    elif kind == "wood":
        background[:] = [
            rng.uniform(120, 195),
            rng.uniform(85, 155),
            rng.uniform(55, 115),
        ]
        grain = np.sin(np.linspace(0, rng.uniform(8, 26), height) + rng.uniform(0, 6))
        background += (grain * rng.uniform(6, 20))[:, None, None]
        background += cv2.GaussianBlur(
            np_rng.normal(0, 9, background.shape).astype(np.float32), (0, 0), 3
        )
    elif kind == "paper":
        background[:] = [rng.uniform(205, 250) for _ in range(3)]
        background += np_rng.normal(0, 5, background.shape).astype(np.float32)
    elif kind == "gradient":
        start = np.asarray([rng.uniform(60, 240) for _ in range(3)], np.float32)
        end = np.asarray([rng.uniform(60, 240) for _ in range(3)], np.float32)
        if rng.random() < 0.5:
            ramp = np.tile(np.linspace(0, 1, width)[None, :, None], (height, 1, 1))
        else:
            ramp = np.tile(np.linspace(0, 1, height)[:, None, None], (1, width, 1))
        background = start * (1 - ramp) + end * ramp
    else:
        for weight, sigma in ((1, 21), (0.5, 7), (0.25, 3)):
            background += weight * cv2.GaussianBlur(
                np_rng.normal(0, 40, background.shape).astype(np.float32),
                (0, 0),
                sigma,
            )
        background += rng.uniform(110, 200)
    for _ in range(rng.randint(1, 4)):
        colour = tuple(float(rng.uniform(0, 255)) for _ in range(3))
        if rng.random() < 0.5:
            x, y = rng.randint(-width // 3, width), rng.randint(-height // 3, height)
            cv2.rectangle(
                background,
                (x, y),
                (
                    x + rng.randint(width // 6, width),
                    y + rng.randint(height // 6, height),
                ),
                colour,
                -1,
            )
        else:
            cv2.line(
                background,
                (rng.randint(0, width - 1), rng.randint(0, height - 1)),
                (rng.randint(0, width - 1), rng.randint(0, height - 1)),
                colour,
                rng.randint(2, 12),
            )
    return np.clip(cv2.GaussianBlur(background, (0, 0), rng.uniform(0.5, 2.5)), 0, 255)


def simulate_capture(image: Image.Image, rng: random.Random, np_rng) -> Image.Image:
    pixels = np.asarray(image.convert("RGB"), dtype=np.float32)
    height, width = pixels.shape[:2]
    scale = rng.uniform(0.55, 0.90)
    inner_height, inner_width = max(8, int(height * scale)), max(8, int(width * scale))
    inner = cv2.resize(
        pixels, (inner_width, inner_height), interpolation=cv2.INTER_AREA
    )
    canvas = _random_background(rng, np_rng, width)
    offset_y = rng.randint(0, height - inner_height)
    offset_x = rng.randint(0, width - inner_width)
    if rng.random() < 0.6:
        maximum_padding = max(
            3,
            min(
                offset_y,
                offset_x,
                height - offset_y - inner_height,
                width - offset_x - inner_width,
            )
            + 1,
        )
        padding = rng.randint(2, maximum_padding)
        sheet = float(rng.uniform(200, 255))
        canvas[
            max(0, offset_y - padding) : offset_y + inner_height + padding,
            max(0, offset_x - padding) : offset_x + inner_width + padding,
        ] = sheet
    canvas[offset_y : offset_y + inner_height, offset_x : offset_x + inner_width] = (
        inner
    )
    margin = rng.uniform(0.02, 0.12)

    def offset() -> float:
        return rng.uniform(-margin, margin)

    source = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    destination = np.float32(
        [
            [width * offset(), height * offset()],
            [width * (1 + offset()), height * offset()],
            [width * (1 + offset()), height * (1 + offset())],
            [width * offset(), height * (1 + offset())],
        ]
    )
    pixels = cv2.warpPerspective(
        canvas,
        cv2.getPerspectiveTransform(source, destination),
        (width, height),
        borderMode=cv2.BORDER_REFLECT,
    )
    grid_x, grid_y = np.meshgrid(np.linspace(-1, 1, width), np.linspace(-1, 1, height))
    angle = rng.uniform(0, 2 * math.pi)
    illumination = 1 + rng.uniform(0.05, 0.30) * (
        math.cos(angle) * grid_x + math.sin(angle) * grid_y
    )
    pixels *= illumination[:, :, None]
    reduction = rng.uniform(0.25, 0.80)
    small = cv2.resize(
        pixels,
        (max(8, int(width * reduction)), max(8, int(height * reduction))),
        interpolation=cv2.INTER_AREA,
    )
    pixels = cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR)
    kernel = rng.choice([3, 5])
    pixels = cv2.GaussianBlur(pixels, (kernel, kernel), rng.uniform(0.4, 1.4))
    pixels = np.clip(
        pixels + np_rng.normal(0, rng.uniform(1.0, 5.0), pixels.shape), 0, 255
    ).astype(np.uint8)
    ok, encoded = cv2.imencode(
        ".jpg",
        pixels[:, :, ::-1],
        [cv2.IMWRITE_JPEG_QUALITY, int(rng.uniform(55, 95))],
    )
    if ok:
        pixels = cv2.imdecode(encoded, cv2.IMREAD_COLOR)[:, :, ::-1]
    return Image.fromarray(pixels)


def _camera_if_selected(image: Image.Image, key: str) -> tuple[Image.Image, bool]:
    rng = random.Random(_seed(f"camera:{SEED}:{key}"))
    selected = rng.random() < CAMERA_FRACTION
    if not selected:
        return image, False
    np_rng = np.random.default_rng(_seed(f"camera-numpy:{SEED}:{key}"))
    return simulate_capture(image, rng, np_rng), True


def _derive_clean_and_tampered(base_rows: list[dict]) -> list[dict]:
    rows = []
    for position, base in enumerate(base_rows, 1):
        source = Image.open(base["base_path"]).convert("RGB")
        for label, class_name in ((0, "clean"), (2, "tampered")):
            key = f"{base['group_id']}:{class_name}"
            image = source.copy()
            if class_name == "tampered":
                rng = random.Random(_seed(f"tamper:{SEED}:{key}"))
                np_rng = np.random.default_rng(_seed(f"tamper-numpy:{SEED}:{key}"))
                image = make_tampered(image, rng, np_rng)
            if IS_V3:
                # The condition is controlled and recorded. It is nuisance
                # context, never a Structural target. Severe/unreadable cases
                # are reserved for the quality-abstention evaluation gate.
                condition = V3_CONDITION_CHOICES[
                    _seed(f"condition:{SEED}:{key}") % len(V3_CONDITION_CHOICES)
                ]
                severity = (
                    "none"
                    if condition == "normal"
                    else ("mild", "moderate")[_seed(f"severity:{key}") % 2]
                )
                image = apply_nuisance(image, condition, severity, seed=key)
                camera_simulated = condition != "normal"
            else:
                image, camera_simulated = _camera_if_selected(image, key)
                condition = "not_annotated"
                severity = "not_annotated"
            destination = (
                IMAGES / base["split"] / class_name / f"{base['base_index']:05d}.png"
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.is_file():
                image.save(destination)
            rows.append(
                {
                    "path": destination.relative_to(ROOT).as_posix(),
                    "label": class_name,
                    "class_id": label,
                    "split": base["split"],
                    "group_id": base["group_id"],
                    "source": "procedural_qrguard",
                    "capture_kind": "camera_simulated"
                    if camera_simulated
                    else "pristine",
                    "quality_condition": condition,
                    "quality_severity": severity,
                    "attack_recipe": "none"
                    if class_name == "clean"
                    else "physical_overlay",
                    "is_exact_app_crop": False,
                    "licence": "project_generated",
                }
            )
        if position % 250 == 0:
            print(f"prepared clean/tampered {position}/{len(base_rows)}")
    return rows


def _derive_adversarial(base_rows: list[dict]) -> list[dict]:
    import torch
    import torch.nn as nn
    import torch.nn.functional as functional
    from torchvision import models, transforms

    torch.manual_seed(SEED)
    torch.set_num_threads(min(6, max(1, torch.get_num_threads())))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(
        "Adversarial generation device:",
        torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
    )
    weights = models.ResNet18_Weights.IMAGENET1K_V1
    print(f"Loading adversarial victim weights: {weights.url}", flush=True)
    victim = models.resnet18(weights=weights).eval()

    class Normalized(nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model
            self.register_buffer(
                "mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
            )
            self.register_buffer(
                "std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
            )

        def forward(self, inputs):
            return self.model((inputs - self.mean) / self.std)

    # Moving only `victim` leaves this wrapper's registered mean/std buffers on
    # CPU. Move the wrapper so the model, normalisation buffers and input batch
    # all share cuda:0 on Colab's T4 runtime.
    model = Normalized(victim).to(device).eval()
    to_tensor = transforms.ToTensor()
    pending = {"fgsm": [], "pgd20": []}
    rows = []
    for base in base_rows:
        attack = "fgsm" if _seed(f"attack:{base['group_id']}") % 2 == 0 else "pgd20"
        destination = (
            IMAGES / base["split"] / "adversarial" / f"{base['base_index']:05d}.png"
        )
        record = (base, destination, attack)
        if destination.is_file():
            rows.append(_adversarial_row(base, destination, attack))
        else:
            pending[attack].append(record)

    for attack, records in pending.items():
        for start in range(0, len(records), 16):
            batch = records[start : start + 16]
            originals = torch.stack(
                [
                    to_tensor(
                        Image.open(base["base_path"])
                        .convert("RGB")
                        .resize((IMG_SIZE, IMG_SIZE))
                    )
                    for base, _, _ in batch
                ]
            ).to(device)
            with torch.no_grad():
                labels = model(originals).argmax(1)
            eps = torch.tensor(
                [
                    random.Random(_seed(f"eps:{base['group_id']}")).uniform(0.004, 0.05)
                    for base, _, _ in batch
                ],
                dtype=originals.dtype,
                device=device,
            ).view(-1, 1, 1, 1)
            if attack == "fgsm":
                candidate = originals.detach().clone().requires_grad_(True)
                loss = functional.cross_entropy(model(candidate), labels)
                gradient = torch.autograd.grad(loss, candidate)[0]
                adversarial = torch.clamp(originals + eps * gradient.sign(), 0, 1)
            else:
                candidate = originals.detach().clone()
                alpha = eps / 8
                for _ in range(20):
                    candidate.requires_grad_(True)
                    loss = functional.cross_entropy(model(candidate), labels)
                    gradient = torch.autograd.grad(loss, candidate)[0]
                    candidate = candidate.detach() + alpha * gradient.sign()
                    candidate = torch.maximum(
                        torch.minimum(candidate, originals + eps), originals - eps
                    )
                    candidate = torch.clamp(candidate, 0, 1)
                adversarial = candidate
            for tensor, (base, destination, attack_name) in zip(
                adversarial, batch, strict=True
            ):
                array = (
                    (tensor.detach().cpu().numpy().transpose(1, 2, 0).clip(0, 1) * 255)
                    .round()
                    .astype(np.uint8)
                )
                # Standard FGSM/PGD is a digital-input threat. Applying strong
                # camera/JPEG simulation after the attack destroys the bounded
                # perturbation and creates a mislabeled near-clean photograph.
                # Physical adversarial attacks require EOT plus real recapture;
                # those remain part of the exact app-crop collection gate.
                image = Image.fromarray(array)
                destination.parent.mkdir(parents=True, exist_ok=True)
                image.save(destination)
                rows.append(_adversarial_row(base, destination, attack_name))
            completed = min(start + len(batch), len(records))
            print(f"prepared {attack} adversarial {completed}/{len(records)}")
    # A fresh build appends generated rows attack-by-attack (FGSM, then PGD),
    # while a cache hit used to append them in base-row order. That made the
    # manifest byte identity depend on whether image files already existed.
    # Canonicalise the rows so fresh and cached preparation are identical.
    return _canonical_adversarial_rows(rows)


def _canonical_adversarial_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (row["group_id"], row["attack_recipe"], row["path"]),
    )


def _adversarial_row(base: dict, destination: Path, attack: str) -> dict:
    return {
        "path": destination.relative_to(ROOT).as_posix(),
        "label": "adversarial",
        "class_id": 1,
        "split": base["split"],
        "group_id": base["group_id"],
        "source": "procedural_qrguard",
        "capture_kind": "digital_input",
        "quality_condition": "normal",
        "quality_severity": "none",
        "attack_recipe": attack,
        "is_exact_app_crop": False,
        "licence": "project_generated",
    }


def _external_clean_rows() -> list[dict]:
    qrdn = list(
        csv.DictReader(
            (ROOT / "ml_training/datasets/structural/processed/qrdn/manifest.csv").open(
                encoding="utf-8"
            )
        )
    )
    rows = []
    for row in qrdn:
        qr_identity = int(row["qr_identity"])
        if row["official_split"] == "test":
            split = "external_holdout_test"
        else:
            split = "train" if qr_identity < 40 else "validation"
        rows.append(
            {
                "path": row["path"],
                "label": "clean",
                "class_id": 0,
                "split": split,
                "group_id": row["group_id"],
                "source": "QR-DN1.0",
                "capture_kind": "real_screen_camera_watermark_extraction",
                "attack_recipe": "none",
                "is_exact_app_crop": False,
                "licence": "CC-BY-4.0",
            }
        )
    surfaces_manifest = (
        ROOT / "ml_training/datasets/structural/processed/qr_surfaces/manifest.csv"
    )
    for row in csv.DictReader(surfaces_manifest.open(encoding="utf-8")):
        rows.append(
            {
                "path": row["path"],
                "label": "clean",
                "class_id": 0,
                "split": "train",
                "group_id": row["group_id"],
                "source": "qr_codes_in_surfaces",
                "capture_kind": "external_real_camera",
                "attack_recipe": "none",
                "is_exact_app_crop": False,
                "licence": "CC-BY-4.0",
            }
        )
    return rows


def _runtime_capture_rows() -> list[dict]:
    """Load exact crops produced by the QRGuard app capture contract.

    Training and validation frames are allowed into their matching grouped
    splits. Test sessions remain a separate, untouched runtime holdout so they
    can decide deployment rather than merely improve an aggregate metric.
    """
    capture_root = ROOT / "data/runtime_captures"
    v3_manifest = capture_root / "manifest_v3.csv"
    manifest = v3_manifest if IS_V3 else capture_root / "manifest.csv"
    if not manifest.is_file():
        return []
    split_map = {
        "train": "train",
        "val": "validation",
        "validation": "validation",
        "test": "runtime_holdout_test",
    }
    rows = []
    for capture in csv.DictReader(manifest.open(encoding="utf-8")):
        if IS_V3 and str(capture.get("is_authoritative", "")).lower() != "true":
            continue
        label = capture.get("label", "") if IS_V3 else capture.get("label_name", "")
        split_name = capture.get("split", "")
        split = (
            "runtime_holdout_test"
            if IS_V3 and split_name == "test"
            else split_map.get(split_name)
        )
        relative_crop = (
            capture.get("sample_path", "") if IS_V3 else capture.get("crop_path", "")
        )
        crop = capture_root / relative_crop
        if label not in CLASS_NAMES or split is None or not crop.is_file():
            continue
        group_token = capture.get("payload_hash", "") if IS_V3 else capture["group_id"]
        image_source = capture.get("image_source", "camera")
        if (
            IS_V3
            and capture.get("quality_severity", "none").strip().lower() == "severe"
        ):
            # Runtime quality handling abstains before Structural inference.
            # Keep severe evidence in manifest_v3 for the abstention report, not
            # as a clean/adversarial/tampered classifier training row.
            continue
        rows.append(
            {
                "path": crop.relative_to(ROOT).as_posix(),
                "label": label,
                "class_id": CLASS_NAMES.index(label),
                "split": split,
                "group_id": f"qrguard_runtime:{group_token}",
                "session_id": capture.get(
                    "capture_session", capture.get("session_id", "not_recorded")
                ),
                "source": (
                    f"qrguard_runtime_v3_{image_source}" if IS_V3 else "qrguard_runtime"
                ),
                "capture_kind": "exact_app_crop",
                "device_model": capture.get(
                    "device", capture.get("device_model", "not_recorded")
                ),
                "quality_condition": capture.get("quality_condition", "not_annotated"),
                "quality_severity": capture.get("quality_severity", "not_annotated"),
                "image_source": image_source,
                "paired_group": capture.get("paired_group", group_token),
                "physical_qr": capture.get("physical_qr", group_token),
                "payload_hash": capture.get("payload_hash", group_token),
                "attack_recipe": "human_verified_ground_truth",
                "is_exact_app_crop": True,
                "licence": "project_internal_opt_in",
            }
        )
    return rows


def _dataset_reference_version(key: str, default: str) -> str:
    config_path = ROOT / "ml_training/configs" / f"{VERSION}.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return str(config.get("dataset_references", {}).get(key, default))
    return default


def _optional_dataset_reference_version(key: str) -> str | None:
    config_path = ROOT / "ml_training/configs" / f"{VERSION}.json"
    if not config_path.is_file():
        return None
    config = json.loads(config_path.read_text(encoding="utf-8"))
    value = config.get("dataset_references", {}).get(key)
    return str(value) if value else None


def _development_release_directory(key: str, version: str) -> str:
    """Map immutable dataset versions to readable local directory labels."""
    labels = {
        "physical_attack_development_version": {
            "2026-09-r02": "physical_attack_release_r02",
        },
        "acquisition_quality_development_version": {
            "2026-09-r02": "acquisition_quality_release_r02",
        },
        "consumed_blind_development_version": {
            "2026-09-r01": "consumed_blind_clean_release_r01",
        },
    }
    return labels.get(key, {}).get(version, version)


def _prepared_gallery_reference_rows() -> list[dict]:
    """Load verified non-test digital references paired with Camera captures."""
    if not IS_V3:
        return []
    reference_version = _dataset_reference_version(
        "prepared_gallery_version", VERSION
    )
    manifest = (
        ROOT
        / "data/prepared_gallery_references"
        / reference_version
        / "manifest.csv"
    )
    if not manifest.is_file():
        return []
    rows = []
    for reference in csv.DictReader(manifest.open(encoding="utf-8")):
        label = reference.get("label", "")
        split = reference.get("split", "")
        path = ROOT / reference.get("path", "")
        if label not in CLASS_NAMES:
            raise ValueError(f"invalid prepared Gallery label: {label!r}")
        if split not in {"train", "validation"}:
            raise ValueError(
                "prepared Gallery references must exclude the locked test split: "
                f"{reference.get('case_id', path.name)} -> {split!r}"
            )
        if not path.is_file():
            raise FileNotFoundError(f"prepared Gallery reference not found: {path}")
        payload_hash = reference.get("payload_hash", "")
        if len(payload_hash) != 64:
            raise ValueError(f"invalid prepared Gallery payload hash: {path}")
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "label": label,
                "class_id": CLASS_NAMES.index(label),
                "split": split,
                "group_id": f"qrguard_runtime:{payload_hash}",
                "session_id": reference.get(
                    "session_id", f"prepared-gallery:{path.stem}"
                ),
                "source": "qrguard_prepared_gallery_reference",
                "capture_kind": "prepared_gallery_reference",
                "device_model": "digital-reference",
                "quality_condition": reference.get("quality_condition", "normal"),
                "quality_severity": reference.get("quality_severity", "none"),
                "image_source": "gallery",
                "paired_group": reference.get("paired_group", payload_hash),
                "physical_qr": reference.get("physical_qr", payload_hash),
                "payload_hash": payload_hash,
                "attack_recipe": reference.get("attack_recipe", "none"),
                "is_exact_app_crop": False,
                "licence": reference.get("licence", "project_generated_internal"),
            }
        )
    return rows


def _coverage_development_rows() -> list[dict]:
    """Load the M5 low/medium/high-Version development frames for 2026.09."""
    if not VERSION.startswith(("structural-2026.09", "structural-r07")):
        return []
    manifest = ROOT / "data/structural_coverage_development/coverage_development_release_r01/manifest.csv"
    if not manifest.is_file():
        raise FileNotFoundError(f"M5 coverage development manifest missing: {manifest}")
    rows = list(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
    if len(rows) != 240:
        raise ValueError(
            f"M5 coverage manifest must contain 240 frames, got {len(rows)}"
        )
    for row in rows:
        if row.get("split") not in {"train", "validation"}:
            raise ValueError(f"M5 row has invalid development split: {row.get('path')}")
        if str(row.get("deployment_holdout_eligible", "")).lower() != "false":
            raise ValueError(f"M5 row cannot be holdout eligible: {row.get('path')}")
        path = ROOT / str(row.get("path", ""))
        if not path.is_file():
            raise FileNotFoundError(f"M5 development crop missing: {path}")
    return rows


def _physical_attack_development_rows() -> list[dict]:
    """Load only clean and verified-surviving physical r02 development frames."""
    if not VERSION.startswith(("structural-2026.09", "structural-r07")):
        return []
    reference_version = _dataset_reference_version(
        "physical_attack_development_version", "2026-09-r02"
    )
    manifest = (
        ROOT
        / "data/structural_physical_attack_development"
        / _development_release_directory(
            "physical_attack_development_version", reference_version
        )
        / "manifest.csv"
    )
    if not manifest.is_file():
        raise FileNotFoundError(
            f"physical-attack development manifest missing: {manifest}"
        )
    rows = list(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
    if len(rows) != 130:
        raise ValueError(
            "physical-attack manifest must contain 130 admitted frames, got "
            f"{len(rows)}"
        )
    attack_rows = [row for row in rows if row.get("label") == "adversarial"]
    if len(attack_rows) != 50 or any(
        str(row.get("physical_attack_survival_verified", "")).lower() != "true"
        for row in attack_rows
    ):
        raise ValueError(
            "physical-attack classifier rows must be exactly 50 "
            "verified-surviving frames"
        )
    if any(
        str(row.get("deployment_holdout_eligible", "")).lower() != "false"
        or row.get("split") not in {"train", "validation"}
        for row in rows
    ):
        raise ValueError("physical development rows cannot become deployment holdout")
    for row in rows:
        path = ROOT / str(row.get("path", ""))
        if not path.is_file():
            raise FileNotFoundError(f"physical development crop missing: {path}")
    return rows


def _acquisition_quality_development_rows() -> list[dict]:
    """Load explicitly admitted clean hard negatives after r03 diagnosis."""
    reference_version = _optional_dataset_reference_version(
        "acquisition_quality_development_version"
    )
    if reference_version is None:
        return []
    root = (
        ROOT
        / "data/acquisition_quality_development"
        / _development_release_directory(
            "acquisition_quality_development_version", reference_version
        )
    )
    manifest = root / "manifest.csv"
    audit_path = root / "audit.json"
    if not manifest.is_file() or not audit_path.is_file():
        raise FileNotFoundError(
            f"acquisition-quality development evidence missing: {root}"
        )
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
    if len(rows) != 90 or audit.get("admitted_clean_frames") != 90:
        raise ValueError(
            "acquisition-quality development evidence must contain 90 clean frames"
        )
    if audit.get("source_archive_sha256") != (
        "02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4"
    ):
        raise ValueError("acquisition-quality source archive identity mismatch")
    if any(
        row.get("label") != "clean"
        or row.get("split") != "train"
        or str(row.get("development_only", "")).lower() != "true"
        or str(row.get("deployment_holdout_eligible", "")).lower() != "false"
        for row in rows
    ):
        raise ValueError(
            "acquisition-quality rows must remain clean, train-only development data"
        )
    for row in rows:
        path = ROOT / str(row.get("path", ""))
        if not path.is_file():
            raise FileNotFoundError(
                f"acquisition-quality development crop missing: {path}"
            )
        if _sha256(path) != row.get("crop_sha256"):
            raise ValueError(
                f"acquisition-quality development crop hash mismatch: {path}"
            )
    return rows


def _consumed_blind_clean_development_rows() -> list[dict]:
    """Load clean hard negatives from the unblinded M8 development replay.

    The source campaign is permanently ineligible for promotion.  Only its
    clean crops are admitted; physical attack rows remain excluded because the
    old capture did not provide enough verified surviving attacks.
    """
    reference_version = _optional_dataset_reference_version(
        "consumed_blind_development_version"
    )
    if reference_version is None:
        return []
    root = (
        ROOT
        / "data/structural_consumed_blind_development"
        / _development_release_directory(
            "consumed_blind_development_version", reference_version
        )
    )
    manifest = root / "manifest.csv"
    audit_path = root / "audit.json"
    if not manifest.is_file() or not audit_path.is_file():
        raise FileNotFoundError(f"consumed M8 development evidence missing: {root}")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
    if (
        len(rows) != 80
        or audit.get("admitted_clean_frames") != 80
        or audit.get("source_archive_sha256")
        != "d5930ffcaf1edc0702afd5ff2b2241584a95edd9f9f0de81fdc8a5a5a7921f6d"
        or audit.get("source_holdout_consumed") is not True
        or audit.get("promotion_eligible") is not False
    ):
        raise ValueError("consumed M8 clean development evidence contract mismatch")
    if Counter(row.get("split") for row in rows) != {
        "train": 60,
        "validation": 20,
    }:
        raise ValueError("consumed M8 clean split must remain 60/20")
    if any(
        row.get("label") != "clean"
        or row.get("source")
        != "qrguard_consumed_blind_clean_2026_09_camera"
        or str(row.get("blind_holdout_consumed", "")).lower() != "true"
        or str(row.get("development_only", "")).lower() != "true"
        or str(row.get("deployment_holdout_eligible", "")).lower() != "false"
        or str(row.get("promotion_eligible", "")).lower() != "false"
        for row in rows
    ):
        raise ValueError("consumed M8 rows escaped their non-promoting clean contract")
    group_splits: dict[str, set[str]] = {}
    for row in rows:
        path = ROOT / str(row.get("path", ""))
        if not path.is_file():
            raise FileNotFoundError(f"consumed M8 development crop missing: {path}")
        if _sha256(path) != row.get("crop_sha256"):
            raise ValueError(f"consumed M8 crop hash mismatch: {path}")
        group_splits.setdefault(str(row["group_id"]), set()).add(str(row["split"]))
    if len(group_splits) != 16 or any(
        len(splits) != 1 for splits in group_splits.values()
    ):
        raise ValueError("consumed M8 QR identities leak across development splits")
    return rows


def prepare_dataset() -> Path:
    required_manifests = {
        "QR-DN1.0": ROOT
        / "ml_training/datasets/structural/processed/qrdn/manifest.csv",
        "QR Codes in Surfaces": ROOT
        / "ml_training/datasets/structural/processed/qr_surfaces/manifest.csv",
    }
    missing = [name for name, path in required_manifests.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Phase 2 did not produce the required manifest(s): "
            + ", ".join(missing)
            + ". Rerun Phase 2 before Phase 4."
        )
    print("Preparing 1,260 grouped synthetic QR identities...", flush=True)
    base = generate_base_qrs()
    print("Generating clean and physically tampered variants...", flush=True)
    rows = _derive_clean_and_tampered(base)
    topology_rows = generate_topology_counterfactual_clean_rows()
    if topology_rows:
        print(
            f"Generated {len(topology_rows):,} grouped clean mask counterfactuals.",
            flush=True,
        )
        rows.extend(topology_rows)
    print("Generating FGSM/PGD adversarial variants...", flush=True)
    rows.extend(_derive_adversarial(base))
    rows.extend(_external_clean_rows())
    rows.extend(_runtime_capture_rows())
    rows.extend(_prepared_gallery_reference_rows())
    rows.extend(_coverage_development_rows())
    rows.extend(_physical_attack_development_rows())
    rows.extend(_acquisition_quality_development_rows())
    rows.extend(_consumed_blind_clean_development_rows())
    for row in rows:
        row.setdefault("session_id", row["group_id"])
        row.setdefault("device_model", "not_recorded")
        row.setdefault("display_id", "not_recorded")
        row.setdefault("quality_condition", "not_annotated")
        row.setdefault("quality_severity", "not_annotated")
        row.setdefault("image_source", "not_annotated")
        row.setdefault("paired_group", row["group_id"])
        row.setdefault("physical_qr", row["group_id"])
        row.setdefault("payload_hash", row["group_id"])
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    split_groups = {
        split: {row["group_id"] for row in rows if row["split"] == split}
        for split in (
            "train",
            "validation",
            "test",
            "external_holdout_test",
            "runtime_holdout_test",
        )
    }
    split_names = list(split_groups)
    for left_index, left in enumerate(split_names):
        for right in split_names[left_index + 1 :]:
            overlap = split_groups[left] & split_groups[right]
            if overlap:
                raise AssertionError(
                    f"group leakage {left}/{right}: {sorted(overlap)[:3]}"
                )
    audit = {
        "version": VERSION,
        "rows": len(rows),
        "counts": {
            f"{split}/{label}": sum(
                row["split"] == split and row["label"] == label for row in rows
            )
            for split in sorted({row["split"] for row in rows})
            for label in CLASS_NAMES
        },
        "groups": {split: len(groups) for split, groups in split_groups.items()},
        "camera_fraction": CAMERA_FRACTION if not IS_V3 else None,
        "controlled_nuisance_fraction": (
            sum(condition != "normal" for condition in V3_CONDITION_CHOICES)
            / len(V3_CONDITION_CHOICES)
            if IS_V3
            else None
        ),
        "adversarial_recipes": (
            "Gallery/digital-input FGSM and untargeted PGD-20, epsilon 0.004-0.05; "
            "no post-attack camera simulation because it invalidates the attack label"
        ),
        "exact_app_crop_rows": sum(
            str(row["is_exact_app_crop"]).lower() == "true" for row in rows
        ),
        "acquisition_quality_development_rows": sum(
            row.get("source") == "qrguard_acquisition_quality_2026_09_camera"
            for row in rows
        ),
        "consumed_blind_clean_development_rows": sum(
            row.get("source")
            == "qrguard_consumed_blind_clean_2026_09_camera"
            for row in rows
        ),
        "topology_counterfactual_clean_rows": sum(
            row.get("source")
            == "procedural_qrguard_topology_counterfactual"
            for row in rows
        ),
        "topology_counterfactual_groups": len(
            {
                row["group_id"]
                for row in rows
                if row.get("source")
                == "procedural_qrguard_topology_counterfactual"
            }
        ),
        "deployment_note": (
            "External camera data improves domain coverage but exact QRGuard app crops "
            "remain mandatory for final Structural deployment approval."
        ),
    }
    (PROCESSED / "preparation_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))
    return MANIFEST


if __name__ == "__main__":
    prepare_dataset()
