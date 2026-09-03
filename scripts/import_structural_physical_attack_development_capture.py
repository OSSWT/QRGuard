"""Import verified physical-attack development captures for Structural r02.

Only clean sessions and adversarial sessions that pass the locked post-capture
survival rule are admitted. Non-surviving attacks remain evaluation evidence and
are never silently relabelled or used for classifier fitting. Every temporal
frame inherits its base QR development split, preventing identity leakage.
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

from scripts.analyze_live_camera_diagnostic import (  # noqa: E402
    ValidatedFrame,
    validate_archive,
)

CAMPAIGN_ID = "structural-physical-attack-development-2026-09-r02"
CANDIDATE_VERSION = "structural-2026.09-r02"
DEFAULT_PLAN = (
    ROOT / "app/assets/capture/structural_physical_attack_development_plan.json"
)
DEFAULT_PACK_MANIFEST = (
    ROOT / "dist/Structural_Physical_Attack_Development_2026-09-r02/MANIFEST.json"
)
DEFAULT_SURVIVAL_REPORT = (
    ROOT
    / "research_evidence/structural/performance"
    / "screen-camera-robustness-2026-09-r01"
    / "R02_PHYSICAL_ATTACK_DEVELOPMENT_SURVIVAL/ANALYSIS.json"
)
DEFAULT_BASE_MANIFEST = (
    ROOT
    / "ml_training/datasets/structural/processed/structural-2026.09-r01"
    / "manifest.csv"
)
DEFAULT_DATA_ROOT = (
    ROOT / "data/structural_physical_attack_development/physical_attack_release_r02"
)
DEFAULT_CANDIDATE_MANIFEST = (
    ROOT
    / "ml_training/datasets/structural/processed"
    / CANDIDATE_VERSION
    / "manifest.csv"
)
CLASS_IDS = {"clean": 0, "adversarial": 1, "tampered": 2}


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


def _contracts(
    plan_path: Path, pack_manifest_path: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    plan = _read_json(plan_path)
    pack = _read_json(pack_manifest_path)
    if plan.get("campaign_id") != CAMPAIGN_ID or pack.get("pack_id") != CAMPAIGN_ID:
        raise ValueError("physical-attack campaign identity mismatch")
    plan_cases = {str(row["case_id"]): row for row in plan.get("cases", [])}
    pack_cases = {str(row["case_id"]): row for row in pack.get("cases", [])}
    if len(plan_cases) != 48 or set(plan_cases) != set(pack_cases):
        raise ValueError("plan and pack must contain the same 48 unique cases")
    if Counter(str(row["label"]) for row in pack_cases.values()) != {
        "clean": 16,
        "adversarial": 32,
    }:
        raise ValueError("physical pack must contain 16 clean and 32 attack cases")
    for case_id, plan_case in plan_cases.items():
        pack_case = pack_cases[case_id]
        metadata = dict(plan_case.get("metadata", {}))
        if plan_case.get("ground_truth") != pack_case.get("label"):
            raise ValueError(f"{case_id}: plan/pack label mismatch")
        if plan_case.get("expected_payload_sha256") != pack_case.get("payload_sha256"):
            raise ValueError(f"{case_id}: plan/pack payload hash mismatch")
        for key in (
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
            if metadata.get(key) != pack_case.get(key):
                raise ValueError(f"{case_id}: plan/pack metadata {key} mismatch")
        if metadata.get("base_identity") != pack_case.get("base_id"):
            raise ValueError(f"{case_id}: plan/pack base identity mismatch")
        if metadata["development_split"] not in {"train", "validation"}:
            raise ValueError(f"{case_id}: invalid development split")
        if metadata["deployment_holdout_eligible"] is not False:
            raise ValueError(f"{case_id}: development data cannot be holdout eligible")
    return plan_cases, pack_cases


def verified_attack_cases(
    survival_report: dict[str, Any], archive_sha256: str
) -> set[str]:
    if survival_report.get("campaign_id") != CAMPAIGN_ID:
        raise ValueError("survival report campaign mismatch")
    if survival_report.get("source_archive_sha256") != archive_sha256:
        raise ValueError("survival report does not match the source archive")
    if survival_report.get("adversarial_pairs") != 32:
        raise ValueError("survival report must evaluate all 32 adversarial cases")
    rows = survival_report.get("rows", [])
    case_ids = [str(row.get("adversarial_case_id", "")) for row in rows]
    if len(rows) != 32 or len(set(case_ids)) != 32:
        raise ValueError("survival report must contain 32 unique attack rows")
    selected = {
        str(row["adversarial_case_id"])
        for row in rows
        if row.get("physical_attack_survival_verified") is True
    }
    if len(selected) != int(survival_report.get("verified_surviving_attacks", -1)):
        raise ValueError("survival report verified count is inconsistent")
    if len(selected) != 10:
        raise ValueError(
            f"locked r02 evidence requires 10 surviving attacks, got {len(selected)}"
        )
    return selected


def development_row(
    frame: ValidatedFrame,
    plan_case: dict[str, Any],
    pack_case: dict[str, Any],
    relative_path: str,
    survival_verified: bool,
) -> dict[str, Any]:
    metadata = dict(plan_case["metadata"])
    label = frame.ground_truth
    base_id = str(metadata["base_identity"])
    return {
        "path": relative_path,
        "label": label,
        "class_id": CLASS_IDS[label],
        "split": metadata["development_split"],
        "group_id": f"physical_attack_dev_2026_09:{base_id}",
        "source": "qrguard_physical_attack_2026_09_camera",
        "capture_kind": "exact_app_screen_capture",
        "quality_condition": "screen_moire_or_compression",
        "quality_severity": "none",
        "attack_recipe": (
            str(pack_case["attack_method"]) if label == "adversarial" else "none"
        ),
        "is_exact_app_crop": True,
        "licence": "project_internal_opt_in",
        "session_id": frame.session_id,
        "device_model": "android_test_device_unrecorded",
        "display_id": "screen_device_unrecorded",
        "image_source": "camera",
        "paired_group": f"physical_attack_dev_2026_09:{frame.case_id}",
        "physical_qr": f"physical_attack_dev_2026_09:{base_id}",
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
        "physical_attack_survival_verified": survival_verified,
        "development_campaign": CAMPAIGN_ID,
        "deployment_holdout_eligible": False,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _validate_selected_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 130:
        raise ValueError(f"expected 130 admitted physical frames, got {len(rows)}")
    counts = Counter((row["split"], row["label"]) for row in rows)
    expected = {
        ("train", "clean"): 60,
        ("validation", "clean"): 20,
        ("train", "adversarial"): 40,
        ("validation", "adversarial"): 10,
    }
    if counts != expected:
        raise ValueError(f"unexpected selected physical split/class counts: {counts}")
    case_counts = Counter(str(row["case_id"]) for row in rows)
    if len(case_counts) != 26 or set(case_counts.values()) != {5}:
        raise ValueError(
            "16 clean plus 10 verified attacks must each contribute five frames"
        )
    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group_splits[str(row["group_id"])].add(str(row["split"]))
        if row["label"] == "adversarial" and row[
            "physical_attack_survival_verified"
        ] is not True:
            raise ValueError("non-surviving physical attack entered classifier data")
    if len(group_splits) != 16 or any(
        len(splits) != 1 for splits in group_splits.values()
    ):
        raise ValueError("physical base identity leaks across development splits")


def import_capture(
    *,
    archive_path: Path,
    plan_path: Path,
    pack_manifest_path: Path,
    survival_report_path: Path,
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
    plan_cases, pack_cases = _contracts(plan_path, pack_manifest_path)
    archive_hash = _sha256(archive_path)
    selected_attacks = verified_attack_cases(
        _read_json(survival_report_path), archive_hash
    )
    frames = validate_archive(archive_path, plan_path)
    if len(frames) != 240 or len({frame.crop_sha256 for frame in frames}) != 240:
        raise ValueError("physical archive must contain 240 unique crops")

    selected_rows: list[dict[str, Any]] = []
    destinations: list[tuple[Path, bytes]] = []
    excluded_attack_frames = 0
    for frame in frames:
        include = frame.ground_truth == "clean" or frame.case_id in selected_attacks
        if not include:
            excluded_attack_frames += 1
            continue
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
        selected_rows.append(
            development_row(
                frame,
                plan_case,
                pack_case,
                destination.relative_to(ROOT).as_posix(),
                frame.case_id in selected_attacks,
            )
        )
        destinations.append((destination, frame.crop_png))
    _validate_selected_rows(selected_rows)
    if excluded_attack_frames != 110:
        raise ValueError(
            "expected to quarantine 110 non-surviving frames, got "
            f"{excluded_attack_frames}"
        )

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
    new_groups = {str(row["group_id"]) for row in selected_rows}
    if new_groups & set(base_groups):
        raise ValueError("physical development groups collide with base groups")

    data_root.mkdir(parents=True, exist_ok=True)
    for destination, raw in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    _write_csv(data_root / "manifest.csv", selected_rows)
    candidate_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    combined_rows = [*base_rows, *selected_rows]
    _write_csv(candidate_manifest_path, combined_rows)

    audit = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "candidate_version": CANDIDATE_VERSION,
        "deployment_holdout_eligible": False,
        "source_archive": {"filename": archive_path.name, "sha256": archive_hash},
        "survival_report": {
            "path": survival_report_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(survival_report_path),
            "verified_attack_sessions": len(selected_attacks),
            "quarantined_non_surviving_attack_sessions": 32 - len(selected_attacks),
        },
        "base_manifest": {
            "path": base_manifest_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(base_manifest_path),
            "rows": len(base_rows),
        },
        "development_manifest": {
            "path": (data_root / "manifest.csv").relative_to(ROOT).as_posix(),
            "sha256": _sha256(data_root / "manifest.csv"),
            "rows": len(selected_rows),
            "counts": dict(Counter(row["label"] for row in selected_rows)),
            "splits": dict(Counter(row["split"] for row in selected_rows)),
            "unique_base_identities": len(new_groups),
        },
        "candidate_manifest": {
            "path": candidate_manifest_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(candidate_manifest_path),
            "rows": len(combined_rows),
        },
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
    parser.add_argument("--survival-report", type=Path, default=DEFAULT_SURVIVAL_REPORT)
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
        survival_report_path=args.survival_report.resolve(strict=True),
        base_manifest_path=args.base_manifest.resolve(strict=True),
        data_root=args.data_root.resolve(),
        candidate_manifest_path=args.candidate_manifest.resolve(),
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
