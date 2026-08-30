"""Import prepared Gallery references without leaking the locked test split.

The numbered capture packs contain the exact digital PNGs that were supplied to
QRGuard's Gallery picker and displayed for the paired Camera captures.  This
importer verifies their hashes, copies only train/validation references into a
canonical local dataset, and records enough provenance to rebuild the Structural
v3 training manifest without depending on a user's Desktop layout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASS_NAMES = ("clean", "adversarial", "tampered")
ALLOWED_SPLITS = ("train", "validation")
CASE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_pack_path(pack: Path, relative: str) -> Path:
    candidate = (pack / relative).resolve()
    try:
        candidate.relative_to(pack.resolve())
    except ValueError as error:
        raise ValueError(f"reference escapes capture pack: {relative}") from error
    return candidate


def _load_pack(pack: Path, campaign_id: str) -> tuple[dict, list[dict]]:
    index_path = pack / "capture_index.json"
    if not index_path.is_file():
        raise FileNotFoundError(f"capture pack index not found: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("campaign_id") != campaign_id:
        raise ValueError(
            f"capture pack campaign mismatch in {index_path}: "
            f"{index.get('campaign_id')!r} != {campaign_id!r}"
        )
    rows = index.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"capture pack has no indexed references: {index_path}")
    return index, rows


def import_references(
    pack_paths: list[Path],
    output: Path,
    *,
    root: Path = ROOT,
    campaign_id: str = "structural-v3-real-2026.03-r01",
    include_test: bool = False,
) -> dict:
    """Verify and import capture-pack PNGs, returning the written audit."""
    root = root.resolve()
    output = output.resolve()
    try:
        output.relative_to(root)
    except ValueError as error:
        raise ValueError("output must remain inside the repository root") from error

    seen_cases: set[str] = set()
    seen_payloads: set[str] = set()
    imported: list[dict] = []
    excluded = Counter()
    pack_audit = []

    for raw_pack in pack_paths:
        pack = raw_pack.resolve()
        index, rows = _load_pack(pack, campaign_id)
        index_path = pack / "capture_index.json"
        pack_audit.append(
            {
                "scope_name": index.get("scope_name", pack.name),
                "index_sha256": _sha256(index_path),
                "indexed_references": len(rows),
            }
        )
        for row in rows:
            case_id = str(row.get("case_id", "")).strip()
            label = str(row.get("label", "")).strip().lower()
            split = str(row.get("assigned_split", "")).strip().lower()
            payload_hash = str(row.get("payload_sha256", "")).strip().lower()
            expected_hash = str(row.get("reference_sha256", "")).strip().lower()
            if not CASE_ID_PATTERN.fullmatch(case_id):
                raise ValueError(f"invalid campaign case ID: {case_id!r}")
            if label not in CLASS_NAMES:
                raise ValueError(f"invalid label for {case_id}: {label!r}")
            if split not in (*ALLOWED_SPLITS, "test"):
                raise ValueError(f"invalid assigned split for {case_id}: {split!r}")
            if len(payload_hash) != 64 or len(expected_hash) != 64:
                raise ValueError(f"missing SHA-256 provenance for {case_id}")
            if case_id in seen_cases:
                raise ValueError(f"duplicate campaign case across packs: {case_id}")
            if payload_hash in seen_payloads:
                raise ValueError(f"duplicate payload across packs: {case_id}")
            seen_cases.add(case_id)
            seen_payloads.add(payload_hash)

            source = _safe_pack_path(pack, str(row.get("gallery_reference", "")))
            if not source.is_file():
                raise FileNotFoundError(f"reference image not found: {source}")
            actual_hash = _sha256(source)
            if actual_hash != expected_hash:
                raise ValueError(
                    f"reference hash mismatch for {case_id}: "
                    f"{actual_hash} != {expected_hash}"
                )
            if split == "test" and not include_test:
                excluded[(label, split)] += 1
                continue

            destination = output / "images" / label / f"{case_id}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            imported.append(
                {
                    "path": destination.relative_to(root).as_posix(),
                    "sha256": actual_hash,
                    "label": label,
                    "class_id": CLASS_NAMES.index(label),
                    "split": split,
                    "group_id": f"qrguard_runtime:{payload_hash}",
                    "session_id": f"prepared-gallery:{case_id}",
                    "source": "qrguard_prepared_gallery_reference",
                    "capture_kind": "prepared_gallery_reference",
                    "device_model": "digital-reference",
                    "quality_condition": row.get("quality_condition", "normal"),
                    "quality_severity": row.get("quality_severity", "none"),
                    "image_source": "gallery",
                    "paired_group": payload_hash,
                    "physical_qr": payload_hash,
                    "payload_hash": payload_hash,
                    "attack_recipe": row.get("manipulation_method")
                    or row.get("attack_method")
                    or "none",
                    "is_exact_app_crop": False,
                    "licence": "project_generated_internal",
                    "campaign_id": campaign_id,
                    "case_id": case_id,
                    "reference_sha256": actual_hash,
                }
            )

    imported.sort(key=lambda row: (row["label"], row["split"], row["case_id"]))
    if not imported:
        raise ValueError("no train/validation Gallery references were imported")
    manifest_path = output / "manifest.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(imported[0])
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(imported)

    imported_counts = Counter((row["label"], row["split"]) for row in imported)
    audit = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "train_and_validation_only; locked test references excluded",
        "source_packs": pack_audit,
        "indexed_unique_cases": len(seen_cases),
        "imported_references": len(imported),
        "excluded_test_references": sum(excluded.values()),
        "imported_counts": {
            label: {split: imported_counts[(label, split)] for split in ALLOWED_SPLITS}
            for label in CLASS_NAMES
        },
        "excluded_counts": {
            label: {"test": excluded[(label, "test")]} for label in CLASS_NAMES
        },
        "manifest": manifest_path.relative_to(root).as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "test_rows_written": sum(row["split"] == "test" for row in imported),
        "duplicate_case_ids": 0,
        "duplicate_payload_hashes": 0,
        "hash_mismatches": 0,
    }
    (output / "audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    return audit


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packs", nargs="+", type=Path)
    parser.add_argument(
        "--version",
        default=os.getenv("QRGUARD_STRUCTURAL_VERSION", "structural-2026.03-r01"),
    )
    parser.add_argument("--campaign-id", default="structural-v3-real-2026.03-r01")
    parser.add_argument("--include-test", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output = args.output or ROOT / "data/prepared_gallery_references" / args.version
    audit = import_references(
        args.packs,
        output,
        campaign_id=args.campaign_id,
        include_test=args.include_test,
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
