"""Prepare the real-photo QR-surface dataset as clean Structural auxiliaries.

The source contains 92 photographs but only one unique QR payload/bitmap.  All
photos therefore stay in one auxiliary-training group; they must never be
split across train/test and are not accepted as exact QRGuard app crops.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
RAW_CANDIDATES = (
    ROOT / "ml_training/datasets/structural/raw/qr_surfaces",
    ROOT / "ml_training/structural/raw/qr_surfaces",
)
RAW = next((path for path in RAW_CANDIDATES if path.exists()), RAW_CANDIDATES[0])
OUTPUT = ROOT / "ml_training/datasets/structural/processed/qr_surfaces"
MANIFEST = OUTPUT / "manifest.csv"
AUDIT = OUTPUT / "preparation_audit.json"
BRANCHES = ("flat", "random")
DETECTION_MAX_SIDE = 1280
QUIET_ZONE = 0.15
MIN_SIDE = 24


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _order_points(points: np.ndarray) -> np.ndarray:
    """Return corners as top-left, top-right, bottom-right, bottom-left."""
    points = np.asarray(points, dtype=np.float32).reshape(4, 2)
    ordered = np.zeros((4, 2), dtype=np.float32)
    coordinate_sum = points.sum(axis=1)
    coordinate_difference = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(coordinate_sum)]
    ordered[2] = points[np.argmax(coordinate_sum)]
    ordered[1] = points[np.argmin(coordinate_difference)]
    ordered[3] = points[np.argmax(coordinate_difference)]
    return ordered


def _correct_global_camera_cast(rgb: np.ndarray) -> np.ndarray:
    """Match the bright-pixel colour correction in app/qr_cropper.dart."""
    pixels = rgb.astype(np.float32)
    luminance = (
        0.299 * pixels[:, :, 0]
        + 0.587 * pixels[:, :, 1]
        + 0.114 * pixels[:, :, 2]
    )
    bright = luminance >= 160
    if int(bright.sum()) < max(16, rgb.shape[0] * rgb.shape[1] // 20):
        return rgb
    means = pixels[bright].mean(axis=0)
    if np.any(means < 1):
        return rgb
    neutral = float(means.mean())
    gains = np.clip(neutral / means, 0.70, 1.45)
    return np.clip(np.rint(pixels * gains), 0, 255).astype(np.uint8)


def _detect_and_rectify(image_bgr: np.ndarray) -> tuple[np.ndarray | None, dict]:
    height, width = image_bgr.shape[:2]
    scale = min(1.0, DETECTION_MAX_SIDE / max(width, height))
    detected_image = (
        cv2.resize(
            image_bgr,
            (round(width * scale), round(height * scale)),
            interpolation=cv2.INTER_AREA,
        )
        if scale < 1
        else image_bgr
    )
    detector = cv2.QRCodeDetector()
    found, corners = detector.detect(detected_image)
    if not found or corners is None:
        return None, {"reason": "qr_detector_failed"}
    ordered = _order_points(corners / scale)
    edges = np.asarray(
        [
            np.linalg.norm(ordered[0] - ordered[1]),
            np.linalg.norm(ordered[1] - ordered[2]),
            np.linalg.norm(ordered[2] - ordered[3]),
            np.linalg.norm(ordered[3] - ordered[0]),
        ]
    )
    if float(edges.min()) < MIN_SIDE or float(edges.max() / edges.min()) > 3.5:
        return None, {"reason": "untrustworthy_geometry", "edges": edges.tolist()}
    centre = ordered.mean(axis=0)
    expansion = 1 + 2 * QUIET_ZONE
    expanded = centre + (ordered - centre) * expansion
    expanded[:, 0] = np.clip(expanded[:, 0], 0, width - 1)
    expanded[:, 1] = np.clip(expanded[:, 1], 0, height - 1)
    output_side = int(round(float(edges.mean()) * expansion))
    output_side = min(output_side, width, height)
    if output_side < MIN_SIDE:
        return None, {"reason": "crop_too_small"}
    destination = np.asarray(
        [
            [0, 0],
            [output_side - 1, 0],
            [output_side - 1, output_side - 1],
            [0, output_side - 1],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(expanded, destination)
    rectified_bgr = cv2.warpPerspective(
        image_bgr,
        transform,
        (output_side, output_side),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    rectified_rgb = _correct_global_camera_cast(
        cv2.cvtColor(rectified_bgr, cv2.COLOR_BGR2RGB)
    )
    return rectified_rgb, {
        "reason": "ok",
        "detector_scale": scale,
        "corners": ordered.round(3).tolist(),
        "expanded_corners": expanded.round(3).tolist(),
        "output_side": output_side,
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    rejected: list[dict] = []
    bitmap_hashes: set[str] = set()
    for branch in BRANCHES:
        bitmap = RAW / branch / "bitmaps/1.png"
        bitmap_sha = _sha256(bitmap)
        bitmap_hashes.add(bitmap_sha)
        annotations = RAW / branch / "annotations"
        destination_dir = OUTPUT / "clean" / branch
        destination_dir.mkdir(parents=True, exist_ok=True)
        for image_path in sorted((RAW / branch / "images").iterdir()):
            if not image_path.is_file():
                continue
            annotation_path = annotations / f"{image_path.stem}.json"
            annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                rejected.append({"source_path": image_path.as_posix(), "reason": "decode_failed"})
                continue
            crop, details = _detect_and_rectify(image)
            if crop is None:
                rejected.append({"source_path": image_path.as_posix(), **details})
                continue
            output_path = destination_dir / f"{image_path.stem}.png"
            encoded = cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)
            if not cv2.imwrite(str(output_path), encoded, [cv2.IMWRITE_PNG_COMPRESSION, 6]):
                raise OSError(f"failed to write {output_path}")
            rows.append(
                {
                    "path": output_path.relative_to(ROOT).as_posix(),
                    "label": "clean",
                    "class_id": 0,
                    "split": "auxiliary_train_only",
                    "group_id": f"qr_surfaces:{bitmap_sha}",
                    "payload_id": annotation["id_original"],
                    "source": "qr_codes_in_surfaces",
                    "capture_kind": "external_real_camera",
                    "surface_branch": branch,
                    "deformation": annotation.get("deformation", "unknown"),
                    "is_exact_app_crop": False,
                    "licence": "CC-BY-4.0",
                    "source_path": image_path.relative_to(ROOT).as_posix(),
                    "source_sha256": _sha256(image_path),
                    "crop_sha256": _sha256(output_path),
                    "crop_width": crop.shape[1],
                    "crop_height": crop.shape[0],
                    "detector_scale": details["detector_scale"],
                }
            )
    fields = list(rows[0]) if rows else ["path"]
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    audit = {
        "source": "https://data.mendeley.com/datasets/m6mfwc52vk/1",
        "licence": "CC-BY-4.0",
        "input_photos": sum(1 for branch in BRANCHES for _ in (RAW / branch / "images").iterdir()),
        "accepted_crops": len(rows),
        "rejected_crops": len(rejected),
        "rejection_reasons": dict(Counter(item["reason"] for item in rejected)),
        "unique_qr_bitmaps": len(bitmap_hashes),
        "leakage_control": (
            "All photographs share one QR bitmap SHA and remain auxiliary_train_only; "
            "none may be used as an independent test observation."
        ),
        "app_crop_parity": (
            "15% quiet-zone expansion, perspective rectification, linear interpolation, "
            "and bright-pixel camera colour correction are mirrored; OpenCV detection "
            "replaces mobile_scanner corner detection, so is_exact_app_crop remains false."
        ),
        "rejected": rejected,
    }
    AUDIT.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in audit.items() if key != "rejected"}, indent=2))


if __name__ == "__main__":
    main()
