"""Import only physically verified M8 attacks as non-promoting hard positives.

The source archive has already been consumed by development analysis and can
never promote a model. Attack labels are admitted only when the locked paired
post-capture survival audit proves that the adversarial effect survived the
screen/camera channel.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_live_camera_diagnostic import ValidatedFrame, validate_archive
from scripts.import_consumed_blind_clean_development import _case_contracts

CAMPAIGN_ID = "structural-coverage-blind-holdout-2026-09-r01"
EVIDENCE_ROLE = "consumed_verified_attack_development"
SOURCE_ARCHIVE_SHA256 = (
    "d5930ffcaf1edc0702afd5ff2b2241584a95edd9f9f0de81fdc8a5a5a7921f6d"
)
SURVIVAL_AUDIT_SHA256 = (
    "7cabf33531cecbfba6b87310c7a24f415ac42b54bee8cbd1fe62424472f2cc6d"
)
SOURCE_NAME = "qrguard_consumed_blind_verified_attack_camera"
DEFAULT_ARCHIVE = (
    Path.home()
    / "Downloads/Telegram Desktop/"
    "QRGuard_Diagnostic_structural_coverage_blind_holdout_2026_09_r01.zip"
)
DEFAULT_PLAN = ROOT / "app/assets/capture/structural_coverage_blind_holdout_plan.json"
DEFAULT_PACK_MANIFEST = (
    ROOT / "dist/Structural_Coverage_Blind_Holdout_2026-09-r01/MANIFEST.json"
)
DEFAULT_SURVIVAL_AUDIT = (
    ROOT
    / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r01/"
    "M8_PHYSICAL_ATTACK_SURVIVAL/ANALYSIS.json"
)
DEFAULT_DATA_ROOT = (
    ROOT / "data/structural_consumed_blind_attack_development/r07-corrective-v1"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_verified_cases(path: Path) -> dict[str, dict[str, Any]]:
    if _sha256(path) != SURVIVAL_AUDIT_SHA256:
        raise ValueError("M8 survival audit SHA-256 mismatch")
    report = json.loads(path.read_text(encoding="utf-8"))
    if (
        report.get("evaluation") != "paired_post_capture_adversarial_survival"
        or report.get("campaign_id") != CAMPAIGN_ID
        or report.get("source_archive_sha256") != SOURCE_ARCHIVE_SHA256
    ):
        raise ValueError("M8 survival audit identity mismatch")
    verified = {
        str(row["adversarial_case_id"]): row
        for row in report.get("rows", [])
        if row.get("physical_attack_survival_verified") is True
    }
    if set(verified) != {"BLD-27-90C833", "BLD-39-5285E9"}:
        raise ValueError("verified M8 attack set drifted")
    return verified


def development_row(
    frame: ValidatedFrame,
    plan_case: dict[str, Any],
    survival_row: dict[str, Any],
    relative_path: str,
) -> dict[str, Any]:
    if frame.ground_truth != "adversarial":
        raise ValueError("only verified adversarial M8 frames may enter this set")
    metadata = dict(plan_case["metadata"])
    base_id = str(metadata["base_identity"])
    if survival_row.get("physical_attack_survival_verified") is not True:
        raise ValueError("attack does not have verified physical survival")
    if survival_row.get("base_identity") != base_id:
        raise ValueError("survival audit base identity mismatch")
    return {
        "path": relative_path,
        "label": "adversarial",
        "class_id": 1,
        "split": "train",
        "group_id": f"consumed_blind_verified_attack:{base_id}",
        "source": SOURCE_NAME,
        "capture_kind": "exact_app_screen_capture_consumed_verified_attack",
        "quality_condition": "screen_moire_or_compression",
        "quality_severity": "observed",
        "attack_recipe": metadata["attack_method"],
        "is_exact_app_crop": True,
        "licence": "project_internal_opt_in",
        "session_id": frame.session_id,
        "device_model": "android_test_device_unrecorded",
        "display_id": "screen_test_display_unrecorded",
        "image_source": "camera",
        "paired_group": f"consumed_blind_verified_attack:{frame.case_id}",
        "physical_qr": f"consumed_blind_verified_attack:{base_id}",
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
        "physical_attack_survival_verified": True,
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


def _validate_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 10:
        raise ValueError(f"expected 10 verified M8 attack frames, got {len(rows)}")
    case_counts = Counter(str(row["case_id"]) for row in rows)
    if case_counts != {"BLD-27-90C833": 5, "BLD-39-5285E9": 5}:
        raise ValueError(f"verified M8 attack frame contract drifted: {case_counts}")
    if len({str(row["crop_sha256"]) for row in rows}) != len(rows):
        raise ValueError("verified M8 attack set contains duplicate crop pixels")
    for row in rows:
        if (
            row.get("label") != "adversarial"
            or row.get("split") != "train"
            or row.get("physical_attack_survival_verified") is not True
            or row.get("development_only") is not True
            or row.get("deployment_holdout_eligible") is not False
            or row.get("promotion_eligible") is not False
        ):
            raise ValueError("verified M8 attack row escaped its safety contract")


def import_capture(
    *,
    archive_path: Path,
    plan_path: Path,
    pack_manifest_path: Path,
    survival_audit_path: Path,
    data_root: Path,
) -> dict[str, Any]:
    if data_root.exists() and any(data_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty data root: {data_root}")
    if _sha256(archive_path) != SOURCE_ARCHIVE_SHA256:
        raise ValueError("consumed M8 archive SHA-256 mismatch")
    plan_cases, _ = _case_contracts(plan_path, pack_manifest_path)
    verified = _load_verified_cases(survival_audit_path)
    frames = [
        frame
        for frame in validate_archive(archive_path, plan_path)
        if frame.case_id in verified
    ]

    rows: list[dict[str, Any]] = []
    destinations: list[tuple[Path, bytes]] = []
    for frame in frames:
        destination = (
            data_root
            / "images/train"
            / frame.case_id
            / f"crop_{frame.frame_index:02d}.png"
        )
        rows.append(
            development_row(
                frame,
                plan_cases[frame.case_id],
                verified[frame.case_id],
                destination.relative_to(ROOT).as_posix(),
            )
        )
        destinations.append((destination, frame.crop_png))
    _validate_rows(rows)

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
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "survival_audit_sha256": SURVIVAL_AUDIT_SHA256,
        "admission_rule": "only attacks with locked post-capture survival verification",
        "admitted_frames": len(rows),
        "admitted_sessions": len({row["case_id"] for row in rows}),
        "verified_cases": sorted(verified),
        "development_only": True,
        "deployment_holdout_eligible": False,
        "promotion_eligible": False,
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
    parser.add_argument("--survival-audit", type=Path, default=DEFAULT_SURVIVAL_AUDIT)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = import_capture(
        archive_path=args.archive.resolve(strict=True),
        plan_path=args.plan.resolve(strict=True),
        pack_manifest_path=args.pack_manifest.resolve(strict=True),
        survival_audit_path=args.survival_audit.resolve(strict=True),
        data_root=args.data_root.resolve(),
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
