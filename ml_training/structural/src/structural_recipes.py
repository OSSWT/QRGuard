"""Reproducible data recipes for the local Structural Training candidate."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
VERSION = "structural-2026.02"
PROCESSED = ROOT / "ml_training/datasets/structural/processed" / VERSION
IMAGES = PROCESSED / "images"
MANIFEST = PROCESSED / "manifest.csv"
IMG_SIZE = 224
SEED = 42
BASE_COUNTS = {"train": 900, "validation": 180, "test": 180}
CAMERA_FRACTION = 0.70
CLASS_NAMES = ("clean", "adversarial", "tampered")


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
    offset = lambda: rng.uniform(-margin, margin)
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
            image, camera_simulated = _camera_if_selected(image, key)
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
    return rows


def _adversarial_row(base: dict, destination: Path, attack: str) -> dict:
    return {
        "path": destination.relative_to(ROOT).as_posix(),
        "label": "adversarial",
        "class_id": 1,
        "split": base["split"],
        "group_id": base["group_id"],
        "source": "procedural_qrguard",
        "capture_kind": "digital_input",
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
    manifest = capture_root / "manifest.csv"
    if not manifest.is_file():
        return []
    split_map = {
        "train": "train",
        "val": "validation",
        "test": "runtime_holdout_test",
    }
    rows = []
    for capture in csv.DictReader(manifest.open(encoding="utf-8")):
        label = capture.get("label_name", "")
        split = split_map.get(capture.get("split", ""))
        crop = capture_root / capture.get("crop_path", "")
        if label not in CLASS_NAMES or split is None or not crop.is_file():
            continue
        rows.append(
            {
                "path": crop.relative_to(ROOT).as_posix(),
                "label": label,
                "class_id": CLASS_NAMES.index(label),
                "split": split,
                "group_id": f"qrguard_runtime:{capture['group_id']}",
                "session_id": capture.get("session_id", "not_recorded"),
                "source": "qrguard_runtime",
                "capture_kind": "exact_app_crop",
                "device_model": capture.get("device_model", "not_recorded"),
                "attack_recipe": "human_verified_ground_truth",
                "is_exact_app_crop": True,
                "licence": "project_internal_opt_in",
            }
        )
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
    print("Generating FGSM/PGD adversarial variants...", flush=True)
    rows.extend(_derive_adversarial(base))
    rows.extend(_external_clean_rows())
    rows.extend(_runtime_capture_rows())
    for row in rows:
        row.setdefault("session_id", row["group_id"])
        row.setdefault("device_model", "not_recorded")
    fields = list(rows[0])
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
        "camera_fraction": CAMERA_FRACTION,
        "adversarial_recipes": (
            "Gallery/digital-input FGSM and untargeted PGD-20, epsilon 0.004-0.05; "
            "no post-attack camera simulation because it invalidates the attack label"
        ),
        "exact_app_crop_rows": sum(
            str(row["is_exact_app_crop"]).lower() == "true" for row in rows
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
