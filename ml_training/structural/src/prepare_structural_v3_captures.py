"""Build the privacy-safe Structural v3 Gallery/Camera capture manifest.

Unlike the historical camera-only collector, v3 accepts one to five crops per
session, records one authoritative crop, and can join Gallery and Camera sessions
through an opaque SHA-256 pair identifier. Raw payloads and human identifiers are
never stored.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

LABELS = {"clean": 0, "adversarial": 1, "tampered": 2}
IMAGE_SOURCES = {"camera", "gallery"}
QUALITY_CONDITIONS = {
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
}
QUALITY_SEVERITIES = {"none", "mild", "moderate", "severe"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SPLIT_BOUNDS = (("train", 0.70), ("validation", 0.85), ("test", 1.0))


@dataclass(frozen=True)
class CaptureRow:
    sample_path: str
    sha256: str
    label: str
    class_id: int
    quality_condition: str
    quality_severity: str
    source_dataset: str
    source_version: str
    capture_session: str
    paired_group: str
    physical_qr: str
    payload_hash: str
    image_source: str
    device: str
    medium: str
    environment: str
    is_real_camera: bool
    is_exact_app_crop: bool
    is_authoritative: bool
    frame_index: int
    width: int
    height: int
    split: str
    parent_sample: str
    licence: str


@dataclass
class CaptureAudit:
    accepted_sessions: int
    accepted_frames: int
    authoritative_frames: int
    rejected_sessions: int
    rejected_reasons: dict[str, int]
    camera_sessions_per_class: dict[str, int]
    gallery_sessions_per_class: dict[str, int]
    camera_test_groups_per_class: dict[str, int]
    paired_groups_per_class: dict[str, int]
    paired_test_groups_per_class: dict[str, int]
    quality_sessions_per_class: dict[str, dict[str, int]]
    leakage_groups: list[str]
    strict_ready: bool
    strict_failures: list[str]


def _split_for_group(group_id: str, seed: int) -> str:
    digest = hashlib.sha256(f"qrguard-v3:{seed}:{group_id}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    for split, upper in SPLIT_BOUNDS:
        if fraction < upper:
            return split
    raise AssertionError("unreachable split fraction")


def _safe_text(value: object, default: str, maximum: int = 80) -> str:
    text = str(value or "").strip()
    return text if text and len(text) <= maximum else default


def _valid_crop(path: Path) -> tuple[int, int, str] | None:
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            if image.format != "PNG" or width < 24 or height < 24 or width != height:
                return None
            rgb = image.convert("RGB")
            digest = hashlib.sha256()
            digest.update(width.to_bytes(4, "big"))
            digest.update(height.to_bytes(4, "big"))
            digest.update(rgb.tobytes())
            return width, height, digest.hexdigest()
    except (OSError, ValueError):
        return None


def discover(capture_root: Path, seed: int = 42) -> tuple[list[CaptureRow], Counter]:
    root = capture_root.resolve()
    rows: list[CaptureRow] = []
    rejected: Counter = Counter()

    for metadata_path in sorted(root.glob("*/scan_*/metadata.json")):
        session = metadata_path.parent
        folder_label = session.parent.name.lower()
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rejected["invalid_metadata"] += 1
            continue

        label = str(metadata.get("ground_truth", "")).lower()
        payload_hash = str(metadata.get("payload_sha256", "")).lower()
        image_source = str(metadata.get("image_source", "")).lower()
        paired_group = str(metadata.get("paired_group_sha256", payload_hash)).lower()
        physical_qr = str(metadata.get("physical_qr_sha256", paired_group)).lower()
        condition = str(metadata.get("quality_condition", "normal")).lower()
        severity = str(metadata.get("quality_severity", "none")).lower()

        if label not in LABELS or label != folder_label:
            rejected["missing_or_mismatched_label"] += 1
            continue
        if not SHA256_PATTERN.fullmatch(payload_hash):
            rejected["invalid_payload_hash"] += 1
            continue
        if not SHA256_PATTERN.fullmatch(paired_group):
            rejected["invalid_paired_group"] += 1
            continue
        if not SHA256_PATTERN.fullmatch(physical_qr):
            rejected["invalid_physical_qr"] += 1
            continue
        if image_source not in IMAGE_SOURCES:
            rejected["invalid_image_source"] += 1
            continue
        if condition not in QUALITY_CONDITIONS:
            rejected["invalid_quality_condition"] += 1
            continue
        if severity not in QUALITY_SEVERITIES:
            rejected["invalid_quality_severity"] += 1
            continue

        crops = sorted(session.glob("crop_*.png"))
        if not 1 <= len(crops) <= 5:
            rejected["requires_1_to_5_frames"] += 1
            continue
        try:
            selected_index = int(metadata.get("selected_frame_index", 0))
        except (TypeError, ValueError):
            rejected["invalid_selected_frame_index"] += 1
            continue
        if not 0 <= selected_index < len(crops):
            rejected["invalid_selected_frame_index"] += 1
            continue

        validated = [_valid_crop(path) for path in crops]
        if any(item is None for item in validated):
            rejected["invalid_crop"] += 1
            continue
        crop_hashes = [item[2] for item in validated if item is not None]
        if len(set(crop_hashes)) != len(crop_hashes):
            rejected["duplicate_frames"] += 1
            continue

        split = _split_for_group(payload_hash, seed)
        session_id = session.relative_to(root).as_posix()
        device = _safe_text(metadata.get("device_model"), "not_recorded")
        medium = _safe_text(metadata.get("medium"), "not_recorded")
        environment = _safe_text(metadata.get("environment"), "not_recorded")
        for index, (path, item) in enumerate(zip(crops, validated, strict=True)):
            assert item is not None
            rows.append(
                CaptureRow(
                    sample_path=path.relative_to(root).as_posix(),
                    sha256=crop_hashes[index],
                    label=label,
                    class_id=LABELS[label],
                    quality_condition=condition,
                    quality_severity=severity,
                    source_dataset="qrguard_runtime_v3",
                    source_version="structural-2026.03-r01",
                    capture_session=session_id,
                    paired_group=paired_group,
                    physical_qr=physical_qr,
                    payload_hash=payload_hash,
                    image_source=image_source,
                    device=device,
                    medium=medium,
                    environment=environment,
                    is_real_camera=image_source == "camera",
                    is_exact_app_crop=True,
                    is_authoritative=index == selected_index,
                    frame_index=index,
                    width=item[0],
                    height=item[1],
                    split=split,
                    parent_sample=session_id,
                    licence="project_internal_opt_in",
                )
            )
    return rows, rejected


def audit_rows(
    rows: list[CaptureRow],
    rejected: Counter,
    min_camera_sessions_per_class: int = 100,
    min_camera_test_groups_per_class: int = 20,
    min_paired_test_groups_per_class: int = 20,
    min_quality_sessions_per_condition: int = 0,
) -> CaptureAudit:
    authoritative = [row for row in rows if row.is_authoritative]
    sessions = {row.capture_session: row for row in authoritative}
    camera = [row for row in sessions.values() if row.image_source == "camera"]
    gallery = [row for row in sessions.values() if row.image_source == "gallery"]

    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in authoritative:
        group_splits[row.payload_hash].add(row.split)
    leakage = sorted(group for group, splits in group_splits.items() if len(splits) > 1)

    camera_counts = Counter(row.label for row in camera)
    gallery_counts = Counter(row.label for row in gallery)
    camera_test = Counter(
        (row.label, row.payload_hash) for row in camera if row.split == "test"
    )
    camera_test_by_class = Counter(label for label, _ in camera_test)

    pair_sources: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    pair_source_counts = Counter(
        (row.paired_group, row.image_source) for row in authoritative
    )
    pair_context: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in authoritative:
        pair_sources[(row.paired_group, row.label, row.split)].add(row.image_source)
        pair_context[row.paired_group].add((row.label, row.split))
    paired = [key for key, sources in pair_sources.items() if sources == IMAGE_SOURCES]
    paired_counts = Counter(label for _, label, _ in paired)
    paired_test_counts = Counter(label for _, label, split in paired if split == "test")

    quality_counts: dict[str, Counter] = defaultdict(Counter)
    for row in camera:
        quality_counts[row.label][row.quality_condition] += 1

    failures: list[str] = []
    for label in LABELS:
        if camera_counts[label] < min_camera_sessions_per_class:
            failures.append(
                f"{label}: {camera_counts[label]} camera sessions; require "
                f"{min_camera_sessions_per_class}"
            )
        if camera_test_by_class[label] < min_camera_test_groups_per_class:
            failures.append(
                f"{label}: {camera_test_by_class[label]} camera test groups; require "
                f"{min_camera_test_groups_per_class}"
            )
        if paired_test_counts[label] < min_paired_test_groups_per_class:
            failures.append(
                f"{label}: {paired_test_counts[label]} paired test groups; require "
                f"{min_paired_test_groups_per_class}"
            )
        if min_quality_sessions_per_condition:
            for condition in sorted(QUALITY_CONDITIONS):
                count = quality_counts[label][condition]
                if count < min_quality_sessions_per_condition:
                    failures.append(
                        f"{label}/{condition}: {count} camera sessions; require "
                        f"{min_quality_sessions_per_condition}"
                    )
    if leakage:
        failures.append(f"{len(leakage)} payload groups leaked across splits")
    duplicate_pair_sources = [
        key for key, count in pair_source_counts.items() if count > 1
    ]
    if duplicate_pair_sources:
        failures.append(
            f"{len(duplicate_pair_sources)} paired groups contain multiple "
            "authoritative rows for one image source"
        )
    inconsistent_pairs = [
        group for group, contexts in pair_context.items() if len(contexts) > 1
    ]
    if inconsistent_pairs:
        failures.append(
            f"{len(inconsistent_pairs)} paired groups disagree on label or split"
        )

    return CaptureAudit(
        accepted_sessions=len(sessions),
        accepted_frames=len(rows),
        authoritative_frames=len(authoritative),
        rejected_sessions=sum(rejected.values()),
        rejected_reasons=dict(sorted(rejected.items())),
        camera_sessions_per_class={label: camera_counts[label] for label in LABELS},
        gallery_sessions_per_class={label: gallery_counts[label] for label in LABELS},
        camera_test_groups_per_class={
            label: camera_test_by_class[label] for label in LABELS
        },
        paired_groups_per_class={label: paired_counts[label] for label in LABELS},
        paired_test_groups_per_class={
            label: paired_test_counts[label] for label in LABELS
        },
        quality_sessions_per_class={
            label: {
                condition: quality_counts[label][condition]
                for condition in sorted(QUALITY_CONDITIONS)
            }
            for label in LABELS
        },
        leakage_groups=leakage,
        strict_ready=not failures,
        strict_failures=failures,
    )


def write_outputs(root: Path, rows: list[CaptureRow], audit: CaptureAudit) -> None:
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest_v3.csv"
    fields = list(CaptureRow.__dataclass_fields__)
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    (root / "audit_v3.json").write_text(
        json.dumps(asdict(audit), indent=2), encoding="utf-8"
    )
    print(f"wrote {manifest}")
    print(f"wrote {root / 'audit_v3.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-camera-sessions-per-class", type=int, default=100)
    parser.add_argument("--min-camera-test-groups-per-class", type=int, default=20)
    parser.add_argument("--min-paired-test-groups-per-class", type=int, default=20)
    parser.add_argument("--min-quality-sessions-per-condition", type=int, default=5)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    rows, rejected = discover(args.capture_root, args.seed)
    audit = audit_rows(
        rows,
        rejected,
        args.min_camera_sessions_per_class,
        args.min_camera_test_groups_per_class,
        args.min_paired_test_groups_per_class,
        args.min_quality_sessions_per_condition,
    )
    write_outputs(args.capture_root, rows, audit)
    print(json.dumps(asdict(audit), indent=2))
    if args.strict and not audit.strict_ready:
        raise SystemExit("v3 capture gate failed: " + "; ".join(audit.strict_failures))


if __name__ == "__main__":
    main()
