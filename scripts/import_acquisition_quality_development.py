"""Import validated acquisition captures as development-only training evidence.

Only Structural-clean crops are admitted.  Payload text is never extracted or
stored; the manifest retains the on-device SHA-256 identifier required for QR
identity grouping and provenance checks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.analyze_live_camera_diagnostic import ValidatedFrame, validate_archive
except ModuleNotFoundError:
    from analyze_live_camera_diagnostic import ValidatedFrame, validate_archive

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "app/assets/capture/acquisition_validation_plan.json"
DEFAULT_OUTPUT = ROOT / "data/acquisition_quality_development/acquisition_quality_release_r02"
EXPECTED_ARCHIVE_SHA256 = (
    "02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4"
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_plan(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    cases = {str(row["case_id"]): row for row in plan["cases"]}
    distances = {str(row["id"]): row for row in plan["distances"]}
    return cases, distances


def _quality_condition(distance: dict[str, Any]) -> str:
    role = str(distance.get("metadata", {}).get("exposure_role", "baseline"))
    return {
        "baseline": "normal",
        "overexposure_stress": "overexposure",
        "underexposure_stress": "underexposure",
    }.get(role, role)


def _manifest_row(
    frame: ValidatedFrame,
    case: dict[str, Any],
    distance: dict[str, Any],
    relative_path: str,
) -> dict[str, Any]:
    metadata = case.get("metadata", {})
    payload_bytes = metadata.get("payload_utf8_bytes", "")
    return {
        "path": relative_path,
        "label": "clean",
        "class_id": 0,
        "split": "train",
        "group_id": f"qrguard_acquisition_development:{frame.case_id}",
        "source": "qrguard_acquisition_quality_2026_09_camera",
        "capture_kind": "exact_qrguard_app_camera_development_hard_negative",
        "quality_condition": _quality_condition(distance),
        "quality_severity": "controlled_stress",
        "attack_recipe": "none",
        "is_exact_app_crop": True,
        "licence": "project_internal_opt_in",
        "session_id": frame.session_id,
        "device_model": "xiaomi-10t-pro",
        "display_id": "development-screen-2026-09",
        "image_source": "camera",
        "paired_group": f"qrguard_acquisition_development:{frame.case_id}",
        "physical_qr": str(metadata.get("source_image_sha256", frame.case_id)),
        "payload_hash": frame.payload_sha256,
        "case_id": frame.case_id,
        "frame_index": frame.frame_index,
        "crop_sha256": frame.crop_sha256,
        "qr_version": metadata.get("qr_version", ""),
        "module_count": metadata.get("module_count", ""),
        "mask_pattern": "not_recorded",
        "version_band": (
            "low"
            if int(metadata.get("qr_version", 1)) <= 5
            else "medium"
            if int(metadata.get("qr_version", 1)) <= 10
            else "high"
        ),
        "payload_length_bin": metadata.get("payload_length_bin", "not_recorded"),
        "payload_utf8_bytes": payload_bytes,
        "qr_matrix_sha256": metadata.get("source_image_sha256", "not_recorded"),
        "development_campaign": "acquisition-quality-exposure-module-scale-2026-09-r02",
        "development_only": True,
        "deployment_holdout_eligible": False,
        "physical_attack_survival_verified": "not_applicable",
        "capture_distance": frame.distance,
        "qr_coverage": frame.qr_coverage,
        "frame_width": frame.frame_width,
        "frame_height": frame.frame_height,
    }


def import_archive(archive: Path, plan: Path, output: Path) -> dict[str, Any]:
    archive_hash = _sha256_file(archive)
    if archive_hash != EXPECTED_ARCHIVE_SHA256:
        raise ValueError(
            f"unexpected acquisition archive SHA-256 {archive_hash}; "
            f"expected {EXPECTED_ARCHIVE_SHA256}"
        )
    frames = validate_archive(archive, plan)
    cases, distances = _load_plan(plan)
    admitted = [frame for frame in frames if frame.ground_truth == "clean"]
    if len(frames) != 120 or len(admitted) != 90:
        raise ValueError(
            f"expected 120 validated frames and 90 clean frames; got "
            f"{len(frames)} and {len(admitted)}"
        )
    if len({frame.session_id for frame in admitted}) != 18:
        raise ValueError("expected exactly 18 clean acquisition sessions")

    crop_root = output / "crops"
    rows: list[dict[str, Any]] = []
    for frame in admitted:
        if frame.case_id not in cases or frame.distance not in distances:
            raise ValueError(f"unplanned acquisition frame: {frame.case_id}/{frame.distance}")
        destination = (
            crop_root
            / frame.case_id
            / frame.distance
            / f"frame-{frame.frame_index:02d}-{frame.crop_sha256[:12]}.png"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and _sha256_file(destination) != frame.crop_sha256:
            raise ValueError(f"existing crop hash mismatch: {destination}")
        if not destination.is_file():
            destination.write_bytes(frame.crop_png)
        if _sha256_file(destination) != frame.crop_sha256:
            raise ValueError(f"written crop hash mismatch: {destination}")
        rows.append(
            _manifest_row(
                frame,
                cases[frame.case_id],
                distances[frame.distance],
                destination.relative_to(ROOT).as_posix(),
            )
        )

    rows.sort(
        key=lambda row: (
            str(row["case_id"]),
            str(row["capture_distance"]),
            str(row["session_id"]),
            int(row["frame_index"]),
        )
    )
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    audit = {
        "schema_version": 1,
        "campaign_id": "acquisition-quality-exposure-module-scale-2026-09-r02",
        "source_archive_sha256": archive_hash,
        "validated_frames": len(frames),
        "admitted_clean_frames": len(rows),
        "admitted_sessions": len({row["session_id"] for row in rows}),
        "admitted_cases": sorted({str(row["case_id"]) for row in rows}),
        "rows_by_quality_condition": dict(
            sorted(Counter(str(row["quality_condition"]) for row in rows).items())
        ),
        "manifest_sha256": _sha256_file(manifest),
        "privacy": {
            "raw_payload_stored": False,
            "payload_identifier": "sha256 of on-device decoded text",
        },
        "admission_scope": (
            "development-only Structural-clean hard negatives; all attack frames "
            "remain excluded because attack recall already passed"
        ),
        "promotion_eligible": False,
        "future_evaluation_use": (
            "prohibited for r04 validation, testing, or promotion after admission"
        ),
    }
    (output / "audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = import_archive(
        args.archive.resolve(strict=True),
        args.plan.resolve(strict=True),
        args.output.resolve(),
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
