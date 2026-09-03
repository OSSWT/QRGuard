"""Import clean crops from the consumed M8 blind archive as development data.

The M8 archive was unblinded while diagnosing r04-r06, so it can never be used
as promotion evidence again.  This importer validates the original archive,
admits only clean screen-camera crops, assigns an explicit group-disjoint
development split, and permanently marks every row as consumed/non-holdout.
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

CAMPAIGN_ID = "structural-coverage-blind-holdout-2026-09-r01"
EVIDENCE_ROLE = "consumed_development_replay"
SOURCE_ARCHIVE_SHA256 = (
    "d5930ffcaf1edc0702afd5ff2b2241584a95edd9f9f0de81fdc8a5a5a7921f6d"
)
DEFAULT_ARCHIVE = (
    Path.home()
    / "Downloads/Telegram Desktop/"
    "QRGuard_Diagnostic_structural_coverage_blind_holdout_2026_09_r01.zip"
)
DEFAULT_PLAN = ROOT / "app/assets/capture/structural_coverage_blind_holdout_plan.json"
DEFAULT_PACK_MANIFEST = (
    ROOT / "dist/Structural_Coverage_Blind_Holdout_2026-09-r01/MANIFEST.json"
)
DEFAULT_DATA_ROOT = (
    ROOT / "data/structural_consumed_blind_development/2026-09-r01"
)

# Fixed before r07 training.  The split covers every Version band and holds out
# two of the six V12 identities, while keeping all temporal frames from one QR
# identity on exactly one side of the split.
VALIDATION_BASE_IDENTITIES = {
    "BLIND-BASE-05",  # V3
    "BLIND-BASE-10",  # V6
    "BLIND-BASE-14",  # V12
    "BLIND-BASE-16",  # V12
}


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
        raise ValueError("consumed M8 campaign identity mismatch")
    plan_cases = {str(row["case_id"]): row for row in plan.get("cases", [])}
    pack_cases = {str(row["case_id"]): row for row in pack.get("cases", [])}
    if len(plan_cases) != 48 or set(plan_cases) != set(pack_cases):
        raise ValueError("plan and pack must contain the same 48 unique cases")
    for case_id, plan_case in plan_cases.items():
        pack_case = pack_cases[case_id]
        metadata = dict(plan_case.get("metadata", {}))
        if plan_case.get("ground_truth") != pack_case.get("label"):
            raise ValueError(f"{case_id}: plan/pack label mismatch")
        if plan_case.get("expected_payload_sha256") != pack_case.get(
            "payload_sha256"
        ):
            raise ValueError(f"{case_id}: plan/pack payload mismatch")
        for plan_key, pack_key in (
            ("base_identity", "base_id"),
            ("qr_version", "qr_version"),
            ("module_count", "module_count"),
            ("mask_pattern", "mask_pattern"),
            ("version_band", "version_band"),
            ("payload_length_bin", "payload_length_bin"),
            ("payload_utf8_bytes", "payload_utf8_bytes"),
            ("qr_matrix_sha256", "qr_matrix_sha256"),
        ):
            if metadata.get(plan_key) != pack_case.get(pack_key):
                raise ValueError(f"{case_id}: plan/pack {plan_key} mismatch")
        if metadata.get("deployment_holdout_eligible") is not True:
            raise ValueError(f"{case_id}: source archive was not the locked M8 holdout")
    return plan_cases, pack_cases


def development_row(
    frame: ValidatedFrame,
    plan_case: dict[str, Any],
    relative_path: str,
) -> dict[str, Any]:
    if frame.ground_truth != "clean":
        raise ValueError("only clean M8 frames may enter the r07 hard-negative set")
    metadata = dict(plan_case["metadata"])
    base_id = str(metadata["base_identity"])
    split = "validation" if base_id in VALIDATION_BASE_IDENTITIES else "train"
    return {
        "path": relative_path,
        "label": "clean",
        "class_id": 0,
        "split": split,
        "group_id": f"consumed_blind_clean_2026_09:{base_id}",
        "source": "qrguard_consumed_blind_clean_2026_09_camera",
        "capture_kind": "exact_app_screen_capture_consumed_blind",
        "quality_condition": "screen_moire_or_compression",
        "quality_severity": "observed",
        "attack_recipe": "none",
        "is_exact_app_crop": True,
        "licence": "project_internal_opt_in",
        "session_id": frame.session_id,
        "device_model": "android_test_device_unrecorded",
        "display_id": "screen_test_display_unrecorded",
        "image_source": "camera",
        "paired_group": f"consumed_blind_clean_2026_09:{frame.case_id}",
        "physical_qr": f"consumed_blind_clean_2026_09:{base_id}",
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
        "evidence_role": EVIDENCE_ROLE,
        "source_was_blind_holdout": True,
        "blind_holdout_consumed": True,
        "development_only": True,
        "deployment_holdout_eligible": False,
        "promotion_eligible": False,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _validate_development_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 80:
        raise ValueError(f"expected 80 clean M8 frames, got {len(rows)}")
    if Counter(row["split"] for row in rows) != {"train": 60, "validation": 20}:
        raise ValueError("consumed M8 clean split must be 60 train / 20 validation")
    case_counts = Counter(str(row["case_id"]) for row in rows)
    if len(case_counts) != 16 or set(case_counts.values()) != {5}:
        raise ValueError("every clean M8 case must contribute exactly five frames")
    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group_splits[str(row["group_id"])].add(str(row["split"]))
        if (
            row.get("label") != "clean"
            or str(row.get("development_only", "")).lower() != "true"
            or str(row.get("deployment_holdout_eligible", "")).lower() != "false"
            or str(row.get("promotion_eligible", "")).lower() != "false"
        ):
            raise ValueError("consumed M8 row escaped its development-only contract")
    if len(group_splits) != 16 or any(
        len(splits) != 1 for splits in group_splits.values()
    ):
        raise ValueError("consumed M8 QR identities leak across development splits")
    band_cases = Counter(
        (row["split"], row["version_band"], row["case_id"]) for row in rows
    )
    band_counts = Counter((split, band) for split, band, _ in band_cases)
    if band_counts != {
        ("train", "low_v1_v3"): 4,
        ("train", "medium_v4_v6"): 4,
        ("train", "high_v7_plus"): 4,
        ("validation", "low_v1_v3"): 1,
        ("validation", "medium_v4_v6"): 1,
        ("validation", "high_v7_plus"): 2,
    }:
        raise ValueError(f"consumed M8 Version-band split drifted: {band_counts}")


def import_capture(
    *,
    archive_path: Path,
    plan_path: Path,
    pack_manifest_path: Path,
    data_root: Path,
) -> dict[str, Any]:
    if data_root.exists() and any(data_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty data root: {data_root}")
    actual_archive_hash = _sha256(archive_path)
    if actual_archive_hash != SOURCE_ARCHIVE_SHA256:
        raise ValueError(
            f"consumed M8 archive SHA-256 mismatch: {actual_archive_hash}"
        )
    plan_cases, _ = _case_contracts(plan_path, pack_manifest_path)
    frames = validate_archive(archive_path, plan_path)
    clean_frames = [frame for frame in frames if frame.ground_truth == "clean"]
    if len({frame.crop_sha256 for frame in clean_frames}) != len(clean_frames):
        raise ValueError("consumed M8 clean set contains duplicate crop pixels")

    rows: list[dict[str, Any]] = []
    destinations: list[tuple[Path, bytes]] = []
    for frame in clean_frames:
        plan_case = plan_cases[frame.case_id]
        base_id = str(plan_case["metadata"]["base_identity"])
        split = "validation" if base_id in VALIDATION_BASE_IDENTITIES else "train"
        destination = (
            data_root / "images" / split / frame.case_id / f"crop_{frame.frame_index:02d}.png"
        )
        rows.append(
            development_row(
                frame, plan_case, destination.relative_to(ROOT).as_posix()
            )
        )
        destinations.append((destination, frame.crop_png))
    _validate_development_rows(rows)

    data_root.mkdir(parents=True, exist_ok=True)
    for destination, raw in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    manifest_path = data_root / "manifest.csv"
    _write_csv(manifest_path, rows)
    audit = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "evidence_role": EVIDENCE_ROLE,
        "source_archive_sha256": actual_archive_hash,
        "source_holdout_consumed": True,
        "deployment_holdout_eligible": False,
        "promotion_eligible": False,
        "admission_rule": "clean exact-app crops only; attacks excluded",
        "excluded_attack_frames": len(frames) - len(clean_frames),
        "admitted_clean_frames": len(rows),
        "admitted_clean_sessions": len({row["case_id"] for row in rows}),
        "split_rows": dict(Counter(row["split"] for row in rows)),
        "version_band_sessions": {
            f"{split}/{band}": len(
                {
                    row["case_id"]
                    for row in rows
                    if row["split"] == split and row["version_band"] == band
                }
            )
            for split in ("train", "validation")
            for band in ("low_v1_v3", "medium_v4_v6", "high_v7_plus")
        },
        "validation_base_identities": sorted(VALIDATION_BASE_IDENTITIES),
        "plan_sha256": _sha256(plan_path),
        "pack_manifest_sha256": _sha256(pack_manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "raw_payload_stored": False,
    }
    (data_root / "audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--pack-manifest", type=Path, default=DEFAULT_PACK_MANIFEST)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = import_capture(
        archive_path=args.archive.resolve(strict=True),
        plan_path=args.plan.resolve(strict=True),
        pack_manifest_path=args.pack_manifest.resolve(strict=True),
        data_root=args.data_root.resolve(),
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
