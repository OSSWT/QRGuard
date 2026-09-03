"""Finalize audited Structural capture evidence into one recoverable master ZIP.

The master preserves the original round-one bundle and all round-two Android
exports byte-for-byte. It also contains a training-ready bundle whose inner
archives contain only reference-bound, provenance-matched sessions. Quarantined
sessions remain available for audit but never enter the training-ready batches.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml_training.structural.src.capture_campaign import CAMPAIGN_ID, load_cases
from ml_training.structural.src.import_offline_capture import (
    ARCHIVE_SCHEMA_VERSION,
    COLLECTOR,
    MAX_SESSIONS,
    validate_archive,
)

EXPORT_PATTERN = "QRGuard_Offline_structural_v3_real_2026_03_r01_*.zip"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def _selection(path: Path) -> dict[str, dict[str, object]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("campaign_id") != CAMPAIGN_ID:
        raise ValueError(f"selection campaign mismatch: {path}")
    return {str(item["case_id"]): item for item in value["selected_cases"]}


def _reference_payloads(
    reference_root: Path, case_ids: set[str]
) -> dict[str, str]:
    result: dict[str, str] = {}
    for case_id in sorted(case_ids):
        path = reference_root / case_id / f"{case_id}-reference.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        value = str(metadata["payload_sha256"])
        if len(value) != 64:
            raise ValueError(f"invalid reference payload hash for {case_id}")
        result[case_id] = value
    return result


def _expected_provenance(item: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(item.get("default_attack_method", "none")),
        str(item.get("default_attack_reference_sha256", "")),
        str(item.get("default_manipulation_method", "none")),
    )


def _actual_provenance(metadata: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(metadata.get("attack_method", "none")),
        str(metadata.get("attack_reference_sha256", "")),
        str(metadata.get("manipulation_method", "none")),
    )


def _inspect_batch(
    data: bytes,
    *,
    expected_payloads: dict[str, str],
    selections: dict[str, dict[str, object]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"corrupt inner archive member: {bad}")
        manifest_raw = archive.read("archive_manifest.json")
        manifest = json.loads(manifest_raw)
        sessions = manifest.get("sessions")
        if manifest.get("offline_capture_archive_schema_version") != 1:
            raise ValueError("unexpected inner archive schema")
        if manifest.get("collector") != COLLECTOR:
            raise ValueError("unexpected inner archive collector")
        if manifest.get("campaign_id") != CAMPAIGN_ID:
            raise ValueError("unexpected inner archive campaign")
        if not isinstance(sessions, list) or not 1 <= len(sessions) <= MAX_SESSIONS:
            raise ValueError("invalid inner archive session count")
        if manifest.get("session_count") != len(sessions):
            raise ValueError("inner archive manifest count mismatch")
        records: list[dict[str, object]] = []
        for row in sessions:
            case_id = str(row["case_id"])
            source = str(row["image_source"])
            base = str(row["base_path"])
            metadata_raw = archive.read(f"{base}/metadata.json")
            crop = archive.read(f"{base}/crop_00.png")
            if _sha256_bytes(metadata_raw) != row["metadata_sha256"]:
                raise ValueError(f"metadata hash mismatch for {case_id}/{source}")
            if _sha256_bytes(crop) != row["crop_sha256"]:
                raise ValueError(f"crop hash mismatch for {case_id}/{source}")
            metadata = json.loads(metadata_raw)
            if metadata.get("payload_sha256") != expected_payloads.get(case_id):
                raise ValueError(f"reference binding mismatch for {case_id}/{source}")
            if case_id not in selections:
                raise ValueError(f"case missing from selected scopes: {case_id}")
            if _actual_provenance(metadata) != _expected_provenance(
                selections[case_id]
            ):
                raise ValueError(f"provenance mismatch for {case_id}/{source}")
            records.append(
                {
                    "offline_session_id": str(row["offline_session_id"]),
                    "case_id": case_id,
                    "image_source": source,
                    "payload_sha256": str(metadata["payload_sha256"]),
                    "crop_sha256": str(row["crop_sha256"]),
                    "metadata_sha256": str(row["metadata_sha256"]),
                }
            )
    return manifest, records


def _read_source_members(archive_path: Path, candidate) -> tuple[bytes, bytes]:
    base = (
        f"sessions/{candidate.case.case_id}/{candidate.image_source}/"
        f"{candidate.session_id}"
    )
    with zipfile.ZipFile(archive_path) as archive:
        return (
            archive.read(f"{base}/metadata.json"),
            archive.read(f"{base}/crop_00.png"),
        )


def _curated_batch_bytes(
    rows: list[tuple[Path, object]], *, exported_at: str
) -> bytes:
    manifest_rows: list[dict[str, object]] = []
    members: list[tuple[str, bytes, bytes]] = []
    for archive_path, candidate in rows:
        metadata_raw, crop = _read_source_members(archive_path, candidate)
        base = (
            f"sessions/{candidate.case.case_id}/{candidate.image_source}/"
            f"{candidate.session_id}"
        )
        manifest_rows.append(
            {
                "offline_session_id": candidate.session_id,
                "case_id": candidate.case.case_id,
                "image_source": candidate.image_source,
                "base_path": base,
                "crop_sha256": _sha256_bytes(crop),
                "metadata_sha256": _sha256_bytes(metadata_raw),
            }
        )
        members.append((base, metadata_raw, crop))
    manifest = {
        "offline_capture_archive_schema_version": ARCHIVE_SCHEMA_VERSION,
        "collector": COLLECTOR,
        "campaign_id": CAMPAIGN_ID,
        "exported_at": exported_at,
        "session_count": len(manifest_rows),
        "raw_payload_stored": False,
        "curation": {
            "type": "reference_bound_exact_session_subset",
            "metadata_and_crop_members_rewritten": False,
            "source_archives_preserved_in_master": True,
        },
        "sessions": manifest_rows,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("archive_manifest.json", _json_bytes(manifest))
        for base, metadata_raw, crop in members:
            archive.writestr(f"{base}/metadata.json", metadata_raw)
            archive.writestr(f"{base}/crop_00.png", crop)
    return output.getvalue()


def _outer_bundle_bytes(
    *,
    manifest_name: str,
    manifest: dict[str, object],
    readme: str,
    members: list[tuple[str, bytes]],
    extra_json: list[tuple[str, dict[str, object]]] | None = None,
    extra_files: list[tuple[str, bytes]] | None = None,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            manifest_name, _json_bytes(manifest), compress_type=zipfile.ZIP_DEFLATED
        )
        archive.writestr(
            "README_FIRST.md", readme.encode(), compress_type=zipfile.ZIP_DEFLATED
        )
        for name, value in extra_json or []:
            archive.writestr(
                name, _json_bytes(value), compress_type=zipfile.ZIP_DEFLATED
            )
        for name, value in extra_files or []:
            archive.writestr(name, value, compress_type=zipfile.ZIP_DEFLATED)
        for name, value in members:
            archive.writestr(name, value, compress_type=zipfile.ZIP_STORED)
    return output.getvalue()


def finalize(
    *,
    first_bundle: Path,
    first_selection_path: Path,
    addon_selection_path: Path,
    repair_selection_path: Path,
    addon_export_dir: Path,
    repair_export_dir: Path,
    source_audit_path: Path,
    schedule: Path,
    capture_root: Path,
    reference_root: Path,
    output_dir: Path,
    master_output: Path,
) -> dict[str, object]:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite output directory: {output_dir}")
    if master_output.exists():
        raise FileExistsError(f"refusing to overwrite master ZIP: {master_output}")
    output_dir.mkdir(parents=True)

    first_selection = _selection(first_selection_path)
    addon_selection = _selection(addon_selection_path)
    repair_selection = _selection(repair_selection_path)
    all_selection = {**first_selection, **addon_selection}
    if len(all_selection) != len(first_selection) + len(addon_selection):
        raise ValueError("round selections overlap")
    expected_payloads = _reference_payloads(reference_root, set(all_selection))
    cases = {case.case_id: case for case in load_cases(schedule)}

    first_batches: list[tuple[str, bytes]] = []
    first_records: list[dict[str, object]] = []
    with zipfile.ZipFile(first_bundle) as outer:
        first_manifest = json.loads(outer.read("bundle_manifest.json"))
        for position, row in enumerate(first_manifest["archives"], start=1):
            data = outer.read(str(row["bundle_member"]))
            if _sha256_bytes(data) != row["sha256"]:
                raise ValueError("round-one inner archive hash mismatch")
            _, records = _inspect_batch(
                data,
                expected_payloads=expected_payloads,
                selections=all_selection,
            )
            first_records.extend(records)
            first_batches.append((f"batches/{position:02d}_{row['filename']}", data))
    if len(first_records) != 177:
        raise ValueError(f"expected 177 round-one exports, found {len(first_records)}")

    addon_archives = sorted(addon_export_dir.glob(EXPORT_PATTERN))
    repair_archives = sorted(repair_export_dir.glob(EXPORT_PATTERN))
    if len(addon_archives) != 6 or len(repair_archives) != 3:
        raise ValueError("expected six add-on source exports and three repair exports")

    accepted_addon: dict[tuple[str, str], tuple[Path, object]] = {}
    quarantined: list[dict[str, object]] = []
    raw_addon_rows: list[dict[str, object]] = []
    for archive_path in addon_archives:
        candidates = validate_archive(archive_path, schedule, capture_root)
        raw_addon_rows.append(
            {
                "filename": archive_path.name,
                "sha256": _sha256_file(archive_path),
                "bytes": archive_path.stat().st_size,
                "session_count": len(candidates),
            }
        )
        for candidate in candidates:
            case_id = candidate.case.case_id
            selection_item = addon_selection[case_id]
            exact = (
                candidate.payload_sha256 == expected_payloads[case_id]
                and _actual_provenance(candidate.metadata)
                == _expected_provenance(selection_item)
            )
            key = (case_id, candidate.image_source)
            if exact:
                if key in accepted_addon:
                    raise ValueError(f"multiple exact add-on sessions for {key}")
                accepted_addon[key] = (archive_path, candidate)
            else:
                quarantined.append(
                    {
                        "archive": archive_path.name,
                        "offline_session_id": candidate.session_id,
                        "case_id": case_id,
                        "image_source": candidate.image_source,
                        "payload_sha256": candidate.payload_sha256,
                        "expected_payload_sha256": expected_payloads[case_id],
                        "crop_sha256": candidate.crop_sha256,
                        "reason": "reference_or_provenance_mismatch",
                    }
                )
    if len(accepted_addon) != 61 or len(quarantined) != 143:
        raise ValueError(
            f"unexpected add-on audit counts: {len(accepted_addon)}/{len(quarantined)}"
        )

    repair_records: list[dict[str, object]] = []
    raw_repair_rows: list[dict[str, object]] = []
    repair_batch_bytes: list[tuple[str, bytes]] = []
    for archive_path in repair_archives:
        candidates = validate_archive(archive_path, schedule, capture_root)
        data = archive_path.read_bytes()
        raw_repair_rows.append(
            {
                "filename": archive_path.name,
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
                "session_count": len(candidates),
            }
        )
        for candidate in candidates:
            case_id = candidate.case.case_id
            item = repair_selection.get(case_id)
            if item is None:
                raise ValueError(f"repair export contains unexpected case: {case_id}")
            if candidate.image_source != "camera":
                raise ValueError("repair export contains a non-Camera source")
            if candidate.payload_sha256 != expected_payloads[case_id]:
                raise ValueError(f"repair reference mismatch for {case_id}")
            if _actual_provenance(candidate.metadata) != _expected_provenance(item):
                raise ValueError(f"repair provenance mismatch for {case_id}")
        _, records = _inspect_batch(
            data,
            expected_payloads=expected_payloads,
            selections=all_selection,
        )
        repair_records.extend(records)
        repair_batch_bytes.append((archive_path.name, data))
    if len(repair_records) != 119:
        raise ValueError(f"expected 119 repair sessions, found {len(repair_records)}")

    source_audit = json.loads(source_audit_path.read_text(encoding="utf-8"))
    round2_audit_manifest = {
        "schema_version": 1,
        "bundle_type": "qrguard_round2_raw_audited_evidence",
        "campaign_id": CAMPAIGN_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_payload_stored": False,
        "original_exports_preserved_byte_for_byte": True,
        "raw_export_count": 9,
        "raw_session_count": 323,
        "accepted_session_count": 180,
        "accepted_original_session_count": 61,
        "accepted_repair_session_count": 119,
        "quarantined_session_count": 143,
        "direct_import_supported": False,
        "addon_exports": raw_addon_rows,
        "repair_exports": raw_repair_rows,
        "quarantined_sessions": quarantined,
    }
    round2_raw_members = [
        (f"raw_addon_exports/{position:02d}_{path.name}", path.read_bytes())
        for position, path in enumerate(addon_archives, start=1)
    ] + [
        (f"repair_exports/{position:02d}_{path.name}", path.read_bytes())
        for position, path in enumerate(repair_archives, start=1)
    ]
    round2_audit_bytes = _outer_bundle_bytes(
        manifest_name="round2_audit_manifest.json",
        manifest=round2_audit_manifest,
        readme=(
            "# Round-two raw audited evidence\n\n"
            "All nine Android exports are preserved byte-for-byte. The 143 "
            "reference-mismatched sessions are quarantined and must not be "
            "used for training. Use the training-ready bundle in the master.\n"
        ),
        members=round2_raw_members,
        extra_json=[("SOURCE_EXPORT_AUDIT.json", source_audit)],
    )

    accepted_rows = sorted(
        accepted_addon.values(),
        key=lambda value: (
            int(addon_selection[value[1].case.case_id].get("capture_number", 0)),
            0 if value[1].image_source == "camera" else 1,
        ),
    )
    curated_batches: list[tuple[str, bytes]] = []
    now = datetime.now(timezone.utc).isoformat()
    chunks = [
        accepted_rows[index : index + MAX_SESSIONS]
        for index in range(0, len(accepted_rows), MAX_SESSIONS)
    ]
    for position, chunk in enumerate(chunks, start=1):
        name = (
            "QRGuard_Offline_structural_v3_real_2026_03_r01_"
            f"curated_original_valid_{position:02d}.zip"
        )
        data = _curated_batch_bytes(chunk, exported_at=now)
        _, records = _inspect_batch(
            data,
            expected_payloads=expected_payloads,
            selections=all_selection,
        )
        if len(records) != len(chunk):
            raise ValueError("curated batch validation count mismatch")
        curated_batches.append((name, data))

    round2_batches = curated_batches + repair_batch_bytes
    all_batches = first_batches + [
        (f"batches/{len(first_batches) + index:02d}_{name}", data)
        for index, (name, data) in enumerate(round2_batches, start=1)
    ]
    all_records = list(first_records)
    for _, data in round2_batches:
        _, records = _inspect_batch(
            data,
            expected_payloads=expected_payloads,
            selections=all_selection,
        )
        all_records.extend(records)
    if len(all_records) != 357:
        raise ValueError(f"expected 357 exported valid sessions, found {len(all_records)}")
    session_ids = [str(row["offline_session_id"]) for row in all_records]
    exported_keys = [
        (str(row["case_id"]), str(row["image_source"])) for row in all_records
    ]
    if len(session_ids) != len(set(session_ids)):
        raise ValueError("training-ready sessions contain duplicate IDs")
    if len(exported_keys) != len(set(exported_keys)):
        raise ValueError("training-ready sessions contain duplicate case/source keys")

    canonical_rows: list[dict[str, object]] = []
    canonical_files: list[tuple[str, bytes]] = []
    for metadata_path in sorted(capture_root.glob("*/*/metadata.json")):
        metadata_raw = metadata_path.read_bytes()
        metadata = json.loads(metadata_raw)
        case_id = str(metadata.get("campaign_case_id", ""))
        source = str(metadata.get("image_source", ""))
        if case_id not in first_selection or source not in {"camera", "gallery"}:
            continue
        crop_path = metadata_path.with_name("crop_00.png")
        crop = crop_path.read_bytes()
        if metadata.get("payload_sha256") != expected_payloads[case_id]:
            raise ValueError(f"canonical reference mismatch for {case_id}/{source}")
        relative_dir = metadata_path.parent.relative_to(capture_root).as_posix()
        canonical_rows.append(
            {
                "case_id": case_id,
                "image_source": source,
                "assigned_split": first_selection[case_id]["assigned_split"],
                "relative_directory": relative_dir,
                "metadata_sha256": _sha256_bytes(metadata_raw),
                "crop_sha256": _sha256_bytes(crop),
                "payload_sha256": str(metadata["payload_sha256"]),
            }
        )
        canonical_files.extend(
            [
                (f"canonical_existing/{relative_dir}/metadata.json", metadata_raw),
                (f"canonical_existing/{relative_dir}/crop_00.png", crop),
            ]
        )
    if len(canonical_rows) != 4:
        raise ValueError(f"expected four canonical sessions, found {len(canonical_rows)}")
    canonical_keys = [
        (str(row["case_id"]), str(row["image_source"])) for row in canonical_rows
    ]
    if set(canonical_keys) & set(exported_keys):
        raise ValueError("canonical sessions overlap exported sessions")

    effective_keys = set(exported_keys) | set(canonical_keys)
    sources_by_case: defaultdict[str, set[str]] = defaultdict(set)
    for case_id, source in effective_keys:
        sources_by_case[case_id].add(source)
    label_source_counts = Counter(
        (cases[case_id].label, source) for case_id, source in effective_keys
    )
    split_camera_counts = Counter(
        (all_selection[case_id]["label"], all_selection[case_id]["assigned_split"])
        for case_id, source in effective_keys
        if source == "camera"
    )
    condition_camera_counts = Counter(
        (cases[case_id].label, cases[case_id].quality_condition)
        for case_id, source in effective_keys
        if source == "camera"
    )
    paired_test_counts = Counter(
        all_selection[case_id]["label"]
        for case_id, sources in sources_by_case.items()
        if all_selection[case_id]["assigned_split"] == "test"
        and sources == {"camera", "gallery"}
    )
    camera_case_counts = Counter(
        cases[case_id].label
        for case_id, source in effective_keys
        if source == "camera"
    )
    if dict(camera_case_counts) != {
        "clean": 100,
        "adversarial": 100,
        "tampered": 100,
    }:
        raise ValueError(f"camera gate count mismatch: {dict(camera_case_counts)}")
    if dict(paired_test_counts) != {
        "clean": 20,
        "adversarial": 20,
        "tampered": 20,
    }:
        raise ValueError(f"paired Test gate mismatch: {dict(paired_test_counts)}")
    if len(condition_camera_counts) != 30 or any(
        count != 10 for count in condition_camera_counts.values()
    ):
        raise ValueError("quality-condition Camera count is not uniformly ten")

    batch_rows: list[dict[str, object]] = []
    for name, data in all_batches:
        manifest, records = _inspect_batch(
            data,
            expected_payloads=expected_payloads,
            selections=all_selection,
        )
        batch_rows.append(
            {
                "bundle_member": name,
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
                "session_count": len(records),
                "source_exported_at": manifest.get("exported_at"),
            }
        )
    canonical_manifest = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "session_count": len(canonical_rows),
        "sessions": canonical_rows,
    }
    training_manifest = {
        "schema_version": 1,
        "bundle_type": "qrguard_structural_training_ready_100x3",
        "campaign_id": CAMPAIGN_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_payload_stored": False,
        "direct_import_supported": False,
        "direct_import_reason": (
            "Extract and import each inner batch; the strict importer accepts "
            f"at most {MAX_SESSIONS} sessions per input ZIP."
        ),
        "inner_archive_count": len(batch_rows),
        "exported_valid_session_count": len(all_records),
        "canonical_existing_session_count": len(canonical_rows),
        "effective_session_count": len(effective_keys),
        "distinct_camera_cases": len(
            {case_id for case_id, source in effective_keys if source == "camera"}
        ),
        "quarantined_sessions_included": False,
        "counts": {
            "label_source": {
                f"{label}/{source}": count
                for (label, source), count in sorted(label_source_counts.items())
            },
            "camera_split": {
                f"{label}/{split}": count
                for (label, split), count in sorted(split_camera_counts.items())
            },
            "camera_condition": {
                f"{label}/{condition}": count
                for (label, condition), count in sorted(
                    condition_camera_counts.items()
                )
            },
            "paired_test_per_label": dict(sorted(paired_test_counts.items())),
        },
        "deployment_count_gate": {
            "camera_per_label_at_least_100": True,
            "paired_test_per_label_at_least_20": True,
            "camera_per_condition_per_label_at_least_5": True,
            "count_gate_passed": True,
            "performance_gate_pending_training_evaluation": True,
        },
        "batches": batch_rows,
        "canonical_existing_manifest": "canonical_existing_manifest.json",
    }
    training_ready_bytes = _outer_bundle_bytes(
        manifest_name="bundle_manifest.json",
        manifest=training_manifest,
        readme=(
            "# QRGuard Structural 100 x 3 training-ready bundle\n\n"
            "This bundle contains 13 validated inner import ZIPs and four "
            "already-canonical sessions. Extract the bundle, retain the four "
            "canonical sessions in `data/runtime_captures`, then import the "
            "inner ZIPs in manifest order. Quarantined sessions are excluded.\n"
        ),
        members=all_batches,
        extra_json=[("canonical_existing_manifest.json", canonical_manifest)],
        extra_files=canonical_files,
    )

    master_components = [
        (
            "source_evidence/round1_original_bundle.zip",
            first_bundle.read_bytes(),
        ),
        (
            "source_evidence/round2_raw_audited_bundle.zip",
            round2_audit_bytes,
        ),
        (
            "training_ready/QRGuard_Training_Ready_100x3.zip",
            training_ready_bytes,
        ),
    ]
    master_manifest = {
        "schema_version": 1,
        "bundle_type": "qrguard_structural_100x3_master_audited",
        "campaign_id": CAMPAIGN_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_payload_stored": False,
        "single_file_master": True,
        "source_android_export_count": 17,
        "source_android_session_count": 500,
        "accepted_effective_session_count": len(effective_keys),
        "accepted_camera_cases": 300,
        "accepted_paired_test_cases": 60,
        "quarantined_session_count": len(quarantined),
        "training_ready_member": "training_ready/QRGuard_Training_Ready_100x3.zip",
        "deployment_count_gate_passed": True,
        "performance_gate_pending_training_evaluation": True,
        "components": [
            {
                "member": name,
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
            }
            for name, data in master_components
        ],
    }
    master_readme = (
        "# QRGuard Structural 100 x 3 Master\n\n"
        "This is the single retained master evidence file. It preserves the "
        "original round-one bundle and all round-two raw exports for audit, "
        "including quarantined records. For training, extract only "
        "`training_ready/QRGuard_Training_Ready_100x3.zip` and follow its "
        "manifest. The count gate passes; performance evaluation is still "
        "required after training.\n"
    )
    master_bytes = _outer_bundle_bytes(
        manifest_name="master_manifest.json",
        manifest=master_manifest,
        readme=master_readme,
        members=master_components,
    )
    master_output.parent.mkdir(parents=True, exist_ok=True)
    master_output.write_bytes(master_bytes)
    (output_dir / "FINAL_DATASET_MANIFEST.json").write_text(
        json.dumps(master_manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "TRAINING_READY_MANIFEST.json").write_text(
        json.dumps(training_manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "README_中文.txt").write_text(
        "QRGuard Structural 100 x 3 最终数据集\n\n"
        "保留文件：QRGuard_Structural_100x3_Master_Audited_20260830.zip\n"
        "有效 Camera：Clean 100、Adversarial 100、Tampered 100。\n"
        "Test 配对：每类 20。每类每种画质条件 Camera 10。\n"
        "143 个错位 sessions 仅保留在审计来源中，不进入 training-ready。\n"
        "数量 gate 已通过；模型性能 gate 必须等训练和评估后确认。\n",
        encoding="utf-8",
    )
    return {
        "master_sha256": _sha256_bytes(master_bytes),
        "master_bytes": len(master_bytes),
        "master_manifest": master_manifest,
        "training_manifest": training_manifest,
    }


def main() -> None:
    campaign = ROOT / "ml_training" / "structural" / "campaigns" / CAMPAIGN_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-bundle", type=Path, required=True)
    parser.add_argument("--addon-export-dir", type=Path, required=True)
    parser.add_argument("--repair-export-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--master-output", type=Path, required=True)
    parser.add_argument(
        "--first-selection",
        type=Path,
        default=campaign / "scope_50x3_selection.json",
    )
    parser.add_argument(
        "--addon-selection",
        type=Path,
        default=campaign / "deployment_addon_50x3_selection.json",
    )
    parser.add_argument(
        "--repair-selection",
        type=Path,
        default=campaign / "deployment_addon_repair_119_selection.json",
    )
    parser.add_argument(
        "--source-audit",
        type=Path,
        default=campaign / "deployment_addon_repair_source_audit.json",
    )
    parser.add_argument("--schedule", type=Path, default=campaign / "campaign.csv")
    parser.add_argument(
        "--capture-root", type=Path, default=ROOT / "data" / "runtime_captures"
    )
    parser.add_argument(
        "--reference-root",
        type=Path,
        default=ROOT / "data" / "capture_pilot" / CAMPAIGN_ID,
    )
    args = parser.parse_args()
    result = finalize(
        first_bundle=args.first_bundle,
        first_selection_path=args.first_selection,
        addon_selection_path=args.addon_selection,
        repair_selection_path=args.repair_selection,
        addon_export_dir=args.addon_export_dir,
        repair_export_dir=args.repair_export_dir,
        source_audit_path=args.source_audit,
        schedule=args.schedule,
        capture_root=args.capture_root,
        reference_root=args.reference_root,
        output_dir=args.output_dir,
        master_output=args.master_output,
    )
    print(
        f"master={args.master_output}; bytes={result['master_bytes']}; "
        f"sha256={result['master_sha256']}"
    )


if __name__ == "__main__":
    main()
