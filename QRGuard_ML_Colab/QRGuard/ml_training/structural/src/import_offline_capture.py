"""Validate and import QRGuard Android offline-capture ZIPs.

The phone export is an untrusted transport container.  This importer validates
the canonical campaign fields and every content hash before it runs the local
Structural/Fusion pipeline.  Raw QR payloads are never present in the ZIP; when
OpenCV can independently decode a crop, its hash must match the on-device hash.

Validation is the default. Pass ``--commit`` only after reviewing the summary.
The input ZIP and all existing runtime captures are left untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from PIL import Image

from ml_training.structural.src.capture_campaign import (
    ATTACK_METHODS,
    CAMPAIGN_ID,
    MANIPULATION_METHODS,
    CampaignCase,
    audit_campaign,
    load_cases,
)

ARCHIVE_SCHEMA_VERSION = 1
OFFLINE_METADATA_SCHEMA_VERSION = 1
COLLECTOR = "qrguard_android_offline_capture"
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 384 * 1024 * 1024
MAX_SESSION_CROP_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_SESSIONS = 40
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SESSION_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
SAFE_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._/-]{0,79}$")


@dataclass(frozen=True)
class OfflineCandidate:
    session_id: str
    case: CampaignCase
    image_source: str
    captured_at: str
    payload_sha256: str
    crop_sha256: str
    crop_png: bytes
    metadata: dict[str, object]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _load_json(raw: bytes, description: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {description} JSON") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{description} must be one JSON object")
    return value


def _validate_member_names(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    total_size = 0
    for info in archive.infolist():
        name = info.filename
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or info.is_dir()
        ):
            raise ValueError(f"unsafe or unsupported ZIP member: {name!r}")
        if name in members:
            raise ValueError(f"duplicate ZIP member: {name}")
        # Unix symlink file type in the high 16 external-attribute bits.
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise ValueError(f"symbolic links are not allowed in the ZIP: {name}")
        if info.file_size > MAX_SESSION_CROP_BYTES and name != "archive_manifest.json":
            raise ValueError(f"ZIP member exceeds the per-file limit: {name}")
        if name == "archive_manifest.json" and info.file_size > MAX_MANIFEST_BYTES:
            raise ValueError("archive manifest exceeds the size limit")
        total_size += info.file_size
        if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ValueError("offline capture ZIP exceeds the uncompressed size limit")
        members[name] = info
    return members


def _existing_sessions(capture_root: Path) -> dict[tuple[str, str], dict[str, object]]:
    existing: dict[tuple[str, str], dict[str, object]] = {}
    for metadata_path in sorted(capture_root.glob("*/scan_*/metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if metadata.get("campaign_id") != CAMPAIGN_ID:
            continue
        key = (
            str(metadata.get("campaign_case_id", "")),
            str(metadata.get("image_source", "")),
        )
        if key in existing:
            existing[key] = {"duplicate": True}
        else:
            existing[key] = metadata
    return existing


def _validate_safe_value(metadata: dict[str, object], key: str) -> None:
    value = str(metadata.get(key, ""))
    if not SAFE_VALUE_PATTERN.fullmatch(value):
        raise ValueError(f"invalid {key}: {value!r}")


def validate_archive(
    archive_path: Path,
    schedule: Path,
    capture_root: Path,
) -> list[OfflineCandidate]:
    cases = load_cases(schedule)
    by_id = {case.case_id: case for case in cases}
    existing = _existing_sessions(capture_root)

    if archive_path.stat().st_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ValueError("offline capture ZIP exceeds the compressed size limit")
    with zipfile.ZipFile(archive_path) as archive:
        members = _validate_member_names(archive)
        manifest_info = members.get("archive_manifest.json")
        if manifest_info is None:
            raise ValueError("archive_manifest.json is missing")
        manifest = _load_json(archive.read(manifest_info), "archive manifest")
        if (
            manifest.get("offline_capture_archive_schema_version")
            != ARCHIVE_SCHEMA_VERSION
        ):
            raise ValueError("unsupported offline archive schema")
        if manifest.get("collector") != COLLECTOR:
            raise ValueError("archive collector is not the QRGuard Android capture app")
        if manifest.get("campaign_id") != CAMPAIGN_ID:
            raise ValueError(
                "archive campaign ID does not match the canonical campaign"
            )
        if manifest.get("raw_payload_stored") is not False:
            raise ValueError(
                "archive privacy flag does not confirm raw-payload removal"
            )
        session_rows = manifest.get("sessions")
        if (
            not isinstance(session_rows, list)
            or not 1 <= len(session_rows) <= MAX_SESSIONS
        ):
            raise ValueError(f"archive must contain 1 to {MAX_SESSIONS} sessions")
        if manifest.get("session_count") != len(session_rows):
            raise ValueError("archive session_count does not match its manifest rows")

        candidates: list[OfflineCandidate] = []
        used_paths = {"archive_manifest.json"}
        archive_keys: set[tuple[str, str]] = set()
        archive_payloads: dict[str, str] = {}
        archive_provenance: dict[str, tuple[object, object, object]] = {}
        for row in session_rows:
            if not isinstance(row, dict):
                raise TypeError("each archive session row must be an object")
            session_id = str(row.get("offline_session_id", ""))
            case_id = str(row.get("case_id", ""))
            source = str(row.get("image_source", ""))
            base_path = str(row.get("base_path", ""))
            if not SESSION_ID_PATTERN.fullmatch(session_id):
                raise ValueError(f"invalid offline session ID: {session_id!r}")
            case = by_id.get(case_id)
            if case is None:
                raise ValueError(f"unknown campaign case: {case_id or '<missing>'}")
            if source not in {"gallery", "camera"}:
                raise ValueError(f"invalid image source for {case_id}: {source}")
            expected_base = f"sessions/{case_id}/{source}/{session_id}"
            if base_path != expected_base:
                raise ValueError(f"unexpected base path for {case_id}/{source}")
            crop_name = f"{base_path}/crop_00.png"
            metadata_name = f"{base_path}/metadata.json"
            if crop_name not in members or metadata_name not in members:
                raise ValueError(f"crop or metadata missing for {case_id}/{source}")
            used_paths.update({crop_name, metadata_name})
            crop = archive.read(members[crop_name])
            metadata_raw = archive.read(members[metadata_name])
            if not crop or len(crop) > MAX_SESSION_CROP_BYTES:
                raise ValueError(f"invalid crop size for {case_id}/{source}")
            crop_hash = _sha256_bytes(crop)
            if row.get("crop_sha256") != crop_hash:
                raise ValueError(f"crop hash mismatch for {case_id}/{source}")
            if row.get("metadata_sha256") != _sha256_bytes(metadata_raw):
                raise ValueError(f"metadata hash mismatch for {case_id}/{source}")
            metadata = _load_json(metadata_raw, f"metadata for {case_id}/{source}")
            if "payload" in metadata or "raw_payload" in metadata:
                raise ValueError(f"raw payload field found in {case_id}/{source}")
            expected = {
                "offline_capture_schema_version": OFFLINE_METADATA_SCHEMA_VERSION,
                "collector": COLLECTOR,
                "offline_session_id": session_id,
                "campaign_id": CAMPAIGN_ID,
                "campaign_case_id": case_id,
                "ground_truth": case.label,
                "paired_group_sha256": _sha256_text(case.pair_token),
                "physical_qr_sha256": _sha256_text(case.physical_qr_token),
                "image_source": source,
                "quality_condition": case.quality_condition,
                "quality_severity": case.quality_severity,
                "selected_frame_index": 0,
                "raw_payload_stored": False,
                "crop_sha256": crop_hash,
                "trusted_analysis_pending": True,
            }
            for key, value in expected.items():
                if metadata.get(key) != value:
                    raise ValueError(f"{case_id}/{source}: {key} mismatch")
            payload_hash = str(metadata.get("payload_sha256", ""))
            if not SHA256_PATTERN.fullmatch(payload_hash):
                raise ValueError(f"invalid payload SHA-256 for {case_id}/{source}")
            if metadata.get("payload_hash_source") != "on_device_mlkit_decode":
                raise ValueError(
                    f"untrusted payload-hash source for {case_id}/{source}"
                )
            try:
                captured_at = datetime.fromisoformat(str(metadata.get("captured_at")))
            except ValueError as exc:
                raise ValueError(
                    f"invalid capture timestamp for {case_id}/{source}"
                ) from exc
            if captured_at.tzinfo is None:
                raise ValueError(
                    f"capture timestamp lacks a timezone for {case_id}/{source}"
                )
            for key in ("device_model", "medium", "environment"):
                _validate_safe_value(metadata, key)
            if case.attack_provenance_required:
                if metadata.get("attack_method") not in ATTACK_METHODS:
                    raise ValueError(f"missing attack method for {case_id}/{source}")
                if not SHA256_PATTERN.fullmatch(
                    str(metadata.get("attack_reference_sha256", ""))
                ):
                    raise ValueError(
                        f"missing attack reference hash for {case_id}/{source}"
                    )
            elif metadata.get("attack_method") != "none":
                raise ValueError(f"unexpected attack method for {case_id}/{source}")
            if case.manipulation_provenance_required:
                if metadata.get("manipulation_method") not in MANIPULATION_METHODS:
                    raise ValueError(
                        f"missing manipulation method for {case_id}/{source}"
                    )
            elif metadata.get("manipulation_method") != "none":
                raise ValueError(
                    f"unexpected manipulation method for {case_id}/{source}"
                )

            try:
                image = Image.open(io.BytesIO(crop))
                image.load()
                if image.width < 24 or image.height < 24:
                    raise ValueError("crop is too small")
            except Exception as exc:
                raise ValueError(f"unreadable crop for {case_id}/{source}") from exc

            key = (case_id, source)
            if key in archive_keys:
                raise ValueError(f"duplicate archive session for {case_id}/{source}")
            if key in existing:
                raise ValueError(
                    f"canonical evidence already exists for {case_id}/{source}"
                )
            opposite = existing.get(
                (case_id, "camera" if source == "gallery" else "gallery")
            )
            if opposite and opposite.get("payload_sha256") != payload_hash:
                raise ValueError(
                    f"existing pair payload mismatch for {case_id}/{source}"
                )
            previous_payload = archive_payloads.setdefault(case_id, payload_hash)
            if previous_payload != payload_hash:
                raise ValueError(f"Gallery/Camera payload mismatch for {case_id}")
            provenance = (
                metadata.get("attack_method"),
                metadata.get("attack_reference_sha256"),
                metadata.get("manipulation_method"),
            )
            previous_provenance = archive_provenance.setdefault(case_id, provenance)
            if previous_provenance != provenance:
                raise ValueError(f"Gallery/Camera provenance mismatch for {case_id}")
            archive_keys.add(key)
            candidates.append(
                OfflineCandidate(
                    session_id=session_id,
                    case=case,
                    image_source=source,
                    captured_at=captured_at.astimezone(timezone.utc).isoformat(),
                    payload_sha256=payload_hash,
                    crop_sha256=crop_hash,
                    crop_png=crop,
                    metadata=metadata,
                )
            )

        unexpected = sorted(set(members) - used_paths)
        if unexpected:
            raise ValueError(f"unexpected ZIP members: {', '.join(unexpected[:3])}")
    return candidates


def _default_scan_runner(image: Image.Image, source: str):
    root = Path(__file__).resolve().parents[3]
    candidate_artifacts = (
        root
        / "ml_training"
        / "structural"
        / "runs"
        / "structural-2026.03-r01"
        / "artifacts"
    ).resolve()
    metadata_path = candidate_artifacts / "model_metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"Structural v3 candidate artifacts are missing: {candidate_artifacts}"
        )
    model_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if model_metadata.get("version") != "structural-2026.03-r01":
        raise ValueError("offline import candidate metadata has an unexpected version")
    configured = os.getenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "").strip()
    if configured and Path(configured).resolve() != candidate_artifacts:
        raise ValueError(
            "QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS points to a different model; "
            "offline campaign import refuses mixed-model evidence"
        )
    os.environ["QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS"] = str(candidate_artifacts)
    backend = root / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.pipeline import run_scan

    return run_scan(
        None,
        images=[image],
        image_source=source,
        image_expected=True,
    )


def _canonical_metadata(candidate: OfflineCandidate, result) -> dict[str, object]:
    branch = result.branch_scores
    if result.payload:
        decoded_hash = _sha256_text(result.payload)
        if decoded_hash != candidate.payload_sha256:
            raise ValueError(
                f"desktop decoder payload mismatch for {candidate.case.case_id}/"
                f"{candidate.image_source}"
            )
    with Image.open(io.BytesIO(candidate.crop_png)) as image:
        width, height = image.size
    source_metadata = candidate.metadata
    return {
        "captured_at": candidate.captured_at,
        "campaign_id": CAMPAIGN_ID,
        "campaign_case_id": candidate.case.case_id,
        "ground_truth": candidate.case.label,
        "payload_sha256": candidate.payload_sha256,
        "paired_group_sha256": _sha256_text(candidate.case.pair_token),
        "physical_qr_sha256": _sha256_text(candidate.case.physical_qr_token),
        "image_source": candidate.image_source,
        "quality_condition": candidate.case.quality_condition,
        "quality_severity": candidate.case.quality_severity,
        "selected_frame_index": 0,
        "device_model": source_metadata["device_model"],
        "medium": source_metadata["medium"],
        "environment": source_metadata["environment"],
        "attack_method": source_metadata["attack_method"],
        "attack_reference_sha256": source_metadata["attack_reference_sha256"],
        "manipulation_method": source_metadata["manipulation_method"],
        "image_sizes": [[width, height]],
        "p_structural_effective": branch.p_structural,
        "structural_type": branch.structural_type,
        "structural_quality_status": branch.structural_quality_status,
        "structural_quality_conditions": branch.structural_quality_conditions,
        "structural_rescan_reason": branch.structural_rescan_reason,
        "payload_type": result.payload_type,
        "rule_flags": result.rule_flags,
        "verdict": result.verdict,
        "risk_score": result.risk_score,
        "capture_transport": "offline_zip_v1",
        "offline_session_id": candidate.session_id,
        "offline_crop_sha256": candidate.crop_sha256,
        "payload_hash_source": source_metadata["payload_hash_source"],
        "desktop_payload_decode_verified": bool(result.payload),
    }


def import_candidates(
    candidates: list[OfflineCandidate],
    capture_root: Path,
    *,
    scan_runner: Callable[[Image.Image, str], object] = _default_scan_runner,
) -> list[Path]:
    prepared: list[tuple[OfflineCandidate, dict[str, object], Path]] = []
    for candidate in candidates:
        image = Image.open(io.BytesIO(candidate.crop_png)).convert("RGB")
        result = scan_runner(image, candidate.image_source)
        metadata = _canonical_metadata(candidate, result)
        stamp = datetime.fromisoformat(candidate.captured_at).strftime(
            "%Y%m%d_%H%M%S_%f"
        )
        session = (
            capture_root
            / candidate.case.label
            / f"scan_{stamp}_{candidate.session_id[:8]}"
        )
        if session.exists():
            raise FileExistsError(f"import destination already exists: {session}")
        prepared.append((candidate, metadata, session))

    written: list[Path] = []
    for candidate, metadata, session in prepared:
        session.mkdir(parents=True)
        (session / "crop_00.png").write_bytes(candidate.crop_png)
        (session / "metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        written.append(session)
    return written


def _write_receipt(
    capture_root: Path,
    archive_path: Path,
    candidates: list[OfflineCandidate],
    written: list[Path],
) -> Path:
    imported_at = datetime.now(timezone.utc)
    directory = capture_root / "offline_import_receipts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"import_{imported_at.strftime('%Y%m%d_%H%M%S')}.json"
    receipt = {
        "schema_version": 1,
        "imported_at": imported_at.isoformat(),
        "archive_filename": archive_path.name,
        "archive_sha256": _sha256_bytes(archive_path.read_bytes()),
        "session_count": len(written),
        "sessions": [
            {
                "offline_session_id": candidate.session_id,
                "case_id": candidate.case.case_id,
                "image_source": candidate.image_source,
                "destination": destination.relative_to(capture_root).as_posix(),
            }
            for candidate, destination in zip(candidates, written, strict=True)
        ],
        "source_archive_deleted": False,
    }
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    campaign_dir = root / "ml_training" / "structural" / "campaigns" / CAMPAIGN_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--schedule", type=Path, default=campaign_dir / "campaign.csv")
    parser.add_argument(
        "--capture-root", type=Path, default=root / "data" / "runtime_captures"
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Run local analysis and write canonical sessions after validation.",
    )
    args = parser.parse_args()

    candidates = validate_archive(args.archive, args.schedule, args.capture_root)
    print(f"validated {len(candidates)} offline sessions")
    for candidate in candidates:
        print(
            f"  {candidate.case.case_id:20} {candidate.image_source:7} "
            f"crop={candidate.crop_sha256[:12]}"
        )
    if not args.commit:
        print("validation only; rerun with --commit to import")
        return

    written = import_candidates(candidates, args.capture_root)
    receipt = _write_receipt(args.capture_root, args.archive, candidates, written)
    progress = audit_campaign(args.schedule, args.capture_root)
    print(f"imported {len(written)} sessions; receipt={receipt}")
    print(
        f"campaign pairs={progress.complete_pairs} "
        f"valid_sessions={progress.valid_planned_sessions} "
        f"errors={len(progress.errors)}"
    )


if __name__ == "__main__":
    main()
