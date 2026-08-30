"""Build a camera-only repair pack from audited offline exports.

Every Android export is validated without modification. A source is accepted
only when its on-device payload SHA-256 and provenance match the prepared
reference for the declared campaign case. The repair pack then contains only
cases that still lack an accepted Camera source.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml_training.structural.src.capture_campaign import CAMPAIGN_ID
from ml_training.structural.src.import_offline_capture import validate_archive
from scripts.build_numbered_capture_pack import _write_slideshow

ARCHIVE_PATTERN = "QRGuard_Offline_structural_v3_real_2026_03_r01_*.zip"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for name in row:
            if name not in fieldnames:
                fieldnames.append(name)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _expected_provenance(item: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(item.get("default_attack_method", "none")),
        str(item.get("default_attack_reference_sha256", "")),
        str(item.get("default_manipulation_method", "none")),
    )


def _candidate_provenance(metadata: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(metadata.get("attack_method", "none")),
        str(metadata.get("attack_reference_sha256", "")),
        str(metadata.get("manipulation_method", "none")),
    )


def build_repair_pack(
    *,
    source_pack: Path,
    source_selection: Path,
    archive_dir: Path,
    schedule: Path,
    capture_root: Path,
    output: Path,
    archive_output: Path,
    selection_output: Path,
    audit_output: Path,
) -> dict[str, object]:
    for target in (output, archive_output, selection_output, audit_output):
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {target}")

    index = json.loads((source_pack / "capture_index.json").read_text(encoding="utf-8"))
    selection = json.loads(source_selection.read_text(encoding="utf-8"))
    if index.get("campaign_id") != CAMPAIGN_ID:
        raise ValueError("source pack campaign ID does not match")
    if selection.get("campaign_id") != CAMPAIGN_ID:
        raise ValueError("source selection campaign ID does not match")

    source_rows = list(index["rows"])
    rows_by_case = {str(row["case_id"]): row for row in source_rows}
    selected_by_case = {
        str(item["case_id"]): item for item in selection["selected_cases"]
    }
    if set(rows_by_case) != set(selected_by_case):
        raise ValueError("source pack and selection case sets differ")
    payload_hashes = [str(row["payload_sha256"]) for row in source_rows]
    if len(payload_hashes) != len(set(payload_hashes)):
        raise ValueError("source pack contains duplicate payload hashes")

    archives = sorted(archive_dir.glob(ARCHIVE_PATTERN))
    if not archives:
        raise FileNotFoundError(f"no Android exports found in {archive_dir}")

    session_ids: set[str] = set()
    occurrences: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    accepted: dict[tuple[str, str], dict[str, object]] = {}
    quarantined: list[dict[str, object]] = []
    archive_rows: list[dict[str, object]] = []
    totals: Counter[tuple[str, str]] = Counter()

    for archive in archives:
        candidates = validate_archive(archive, schedule, capture_root)
        counts = Counter(
            (candidate.case.label, candidate.image_source)
            for candidate in candidates
        )
        totals.update(counts)
        archive_rows.append(
            {
                "filename": archive.name,
                "sha256": _sha256(archive),
                "bytes": archive.stat().st_size,
                "session_count": len(candidates),
                "counts": {
                    f"{label}/{source}": count
                    for (label, source), count in sorted(counts.items())
                },
            }
        )
        for candidate in candidates:
            if candidate.session_id in session_ids:
                raise ValueError(
                    f"duplicate session ID across exports: {candidate.session_id}"
                )
            session_ids.add(candidate.session_id)
            case_id = candidate.case.case_id
            if case_id not in selected_by_case:
                raise ValueError(f"export contains a case outside the add-on: {case_id}")
            key = (case_id, candidate.image_source)
            occurrences[key].append(candidate.session_id)
            source_row = rows_by_case[case_id]
            selection_item = selected_by_case[case_id]
            payload_matches = (
                candidate.payload_sha256 == str(source_row["payload_sha256"])
            )
            provenance_matches = _candidate_provenance(
                candidate.metadata
            ) == _expected_provenance(selection_item)
            audit_row = {
                "offline_session_id": candidate.session_id,
                "archive": archive.name,
                "case_id": case_id,
                "original_capture_number": int(source_row["number"]),
                "image_source": candidate.image_source,
                "payload_sha256": candidate.payload_sha256,
                "expected_payload_sha256": str(source_row["payload_sha256"]),
                "crop_sha256": candidate.crop_sha256,
                "payload_matches": payload_matches,
                "provenance_matches": provenance_matches,
            }
            if payload_matches and provenance_matches:
                if key in accepted:
                    raise ValueError(
                        f"multiple exact sessions for {case_id}/{candidate.image_source}"
                    )
                accepted[key] = audit_row
            else:
                quarantined.append(audit_row)

    valid_sources: defaultdict[str, set[str]] = defaultdict(set)
    for case_id, source in accepted:
        valid_sources[case_id].add(source)
    required_gallery_cases = {
        case_id
        for case_id, item in selected_by_case.items()
        if item.get("assigned_split") == "test"
    }
    valid_gallery_cases = {
        case_id for case_id, source in accepted if source == "gallery"
    }
    if valid_gallery_cases != required_gallery_cases:
        missing = sorted(required_gallery_cases - valid_gallery_cases)
        unexpected = sorted(valid_gallery_cases - required_gallery_cases)
        raise ValueError(
            f"Gallery audit mismatch; missing={missing}, unexpected={unexpected}"
        )

    pending_source_rows = [
        row
        for row in sorted(source_rows, key=lambda item: int(item["number"]))
        if "camera" not in valid_sources[str(row["case_id"])]
    ]
    if len(pending_source_rows) != 119:
        raise ValueError(
            f"expected 119 Camera repairs, found {len(pending_source_rows)}"
        )

    gallery = output / "scan_with_gallery"
    live = output / "scan_with_live_cam"
    metadata_dir = output / "reference_metadata"
    gallery.mkdir(parents=True)
    live.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)

    repair_rows: list[dict[str, object]] = []
    repair_selection_items: list[dict[str, object]] = []
    for number, source_row in enumerate(pending_source_rows, start=1):
        case_id = str(source_row["case_id"])
        original_number = int(source_row["number"])
        source_image = source_pack / "scan_with_gallery" / f"{original_number}.png"
        source_metadata = (
            source_pack / "reference_metadata" / f"{original_number}.json"
        )
        shutil.copy2(source_image, gallery / f"{number}.png")
        metadata = json.loads(source_metadata.read_text(encoding="utf-8"))
        metadata["capture_number"] = number
        metadata["original_capture_number"] = original_number
        metadata["numbered_reference"] = f"{number}.png"
        (metadata_dir / f"{number}.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )

        repair_row = dict(source_row)
        repair_row["number"] = number
        repair_row["original_capture_number"] = original_number
        repair_row["gallery_required_for_test"] = False
        repair_row["gallery_reference"] = f"scan_with_gallery/{number}.png"
        repair_row["live_camera_review_name"] = f"scan_with_live_cam/{number}.png"
        repair_rows.append(repair_row)

        selection_item = dict(selected_by_case[case_id])
        selection_item["capture_number"] = number
        selection_item["original_capture_number"] = original_number
        selection_item["expected_payload_sha256"] = str(
            source_row["payload_sha256"]
        )
        selection_item["gallery_required_for_test"] = False
        selection_item["repair_reason"] = "missing_exact_camera_reference_binding"
        repair_selection_items.append(selection_item)

    label_counts = Counter(str(row["label"]) for row in repair_rows)
    expected_counts = {"clean": 40, "adversarial": 40, "tampered": 39}
    if dict(label_counts) != expected_counts:
        raise ValueError(f"unexpected repair label counts: {dict(label_counts)}")
    if any(row["assigned_split"] == "test" for row in repair_rows):
        raise ValueError("repair pack unexpectedly contains a Test case")

    repair_selection = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "scope_name": "deployment-addon-repair-119-camera-only",
        "source_scope_name": selection.get("scope_name"),
        "camera_only": True,
        "gallery_required": False,
        "cases_per_label": expected_counts,
        "selected_cases": repair_selection_items,
    }
    selection_output.parent.mkdir(parents=True, exist_ok=True)
    selection_output.write_text(
        json.dumps(repair_selection, indent=2) + "\n", encoding="utf-8"
    )

    repair_index = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "scope_name": "deployment-addon-repair-119-camera-only",
        "camera_only": True,
        "gallery_required": False,
        "selected_cases": len(repair_rows),
        "numbered_cases": len(repair_rows),
        "label_counts": dict(sorted(label_counts.items())),
        "rows": repair_rows,
    }
    (output / "capture_index.json").write_text(
        json.dumps(repair_index, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(output / "capture_index.csv", repair_rows)
    (live / "README.txt").write_text(
        "Optional review screenshots only. App-exported ZIPs are canonical.\n",
        encoding="utf-8",
    )
    (output / "GALLERY_TEST_NUMBERS.txt").write_text(
        "No Gallery capture is required in this repair round.\n",
        encoding="utf-8",
    )
    (output / "README_FIRST.md").write_text(
        "# QRGuard Camera-only repair pack\n\n"
        "This pack contains 119 Camera repairs: 40 Clean, 40 Adversarial, "
        "and 39 Tampered. Gallery is not required.\n\n"
        "1. Install the matching Repair APK over the current app.\n"
        "2. Open `OPEN_REFERENCE_SLIDESHOW.html` at repair number 1.\n"
        "3. Confirm the same repair number and case ID in the app.\n"
        "4. Capture every repair number with Live Camera.\n"
        "5. The app rejects a QR whose payload hash does not match the case.\n"
        "6. Export after at most 40 queued sessions. Expect three ZIPs.\n"
        "7. Keep exported ZIP filenames unchanged and do not reuse prior ZIPs.\n",
        encoding="utf-8",
    )
    _write_slideshow(output, repair_rows)

    duplicate_rows = [
        {
            "case_id": case_id,
            "image_source": source,
            "session_count": len(ids),
            "offline_session_ids": ids,
        }
        for (case_id, source), ids in sorted(occurrences.items())
        if len(ids) > 1
    ]
    audit = {
        "schema_version": 1,
        "audit_type": "qrguard_reference_bound_repair_audit",
        "campaign_id": CAMPAIGN_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_payload_stored": False,
        "archives": archive_rows,
        "archive_count": len(archive_rows),
        "session_count": len(session_ids),
        "totals": {
            f"{label}/{source}": count
            for (label, source), count in sorted(totals.items())
        },
        "exact_valid_session_count": len(accepted),
        "exact_valid_camera_count": sum(
            source == "camera" for _, source in accepted
        ),
        "exact_valid_gallery_count": sum(
            source == "gallery" for _, source in accepted
        ),
        "quarantined_session_count": len(quarantined),
        "duplicate_case_source_count": len(duplicate_rows),
        "repair_camera_count": len(repair_rows),
        "repair_label_counts": dict(sorted(label_counts.items())),
        "accepted_sessions": list(accepted.values()),
        "quarantined_sessions": quarantined,
        "duplicate_case_sources": duplicate_rows,
    }
    audit_output.parent.mkdir(parents=True, exist_ok=True)
    audit_output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(audit_output, output / "SOURCE_EXPORT_AUDIT.json")

    temporary = archive_output.with_suffix(archive_output.suffix + ".tmp")
    archive_output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(output).as_posix())
    temporary.replace(archive_output)
    return audit


def main() -> None:
    campaign = ROOT / "ml_training" / "structural" / "campaigns" / CAMPAIGN_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pack", type=Path, required=True)
    parser.add_argument(
        "--source-selection",
        type=Path,
        default=campaign / "deployment_addon_50x3_selection.json",
    )
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, default=campaign / "campaign.csv")
    parser.add_argument(
        "--capture-root", type=Path, default=ROOT / "data" / "runtime_captures"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-output", type=Path, required=True)
    parser.add_argument(
        "--selection-output",
        type=Path,
        default=campaign / "deployment_addon_repair_119_selection.json",
    )
    parser.add_argument(
        "--audit-output",
        type=Path,
        default=campaign / "deployment_addon_repair_source_audit.json",
    )
    args = parser.parse_args()
    audit = build_repair_pack(
        source_pack=args.source_pack,
        source_selection=args.source_selection,
        archive_dir=args.archive_dir,
        schedule=args.schedule,
        capture_root=args.capture_root,
        output=args.output,
        archive_output=args.archive_output,
        selection_output=args.selection_output,
        audit_output=args.audit_output,
    )
    print(
        f"validated {audit['session_count']} source sessions; "
        f"accepted={audit['exact_valid_session_count']}; "
        f"quarantined={audit['quarantined_session_count']}; "
        f"repair_camera={audit['repair_camera_count']}"
    )


if __name__ == "__main__":
    main()
