"""Prepare verified adversarial and documented tampered references for 50x3.

The script transforms only the generated hand-off pack. It preserves the QR
payload, verifies every final PNG with OpenCV, records attack/manipulation
provenance, updates the scoped selection, and rebuilds the ZIP atomically.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_numbered_capture_pack import _write_slideshow

CAMPAIGN_ID = "structural-v3-real-2026.03-r01"
PACK_NAME = f"{CAMPAIGN_ID}-50x3-r01"
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
ATTACK_SIZE = 224
DISPLAY_SIZE = 896


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decode(path: Path, detector: cv2.QRCodeDetector) -> str:
    image = cv2.imread(str(path))
    decoded, _, _ = detector.detectAndDecode(image)
    return decoded


def _write_tampered(
    source: Path,
    destination: Path,
    expected_payload: str,
    seed: str,
    detector: cv2.QRCodeDetector,
) -> dict[str, object]:
    image = Image.open(source).convert("RGB")
    width, height = image.size
    rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
    centres = [
        (0.50, 0.50),
        (0.63, 0.50),
        (0.50, 0.63),
        (0.37, 0.50),
        (0.50, 0.37),
    ]
    rng.shuffle(centres)
    colours = [(215, 36, 46), (34, 110, 210), (20, 20, 20)]
    for fraction in (0.12, 0.10, 0.08, 0.06):
        for centre_x, centre_y in centres:
            candidate = image.copy()
            draw = ImageDraw.Draw(candidate)
            side = round(min(width, height) * fraction)
            left = round(width * centre_x - side / 2)
            top = round(height * centre_y - side / 2)
            box = (left, top, left + side, top + side)
            border = max(2, side // 14)
            draw.rounded_rectangle(box, radius=border * 2, fill=colours[side % 3])
            draw.rounded_rectangle(
                (left + border, top + border, left + side - border, top + side - border),
                radius=border,
                outline=(255, 255, 255),
                width=border,
            )
            candidate.save(destination)
            if _decode(destination, detector) == expected_payload:
                return {
                    "method": "sticker_overlay",
                    "overlay_fraction": fraction,
                    "overlay_box": list(box),
                    "decoder_verified": True,
                }
    raise RuntimeError(f"could not create a decodable tampered QR: {source}")


def _load_victim(checkpoint: Path):
    import torch
    from torchvision import models

    victim = models.resnet18(weights=None)
    victim.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    victim.eval()
    for parameter in victim.parameters():
        parameter.requires_grad_(False)
    return victim


def _normalise(tensor):
    import torch

    mean = torch.tensor(IMAGENET_MEAN, dtype=tensor.dtype).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD, dtype=tensor.dtype).view(1, 3, 1, 1)
    return (tensor - mean) / std


def _eot_views(tensor):
    import torch
    from torch.nn import functional

    variants = []
    settings = (
        (1.00, 1.00, 224, 0, 0),
        (0.90, 1.08, 208, 2, -2),
        (1.08, 0.92, 196, -2, 2),
        (0.96, 1.04, 184, 3, 1),
        (1.04, 0.96, 172, -1, -3),
        (0.86, 1.12, 160, 2, 2),
    )
    for brightness, contrast, inner_size, shift_y, shift_x in settings:
        view = tensor * contrast + (brightness - contrast) * 0.5
        if inner_size != ATTACK_SIZE:
            view = functional.interpolate(
                view, size=(inner_size, inner_size), mode="bilinear", align_corners=False
            )
            view = functional.interpolate(
                view,
                size=(ATTACK_SIZE, ATTACK_SIZE),
                mode="bilinear",
                align_corners=False,
            )
        view = torch.roll(view, shifts=(shift_y, shift_x), dims=(2, 3))
        variants.append(view.clamp(0, 1))
    return torch.cat(variants)


def _attack_array(source: Path, victim) -> tuple[np.ndarray, dict[str, object]]:
    import torch
    from torch.nn import functional
    from torchvision.transforms.functional import pil_to_tensor

    image = Image.open(source).convert("RGB").resize(
        (ATTACK_SIZE, ATTACK_SIZE), Image.Resampling.BILINEAR
    )
    original = pil_to_tensor(image).float().unsqueeze(0) / 255.0
    with torch.no_grad():
        baseline_logits = victim(_normalise(_eot_views(original)))
        baseline_label = int(victim(_normalise(original)).argmax(1).item())
        baseline_consistency = float(
            (baseline_logits.argmax(1) == baseline_label).float().mean().item()
        )

    candidate = original.detach().clone().requires_grad_(True)
    labels = torch.full(
        (_eot_views(candidate).shape[0],), baseline_label, dtype=torch.long
    )
    loss = functional.cross_entropy(victim(_normalise(_eot_views(candidate))), labels)
    gradient = torch.autograd.grad(loss, candidate)[0].sign()

    best = None
    for epsilon_pixels in (8, 12, 16, 20, 24, 32):
        adversarial = (original + (epsilon_pixels / 255.0) * gradient).clamp(0, 1)
        with torch.no_grad():
            predictions = victim(_normalise(_eot_views(adversarial))).argmax(1)
            success_rate = float((predictions != baseline_label).float().mean().item())
        best = (adversarial, epsilon_pixels, success_rate)
        if success_rate >= 0.5:
            break
    assert best is not None
    adversarial, epsilon_pixels, success_rate = best
    array = (
        adversarial[0].detach().numpy().transpose(1, 2, 0).clip(0, 1) * 255
    ).round().astype(np.uint8)
    return array, {
        "method": "eot_fgsm",
        "epsilon_pixels": epsilon_pixels,
        "epsilon_linf": epsilon_pixels / 255.0,
        "eot_transform_count": 6,
        "victim_baseline_class": baseline_label,
        "victim_baseline_consistency": baseline_consistency,
        "verified_eot_success_rate": success_rate,
    }


def _write_adversarial(
    source: Path,
    destination: Path,
    expected_payload: str,
    detector: cv2.QRCodeDetector,
    victim,
) -> dict[str, object]:
    array, provenance = _attack_array(source, victim)
    for interpolation in (Image.Resampling.NEAREST, Image.Resampling.BILINEAR):
        Image.fromarray(array).resize((DISPLAY_SIZE, DISPLAY_SIZE), interpolation).save(
            destination
        )
        if _decode(destination, detector) == expected_payload:
            provenance["decoder_verified"] = True
            provenance["display_size"] = DISPLAY_SIZE
            provenance["resize_interpolation"] = interpolation.name.lower()
            return provenance
    raise RuntimeError(f"EOT attack is not QR-decodable: {source}")


def _write_index_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for name in row:
            if name not in fieldnames:
                fieldnames.append(name)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def prepare(pack: Path, selection_path: Path, archive: Path, checkpoint: Path) -> None:
    index_path = pack / "capture_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selected_by_id = {
        str(item["case_id"]): item for item in selection["selected_cases"]
    }
    detector = cv2.QRCodeDetector()
    victim = None
    victim_sha256 = _sha256(checkpoint)

    for position, row in enumerate(index["rows"], start=1):
        number = int(row["number"])
        case_id = str(row["case_id"])
        label = str(row["label"])
        image_path = pack / "scan_with_gallery" / f"{number}.png"
        metadata_path = pack / "reference_metadata" / f"{number}.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expected_hash = str(row["payload_sha256"])
        decoded = _decode(image_path, detector)
        if hashlib.sha256(decoded.encode()).hexdigest() != expected_hash:
            raise ValueError(f"base payload mismatch for {case_id}")

        prepared = metadata.get("prepared_reference")
        if isinstance(prepared, dict) and prepared.get("capture_ready") is True:
            final_hash = _sha256(image_path)
            if prepared.get("reference_sha256") != final_hash:
                raise ValueError(f"prepared reference hash mismatch for {case_id}")
        elif label == "adversarial":
            if victim is None:
                victim = _load_victim(checkpoint)
            base_hash = _sha256(image_path)
            provenance = _write_adversarial(
                image_path, image_path, decoded, detector, victim
            )
            final_hash = _sha256(image_path)
            prepared = {
                "capture_ready": True,
                "base_reference_sha256": base_hash,
                "reference_sha256": final_hash,
                "attack_method": "eot_fgsm",
                "attack_reference_sha256": final_hash,
                "victim_checkpoint_sha256": victim_sha256,
                **provenance,
            }
        elif label == "tampered":
            base_hash = _sha256(image_path)
            provenance = _write_tampered(
                image_path, image_path, decoded, case_id, detector
            )
            final_hash = _sha256(image_path)
            prepared = {
                "capture_ready": True,
                "base_reference_sha256": base_hash,
                "reference_sha256": final_hash,
                "manipulation_method": "sticker_overlay",
                **provenance,
            }
        else:
            final_hash = _sha256(image_path)
            prepared = {
                "capture_ready": True,
                "reference_sha256": final_hash,
                "attack_method": "none",
                "attack_reference_sha256": "",
                "manipulation_method": "none",
                "decoder_verified": True,
            }

        if _decode(image_path, detector) != decoded:
            raise ValueError(f"final payload changed for {case_id}")
        metadata["reference_image_sha256"] = final_hash
        metadata["prepared_reference"] = prepared
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        row["capture_ready"] = True
        row["readiness_reason"] = (
            "verified_eot_fgsm"
            if label == "adversarial"
            else "documented_sticker_overlay"
            if label == "tampered"
            else "ready_clean_reference"
        )
        row["reference_sha256"] = final_hash
        row["attack_method"] = str(prepared.get("attack_method", "none"))
        row["attack_reference_sha256"] = str(
            prepared.get("attack_reference_sha256", "")
        )
        row["manipulation_method"] = str(
            prepared.get("manipulation_method", "none")
        )
        selected = selected_by_id[case_id]
        selected["capture_number"] = number
        selected["prepared_reference_sha256"] = final_hash
        selected["default_attack_method"] = row["attack_method"]
        selected["default_attack_reference_sha256"] = row[
            "attack_reference_sha256"
        ]
        selected["default_manipulation_method"] = row["manipulation_method"]
        if position % 10 == 0 or position == len(index["rows"]):
            print(f"prepared {position}/{len(index['rows'])}", flush=True)

    selection_path.write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    _write_index_csv(pack / "capture_index.csv", index["rows"])
    _write_slideshow(pack, index["rows"])
    scope_name = str(index.get("scope_name", "50x3"))
    selected_count = int(index.get("selected_cases", len(index["rows"])))
    numbered_count = len(index["rows"])
    completed_count = int(index.get("completed_pairs_already_counted", 0))
    gallery_numbers = [
        str(row["number"])
        for row in index["rows"]
        if row["gallery_required_for_test"] is True
    ]
    (pack / "README_FIRST.md").write_text(
        "# QRGuard 50 x 3 camera-first pack\n\n"
        f"Scope: `{scope_name}`. Target: 50 Clean + 50 Adversarial + 50 "
        f"Tampered ({selected_count} selected). This pack contains "
        f"{numbered_count} remaining Camera scans; {completed_count} completed "
        "pairs are already counted.\n\n"
        "1. Open `OPEN_REFERENCE_SLIDESHOW.html` and start at number 1.\n"
        "2. Confirm the same number and case ID in QRGuard Capture.\n"
        "3. Display the numbered PNG full-screen and save its Live Camera crop.\n"
        f"4. Add Gallery only for the {len(gallery_numbers)} cases where "
        "`gallery_required_for_test` is `True`; select the original numbered "
        "PNG, never a screenshot.\n"
        "5. Export the QRGuard offline ZIP every 40 Camera sessions or sooner.\n"
        "6. Prepared adversarial/tampered provenance is bundled in the scoped "
        "APK plan; do not replace it with an ordinary clean QR.\n\n"
        "Files in `scan_with_live_cam` are optional review screenshots only. The "
        "QRGuard Capture ZIP is the canonical training evidence.\n",
        encoding="utf-8",
    )
    (pack / "GALLERY_TEST_NUMBERS.txt").write_text(
        f"Gallery is required only for these {len(gallery_numbers)} test cases:\n"
        + ", ".join(gallery_numbers)
        + "\n\nUse the original same-numbered PNG, never a screenshot.\n",
        encoding="utf-8",
    )

    temporary = archive.with_suffix(archive.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(pack.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(pack).as_posix())
    temporary.replace(archive)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pack",
        type=Path,
        default=ROOT / "data" / "numbered_capture_pack" / PACK_NAME,
    )
    parser.add_argument(
        "--selection",
        type=Path,
        default=(
            ROOT
            / "ml_training"
            / "structural"
            / "campaigns"
            / CAMPAIGN_ID
            / "scope_50x3_selection.json"
        ),
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=ROOT / "data" / "numbered_capture_pack" / f"{PACK_NAME}.zip",
    )
    parser.add_argument(
        "--victim-checkpoint",
        type=Path,
        default=(
            Path.home()
            / ".cache"
            / "torch"
            / "hub"
            / "checkpoints"
            / "resnet18-f37072fd.pth"
        ),
    )
    args = parser.parse_args()
    prepare(args.pack, args.selection, args.archive, args.victim_checkpoint)
    print(f"capture-ready pack and archive prepared: {args.archive}")


if __name__ == "__main__":
    main()
