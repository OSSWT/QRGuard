"""Prepare QR-only Dynamsoft samples as a licence-quarantined holdout.

This source is useful for acquisition/cropping robustness, but it has neither a
repository licence nor QRGuard's clean/adversarial/tampered ground truth.  The
output must therefore never be mixed into model training or class metrics.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ml_training.structural.src.prepare_qr_surfaces import (  # noqa: E402
    MIN_SIDE,
    QUIET_ZONE,
    _correct_global_camera_cast,
    _detect_and_rectify,
    _order_points,
)


RAW = ROOT / "ml_training/datasets/holdout/raw/dynamsoft"
OUTPUT = ROOT / "ml_training/datasets/holdout/processed/dynamsoft_qr"
MANIFEST = OUTPUT / "manifest.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_qr(format_name: str) -> bool:
    return "".join(character for character in format_name.lower() if character.isalnum()) == "qrcode"


def _rectify_known_points(
    image_bgr: np.ndarray, points: list[list[float]]
) -> np.ndarray | None:
    height, width = image_bgr.shape[:2]
    if len(points) != 4:
        return None
    ordered = _order_points(np.asarray(points, dtype=np.float32))
    edges = np.asarray(
        [np.linalg.norm(ordered[index] - ordered[(index + 1) % 4]) for index in range(4)]
    )
    if float(edges.min()) < MIN_SIDE or float(edges.max() / edges.min()) > 3.5:
        return None
    centre = ordered.mean(axis=0)
    expansion = 1 + 2 * QUIET_ZONE
    expanded = centre + (ordered - centre) * expansion
    expanded[:, 0] = np.clip(expanded[:, 0], 0, width - 1)
    expanded[:, 1] = np.clip(expanded[:, 1], 0, height - 1)
    side = min(int(round(float(edges.mean()) * expansion)), width, height)
    if side < MIN_SIDE:
        return None
    destination = np.asarray(
        [[0, 0], [side - 1, 0], [side - 1, side - 1], [0, side - 1]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(expanded, destination)
    crop = cv2.warpPerspective(
        image_bgr,
        transform,
        (side, side),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return _correct_global_camera_cast(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))


def _write_crop(path: Path, crop_rgb: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(
        str(path),
        cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_PNG_COMPRESSION, 6],
    ):
        raise OSError(f"failed to write {path}")


def _challenging_rows() -> tuple[list[dict], list[dict]]:
    source = RAW / "challenging-images"
    annotation_path = source / "annotations.json"
    annotations = json.loads(annotation_path.read_text(encoding="utf-8"))
    rows, rejected = [], []
    for image_record in annotations["images"]:
        image_path = source / image_record["file"]
        qr_records = [record for record in image_record["barcodes"] if _is_qr(record["format"])]
        if not qr_records:
            continue
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            rejected.append({"source_path": image_path.as_posix(), "reason": "decode_failed"})
            continue
        source_sha = _sha256(image_path)
        for index, record in enumerate(qr_records):
            crop = _rectify_known_points(image, record["points"])
            if crop is None:
                rejected.append(
                    {
                        "source_path": image_path.as_posix(),
                        "barcode_index": index,
                        "reason": "untrustworthy_geometry",
                    }
                )
                continue
            output_path = OUTPUT / "challenging_images" / f"{image_path.stem}_qr_{index:03d}.png"
            _write_crop(output_path, crop)
            rows.append(
                {
                    "path": output_path.relative_to(ROOT).as_posix(),
                    "source_path": image_path.relative_to(ROOT).as_posix(),
                    "source_sha256": source_sha,
                    "crop_sha256": _sha256(output_path),
                    "session_group": f"dynamsoft:image:{source_sha}",
                    "capture_condition": image_path.stem,
                    "payload": record.get("text", ""),
                    "expected_structural_class": "not_assigned",
                    "purpose": "acquisition_robustness_only",
                    "licence_status": "quarantined_no_repository_licence",
                    "training_use": False,
                    "class_metric_use": False,
                    "is_exact_app_crop": False,
                }
            )
    return rows, rejected


def _video_rows() -> tuple[list[dict], list[dict]]:
    source = RAW / "video-based-testing/single-code"
    rows, rejected = [], []
    for video_path in sorted(source.glob("*qrcode*.mp4")):
        capture = cv2.VideoCapture(str(video_path))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = max(float(capture.get(cv2.CAP_PROP_FPS)), 1.0)
        # At most 30 temporally separated samples from each physical capture session.
        step = max(1, frame_count // 30)
        source_sha = _sha256(video_path)
        for frame_index in range(0, frame_count, step):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                rejected.append(
                    {"source_path": video_path.as_posix(), "frame": frame_index, "reason": "decode_failed"}
                )
                continue
            crop, details = _detect_and_rectify(frame)
            if crop is None:
                rejected.append(
                    {
                        "source_path": video_path.as_posix(),
                        "frame": frame_index,
                        "reason": details["reason"],
                    }
                )
                continue
            output_path = OUTPUT / "video" / video_path.stem / f"frame_{frame_index:06d}.png"
            _write_crop(output_path, crop)
            rows.append(
                {
                    "path": output_path.relative_to(ROOT).as_posix(),
                    "source_path": video_path.relative_to(ROOT).as_posix(),
                    "source_sha256": source_sha,
                    "crop_sha256": _sha256(output_path),
                    "session_group": f"dynamsoft:video:{source_sha}",
                    "capture_condition": video_path.stem,
                    "payload": "",
                    "expected_structural_class": "not_assigned",
                    "purpose": "acquisition_robustness_only",
                    "licence_status": "quarantined_no_repository_licence",
                    "training_use": False,
                    "class_metric_use": False,
                    "is_exact_app_crop": False,
                }
            )
        capture.release()
    return rows, rejected


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image_rows, image_rejected = _challenging_rows()
    video_rows, video_rejected = _video_rows()
    rows = image_rows + video_rows
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["path"])
        writer.writeheader()
        writer.writerows(rows)
    audit = {
        "source": "https://github.com/Dynamsoft/datasets-from-dynamsoft",
        "accepted_challenging_qr_crops": len(image_rows),
        "accepted_video_qr_crops": len(video_rows),
        "rejected": image_rejected + video_rejected,
        "licence_status": "quarantined_no_repository_licence",
        "allowed_use": "acquisition robustness inspection only",
        "prohibited_use": ["training", "structural class performance metrics"],
    }
    (OUTPUT / "preparation_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in audit.items() if key != "rejected"}, indent=2))


if __name__ == "__main__":
    main()
