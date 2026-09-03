"""Audit and split QRGuard's opt-in live-camera crops for Structural Training.

The backend writes one directory per scan when ``QRGUARD_DUMP_SCANS`` is set::

    runtime_captures/<label>/capture_<case>_<source>_<id>/metadata.json
    runtime_captures/<label>/capture_<case>_<source>_<id>/crop_00.png ... crop_04.png

This script validates those exact post-crop PNGs and builds a privacy-safe CSV.
The split unit is ``payload_sha256``, never a frame: every angle of a QR and every
physical variant carrying the same payload stays in one split. No raw payload is
read, reconstructed, or written.

Typical workflow::

    python -m ml_training.structural.src.prepare_runtime_captures data/runtime_captures
    python -m ml_training.structural.src.prepare_runtime_captures data/runtime_captures --strict

``--strict`` is the pre-training gate. It intentionally fails while the data set
is empty or too small; synthetic camera effects are useful augmentation but are
not evidence that a model works on the live app distribution.
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
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SPLIT_BOUNDS = (("train", 0.70), ("val", 0.85), ("test", 1.0))


@dataclass(frozen=True)
class CaptureRow:
    crop_path: str
    crop_sha256: str
    session_id: str
    group_id: str
    label_name: str
    label: int
    split: str
    frame_index: int
    width: int
    height: int
    image_source: str
    device_model: str


@dataclass
class CaptureAudit:
    accepted_sessions: int
    accepted_frames: int
    rejected_sessions: int
    rejected_reasons: dict[str, int]
    sessions_per_class: dict[str, int]
    frames_per_split_class: dict[str, dict[str, int]]
    sessions_per_split_class: dict[str, dict[str, int]]
    groups_per_split_class: dict[str, dict[str, int]]
    groups_per_split: dict[str, int]
    leakage_groups: list[str]
    strict_ready: bool
    strict_failures: list[str]


def _split_for_group(group_id: str, seed: int) -> str:
    digest = hashlib.sha256(f"qrguard:{seed}:{group_id}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    for split, upper in SPLIT_BOUNDS:
        if fraction < upper:
            return split
    raise AssertionError("unreachable split fraction")


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
    """Return validated frame rows and rejected-session reason counts."""
    root = capture_root.resolve()
    rows: list[CaptureRow] = []
    rejected: Counter = Counter()

    for metadata_path in sorted(root.glob("*/*/metadata.json")):
        session = metadata_path.parent
        folder_label = session.parent.name.lower()
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rejected["invalid_metadata"] += 1
            continue

        label = metadata.get("ground_truth")
        payload_hash = str(metadata.get("payload_sha256", "")).lower()
        source = str(metadata.get("image_source", "")).lower()
        device_model = str(metadata.get("device_model", "not_recorded")).strip()
        if not device_model or len(device_model) > 80:
            device_model = "not_recorded"
        if label not in LABELS or label != folder_label:
            rejected["missing_or_mismatched_label"] += 1
            continue
        if not SHA256_PATTERN.fullmatch(payload_hash):
            rejected["invalid_payload_hash"] += 1
            continue
        if source != "camera":
            rejected["not_live_camera"] += 1
            continue

        crops = sorted(session.glob("crop_*.png"))
        if not 3 <= len(crops) <= 5:
            rejected["requires_3_to_5_frames"] += 1
            continue
        validated = [_valid_crop(path) for path in crops]
        if any(size is None for size in validated):
            rejected["invalid_crop"] += 1
            continue
        crop_hashes = [size[2] for size in validated if size is not None]
        if len(set(crop_hashes)) != len(crop_hashes):
            rejected["duplicate_frames"] += 1
            continue

        split = _split_for_group(payload_hash, seed)
        session_id = session.relative_to(root).as_posix()
        for frame_index, (path, size) in enumerate(zip(crops, validated, strict=True)):
            assert size is not None
            rows.append(
                CaptureRow(
                    crop_path=path.relative_to(root).as_posix(),
                    crop_sha256=crop_hashes[frame_index],
                    session_id=session_id,
                    group_id=payload_hash,
                    label_name=label,
                    label=LABELS[label],
                    split=split,
                    frame_index=frame_index,
                    width=size[0],
                    height=size[1],
                    image_source=source,
                    device_model=device_model,
                )
            )
    return rows, rejected


def audit_rows(
    rows: list[CaptureRow],
    rejected: Counter,
    min_sessions_per_class: int = 100,
    min_test_groups_per_class: int = 20,
) -> CaptureAudit:
    sessions: dict[str, CaptureRow] = {}
    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        sessions.setdefault(row.session_id, row)
        group_splits[row.group_id].add(row.split)

    session_class = Counter(row.label_name for row in sessions.values())
    frame_split_class: dict[str, Counter] = defaultdict(Counter)
    session_split_class: dict[str, Counter] = defaultdict(Counter)
    group_split_class: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        frame_split_class[row.split][row.label_name] += 1
    for row in sessions.values():
        session_split_class[row.split][row.label_name] += 1
    for group_id, label_name, split in {
        (row.group_id, row.label_name, row.split) for row in rows
    }:
        group_split_class[split][label_name] += 1

    leakage = sorted(group for group, splits in group_splits.items() if len(splits) > 1)
    failures = []
    for label in LABELS:
        count = session_class[label]
        if count < min_sessions_per_class:
            failures.append(
                f"{label}: {count} sessions; require {min_sessions_per_class}"
            )
        test_count = group_split_class["test"][label]
        if test_count < min_test_groups_per_class:
            failures.append(
                f"{label} test: {test_count} payload groups; require "
                f"{min_test_groups_per_class}"
            )
    if leakage:
        failures.append(f"{len(leakage)} payload groups leaked across splits")

    def _complete(counts: dict[str, Counter]) -> dict[str, dict[str, int]]:
        return {
            split: {label: counts[split][label] for label in LABELS}
            for split, _ in SPLIT_BOUNDS
        }

    return CaptureAudit(
        accepted_sessions=len(sessions),
        accepted_frames=len(rows),
        rejected_sessions=sum(rejected.values()),
        rejected_reasons=dict(sorted(rejected.items())),
        sessions_per_class={label: session_class[label] for label in LABELS},
        frames_per_split_class=_complete(frame_split_class),
        sessions_per_split_class=_complete(session_split_class),
        groups_per_split_class=_complete(group_split_class),
        groups_per_split={
            split: len({row.group_id for row in rows if row.split == split})
            for split, _ in SPLIT_BOUNDS
        },
        leakage_groups=leakage,
        strict_ready=not failures,
        strict_failures=failures,
    )


def write_outputs(root: Path, rows: list[CaptureRow], audit: CaptureAudit) -> None:
    manifest_path = root / "manifest.csv"
    audit_path = root / "audit.json"
    root.mkdir(parents=True, exist_ok=True)
    fields = list(CaptureRow.__dataclass_fields__)
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    audit_path.write_text(json.dumps(asdict(audit), indent=2), encoding="utf-8")
    print(f"wrote {manifest_path}")
    print(f"wrote {audit_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-sessions-per-class", type=int, default=100)
    parser.add_argument("--min-test-groups-per-class", type=int, default=20)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero unless the real-camera pre-training gate is satisfied",
    )
    args = parser.parse_args()

    rows, rejected = discover(args.capture_root, args.seed)
    audit = audit_rows(
        rows,
        rejected,
        args.min_sessions_per_class,
        args.min_test_groups_per_class,
    )
    write_outputs(args.capture_root, rows, audit)
    print(json.dumps(asdict(audit), indent=2))
    if args.strict and not audit.strict_ready:
        raise SystemExit(
            "runtime capture gate failed: " + "; ".join(audit.strict_failures)
        )


if __name__ == "__main__":
    main()
