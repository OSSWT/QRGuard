"""Bundle validated QRGuard offline archives without rewriting their evidence.

The outer ZIP is a transport bundle, not a direct importer input. Each original
inner archive stays byte-for-byte intact because the strict importer deliberately
accepts at most 40 sessions per archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml_training.structural.src.capture_campaign import CAMPAIGN_ID
from ml_training.structural.src.import_offline_capture import (
    MAX_SESSIONS,
    validate_archive,
)

ARCHIVE_PATTERN = "QRGuard_Offline_structural_v3_real_2026_03_r01_*.zip"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_bundle(
    source_dir: Path,
    output: Path,
    schedule: Path,
    capture_root: Path,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing bundle: {output}")
    archives = sorted(source_dir.glob(ARCHIVE_PATTERN))
    if not archives:
        raise FileNotFoundError(f"no offline archives found in {source_dir}")

    session_ids: set[str] = set()
    case_sources: set[tuple[str, str]] = set()
    payloads: dict[str, str] = {}
    provenance: dict[str, tuple[object, object, object]] = {}
    totals: Counter[tuple[str, str]] = Counter()
    archive_rows: list[dict[str, object]] = []

    for position, archive in enumerate(archives, start=1):
        candidates = validate_archive(archive, schedule, capture_root)
        counts = Counter(
            (candidate.case.label, candidate.image_source)
            for candidate in candidates
        )
        for candidate in candidates:
            key = (candidate.case.case_id, candidate.image_source)
            if candidate.session_id in session_ids:
                raise ValueError(f"duplicate session ID across archives: {candidate.session_id}")
            if key in case_sources:
                raise ValueError(
                    "duplicate case/source across archives: "
                    f"{candidate.case.case_id}/{candidate.image_source}"
                )
            previous_payload = payloads.setdefault(
                candidate.case.case_id, candidate.payload_sha256
            )
            if previous_payload != candidate.payload_sha256:
                raise ValueError(
                    f"cross-archive pair payload mismatch: {candidate.case.case_id}"
                )
            current_provenance = (
                candidate.metadata.get("attack_method"),
                candidate.metadata.get("attack_reference_sha256"),
                candidate.metadata.get("manipulation_method"),
            )
            previous_provenance = provenance.setdefault(
                candidate.case.case_id, current_provenance
            )
            if previous_provenance != current_provenance:
                raise ValueError(
                    f"cross-archive provenance mismatch: {candidate.case.case_id}"
                )
            session_ids.add(candidate.session_id)
            case_sources.add(key)
        totals.update(counts)
        archive_rows.append(
            {
                "order": position,
                "filename": archive.name,
                "bundle_member": f"batches/{position:02d}_{archive.name}",
                "sha256": _sha256(archive),
                "bytes": archive.stat().st_size,
                "session_count": len(candidates),
                "counts": {
                    f"{label}/{source}": count
                    for (label, source), count in sorted(counts.items())
                },
            }
        )

    manifest: dict[str, object] = {
        "schema_version": 1,
        "bundle_type": "qrguard_offline_capture_archive_bundle",
        "campaign_id": CAMPAIGN_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "direct_import_supported": False,
        "direct_import_reason": (
            f"Each original archive is limited to {MAX_SESSIONS} sessions; "
            "extract and validate/import the inner archives in manifest order."
        ),
        "raw_payload_stored": False,
        "archive_count": len(archive_rows),
        "session_count": len(session_ids),
        "unique_case_source_count": len(case_sources),
        "totals": {
            f"{label}/{source}": count
            for (label, source), count in sorted(totals.items())
        },
        "archives": archive_rows,
    }
    readme = (
        "# QRGuard offline 50 x 3 evidence bundle\n\n"
        "This outer ZIP keeps every Android export byte-for-byte unchanged.\n"
        f"The strict importer accepts at most {MAX_SESSIONS} sessions per input, "
        "so do not pass this outer ZIP directly to the importer. Extract it, "
        "then validate/import `batches/01_...` through the last batch in the "
        "order recorded by `bundle_manifest.json`.\n\n"
        "The outer manifest records SHA-256 for every inner ZIP. Raw decoded QR "
        "payload text is not stored.\n"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as bundle:
        bundle.writestr(
            "bundle_manifest.json",
            json.dumps(manifest, indent=2) + "\n",
            compress_type=zipfile.ZIP_DEFLATED,
        )
        bundle.writestr(
            "README_FIRST.md", readme, compress_type=zipfile.ZIP_DEFLATED
        )
        for row, archive in zip(archive_rows, archives, strict=True):
            bundle.write(
                archive,
                str(row["bundle_member"]),
                compress_type=zipfile.ZIP_STORED,
            )
    return manifest


def main() -> None:
    campaign = ROOT / "ml_training" / "structural" / "campaigns" / CAMPAIGN_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--schedule", type=Path, default=campaign / "campaign.csv")
    parser.add_argument(
        "--capture-root", type=Path, default=ROOT / "data" / "runtime_captures"
    )
    args = parser.parse_args()
    manifest = build_bundle(
        args.source_dir, args.output, args.schedule, args.capture_root
    )
    print(
        f"wrote {manifest['archive_count']} validated archives and "
        f"{manifest['session_count']} unique sessions to {args.output}"
    )


if __name__ == "__main__":
    main()
