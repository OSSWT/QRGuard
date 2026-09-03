"""Import the locked M5 diagnostic archive as development-only Structural data.

The archive is fully validated before any output is written. Temporal frames
stay grouped by the pristine base identity, so clean/adversarial/tampered
variants and all five frames can never leak across train and validation. The
existing deployment test holdout is copied unchanged into the candidate
manifest and the M5 rows are never marked as holdout evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_live_camera_diagnostic import ValidatedFrame, validate_archive

CAMPAIGN_ID = "structural-coverage-development-2026-09-r01"
CANDIDATE_VERSION = "structural-2026.09-r01"
DEFAULT_PLAN = ROOT / "app/assets/capture/structural_coverage_development_plan.json"
DEFAULT_PACK_MANIFEST = (
    ROOT / "dist/Structural_Coverage_Development_2026-09-r01/MANIFEST.json"
)
DEFAULT_BASE_MANIFEST = (
    ROOT
    / "ml_training/datasets/structural/processed/structural-2026.03-r01/manifest.csv"
)
DEFAULT_DATA_ROOT = ROOT / "data/structural_coverage_development/2026-09-r01"
DEFAULT_CANDIDATE_MANIFEST = (
    ROOT
    / "ml_training/datasets/structural/processed"
    / CANDIDATE_VERSION
    / "manifest.csv"
)
CLASS_IDS = {"clean": 0, "adversarial": 1, "tampered": 2}


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def _case_contracts(
    plan_path: Path, pack_manifest_path: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    plan = _read_json(plan_path)
    pack = _read_json(pack_manifest_path)
    if plan.get("campaign_id") != CAMPAIGN_ID or pack.get("pack_id") != CAMPAIGN_ID:
        raise ValueError("M5 campaign identity mismatch")
    plan_cases = {str(row["case_id"]): row for row in plan.get("cases", [])}
    pack_cases = {str(row["case_id"]): row for row in pack.get("cases", [])}
    if len(plan_cases) != 48 or set(plan_cases) != set(pack_cases):
        raise ValueError("plan and pack must contain the same 48 unique cases")
    for case_id, plan_case in plan_cases.items():
        pack_case = pack_cases[case_id]
        metadata = dict(plan_case.get("metadata", {}))
        expected = {
            "ground_truth": pack_case["label"],
            "expected_payload_sha256": pack_case["payload_sha256"],
        }
        for key, value in expected.items():
            if plan_case.get(key) != value:
                raise ValueError(f"{case_id}: plan/pack {key} mismatch")
        for key in (
            "base_identity",
            "development_split",
            "deployment_holdout_eligible",
            "qr_version",
            "module_count",
            "mask_pattern",
            "version_band",
            "payload_length_bin",
            "payload_utf8_bytes",
            "qr_matrix_sha256",
        ):
            pack_key = "base_id" if key == "base_identity" else key
            if metadata.get(key) != pack_case.get(pack_key):
                raise ValueError(f"{case_id}: plan/pack metadata {key} mismatch")
        if metadata["development_split"] not in {"train", "validation"}:
            raise ValueError(f"{case_id}: invalid development split")
        if metadata["deployment_holdout_eligible"] is not False:
            raise ValueError(f"{case_id}: M5 data cannot be holdout eligible")
    return plan_cases, pack_cases


def _attack_recipe(label: str, pack_case: dict[str, Any]) -> str:
    if label == "adversarial":
        return str(pack_case["attack_method"])
    if label == "tampered":
        return str(pack_case["manipulation_method"])
    return "none"


def development_row(
    frame: ValidatedFrame,
    plan_case: dict[str, Any],
    pack_case: dict[str, Any],
    relative_path: str,
) -> dict[str, Any]:
    metadata = dict(plan_case["metadata"])
    label = frame.ground_truth
    base_id = str(metadata["base_identity"])
    return {
        "path": relative_path,
        "label": label,
        "class_id": CLASS_IDS[label],
        "split": metadata["development_split"],
        "group_id": f"coverage_dev_2026_09:{base_id}",
        "source": "qrguard_coverage_2026_09_camera",
        "capture_kind": "exact_app_screen_capture",
        "quality_condition": "screen_moire_or_compression",
        "quality_severity": "none",
        "attack_recipe": _attack_recipe(label, pack_case),
        "is_exact_app_crop": True,
        "licence": "project_internal_opt_in",
        "session_id": frame.session_id,
        "device_model": "android_test_device_unrecorded",
        "image_source": "camera",
        "paired_group": f"coverage_dev_2026_09:{frame.case_id}",
        "physical_qr": f"coverage_dev_2026_09:{base_id}",
        "payload_hash": frame.payload_sha256,
        "case_id": frame.case_id,
        "frame_index": frame.frame_index,
        "crop_sha256": frame.crop_sha256,
        "qr_version": metadata["qr_version"],
        "module_count": metadata["module_count"],
        "mask_pattern": metadata["mask_pattern"],
        "version_band": metadata["version_band"],
        "payload_length_bin": metadata["payload_length_bin"],
        "payload_utf8_bytes": metadata["payload_utf8_bytes"],
        "qr_matrix_sha256": metadata["qr_matrix_sha256"],
        "development_campaign": CAMPAIGN_ID,
        "deployment_holdout_eligible": False,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _validate_development_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 240:
        raise ValueError(f"expected 240 M5 frames, got {len(rows)}")
    counts = Counter((row["split"], row["label"]) for row in rows)
    expected_counts = {("train", label): 60 for label in CLASS_IDS} | {
        ("validation", label): 20 for label in CLASS_IDS
    }
    if counts != expected_counts:
        raise ValueError(f"M5 split/class imbalance: {counts}")
    case_counts = Counter(row["case_id"] for row in rows)
    if len(case_counts) != 48 or set(case_counts.values()) != {5}:
        raise ValueError("every M5 case must contribute exactly five frames")
    group_splits: dict[str, set[str]] = defaultdict(set)
    group_labels: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group_splits[str(row["group_id"])].add(str(row["split"]))
        group_labels[str(row["group_id"])].add(str(row["label"]))
    if len(group_splits) != 16 or any(
        len(splits) != 1 for splits in group_splits.values()
    ):
        raise ValueError("base identities leak across development splits")
    if any(labels != set(CLASS_IDS) for labels in group_labels.values()):
        raise ValueError("each base identity must contain all three labels")
    for label in CLASS_IDS:
        label_rows = [row for row in rows if row["label"] == label]
        masks = Counter(int(row["mask_pattern"]) for row in label_rows)
        if masks != {mask: 10 for mask in range(8)}:
            raise ValueError(f"{label}: physical frame mask imbalance: {masks}")


def import_capture(
    *,
    archive_path: Path,
    plan_path: Path,
    pack_manifest_path: Path,
    base_manifest_path: Path,
    data_root: Path,
    candidate_manifest_path: Path,
) -> dict[str, Any]:
    if data_root.exists() and any(data_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty data root: {data_root}")
    if candidate_manifest_path.exists():
        raise FileExistsError(
            f"refusing to overwrite candidate manifest: {candidate_manifest_path}"
        )
    plan_cases, pack_cases = _case_contracts(plan_path, pack_manifest_path)
    frames = validate_archive(archive_path, plan_path)
    if len({frame.crop_sha256 for frame in frames}) != len(frames):
        raise ValueError("M5 archive contains duplicate crop pixels")

    development_rows: list[dict[str, Any]] = []
    destinations: list[tuple[Path, bytes]] = []
    for frame in frames:
        plan_case = plan_cases[frame.case_id]
        pack_case = pack_cases[frame.case_id]
        split = str(plan_case["metadata"]["development_split"])
        relative_from_data = (
            Path("images")
            / split
            / frame.ground_truth
            / frame.case_id
            / f"crop_{frame.frame_index:02d}.png"
        )
        destination = data_root / relative_from_data
        relative_from_root = destination.relative_to(ROOT).as_posix()
        development_rows.append(
            development_row(frame, plan_case, pack_case, relative_from_root)
        )
        destinations.append((destination, frame.crop_png))
    _validate_development_rows(development_rows)

    with base_manifest_path.open(encoding="utf-8", newline="") as handle:
        base_rows = list(csv.DictReader(handle))
    base_groups: dict[str, set[str]] = defaultdict(set)
    for row in base_rows:
        base_groups[str(row["group_id"])].add(str(row["split"]))
        source_path = ROOT / str(row["path"])
        if not source_path.is_file():
            raise FileNotFoundError(f"base manifest image missing: {source_path}")
    if any(len(splits) != 1 for splits in base_groups.values()):
        raise ValueError("base manifest already contains group leakage")
    new_groups = {str(row["group_id"]) for row in development_rows}
    overlap = new_groups & set(base_groups)
    if overlap:
        raise ValueError(f"M5 groups collide with base groups: {sorted(overlap)[:3]}")

    data_root.mkdir(parents=True, exist_ok=True)
    for destination, raw in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    _write_csv(data_root / "manifest.csv", development_rows)

    candidate_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    combined_rows = [*base_rows, *development_rows]
    _write_csv(candidate_manifest_path, combined_rows)
    audit = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "candidate_version": CANDIDATE_VERSION,
        "deployment_holdout_eligible": False,
        "source_archive": {
            "filename": archive_path.name,
            "sha256": _sha256(archive_path),
        },
        "plan_sha256": _sha256(plan_path),
        "pack_manifest_sha256": _sha256(pack_manifest_path),
        "base_manifest": {
            "path": base_manifest_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(base_manifest_path),
            "rows": len(base_rows),
        },
        "development_manifest": {
            "path": (data_root / "manifest.csv").relative_to(ROOT).as_posix(),
            "sha256": _sha256(data_root / "manifest.csv"),
            "rows": len(development_rows),
            "unique_crops": len({row["crop_sha256"] for row in development_rows}),
            "unique_base_identities": len(new_groups),
            "counts": dict(Counter(row["label"] for row in development_rows)),
            "splits": dict(Counter(row["split"] for row in development_rows)),
        },
        "candidate_manifest": {
            "path": candidate_manifest_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(candidate_manifest_path),
            "rows": len(combined_rows),
        },
        "existing_runtime_holdout_rows_unchanged": sum(
            row.get("split") == "runtime_holdout_test" for row in base_rows
        ),
        "raw_payload_stored": False,
    }
    (data_root / "IMPORT_AUDIT.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--pack-manifest", type=Path, default=DEFAULT_PACK_MANIFEST)
    parser.add_argument("--base-manifest", type=Path, default=DEFAULT_BASE_MANIFEST)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument(
        "--candidate-manifest", type=Path, default=DEFAULT_CANDIDATE_MANIFEST
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = import_capture(
        archive_path=args.archive.resolve(strict=True),
        plan_path=args.plan.resolve(strict=True),
        pack_manifest_path=args.pack_manifest.resolve(strict=True),
        base_manifest_path=args.base_manifest.resolve(strict=True),
        data_root=args.data_root.resolve(),
        candidate_manifest_path=args.candidate_manifest.resolve(),
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
