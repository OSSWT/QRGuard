from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import qrcode
from PIL import Image

from ml_training.structural.src.capture_campaign import (
    audit_campaign,
    load_cases,
    write_campaign,
)
from ml_training.structural.src.import_offline_capture import (
    COLLECTOR,
    _default_scan_runner,
    import_candidates,
    validate_archive,
)
from scripts.build_offline_capture_plan import build_plan


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _qr_png(payload: str) -> bytes:
    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    output = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").convert("RGB").save(
        output, "PNG"
    )
    return output.getvalue()


def _write_offline_archive(
    path: Path,
    schedule: Path,
    *,
    corrupt_crop_hash: bool = False,
) -> tuple[str, str]:
    case = load_cases(schedule)[0]
    payload = "https://example.com/?offline-test=1"
    crop = _qr_png(payload)
    session_id = "a" * 32
    source = "gallery"
    base = f"sessions/{case.case_id}/{source}/{session_id}"
    metadata = {
        "offline_capture_schema_version": 1,
        "collector": COLLECTOR,
        "offline_session_id": session_id,
        "captured_at": "2026-08-30T09:00:00.000Z",
        "campaign_id": case.campaign_id,
        "campaign_case_id": case.case_id,
        "ground_truth": case.label,
        "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "payload_hash_source": "on_device_mlkit_decode",
        "raw_payload_stored": False,
        "paired_group_sha256": hashlib.sha256(case.pair_token.encode()).hexdigest(),
        "physical_qr_sha256": hashlib.sha256(
            case.physical_qr_token.encode()
        ).hexdigest(),
        "image_source": source,
        "quality_condition": case.quality_condition,
        "quality_severity": case.quality_severity,
        "selected_frame_index": 0,
        "device_model": "xiaomi-10t-pro",
        "medium": "printed-paper",
        "environment": "indoor-controlled",
        "attack_method": "none",
        "attack_reference_sha256": "",
        "manipulation_method": "none",
        "image_sizes": [[328, 328]],
        "crop_sha256": _sha256(crop),
        "trusted_analysis_pending": True,
    }
    metadata_raw = json.dumps(metadata, indent=2).encode()
    manifest = {
        "offline_capture_archive_schema_version": 1,
        "collector": COLLECTOR,
        "campaign_id": case.campaign_id,
        "exported_at": "2026-08-30T09:01:00.000Z",
        "session_count": 1,
        "raw_payload_stored": False,
        "sessions": [
            {
                "offline_session_id": session_id,
                "case_id": case.case_id,
                "image_source": source,
                "base_path": base,
                "crop_sha256": "0" * 64 if corrupt_crop_hash else _sha256(crop),
                "metadata_sha256": _sha256(metadata_raw),
            }
        ],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("archive_manifest.json", json.dumps(manifest))
        archive.writestr(f"{base}/crop_00.png", crop)
        archive.writestr(f"{base}/metadata.json", metadata_raw)
    return case.case_id, payload


def test_offline_plan_marks_existing_sources_and_keeps_payloads_out(tmp_path):
    campaign = tmp_path / "campaign"
    write_campaign(campaign)
    case = load_cases(campaign / "campaign.csv")[0]
    captures = tmp_path / "captures"
    session = captures / case.label / "scan_existing"
    session.mkdir(parents=True)
    (session / "metadata.json").write_text(
        json.dumps(
            {
                "campaign_id": case.campaign_id,
                "campaign_case_id": case.case_id,
                "ground_truth": case.label,
                "quality_condition": case.quality_condition,
                "quality_severity": case.quality_severity,
                "paired_group_sha256": hashlib.sha256(
                    case.pair_token.encode()
                ).hexdigest(),
                "physical_qr_sha256": hashlib.sha256(
                    case.physical_qr_token.encode()
                ).hexdigest(),
                "payload_sha256": "1" * 64,
                "image_source": "gallery",
            }
        ),
        encoding="utf-8",
    )

    plan = build_plan(campaign / "campaign.csv", captures)

    assert len(plan["cases"]) == 450
    first = plan["cases"][0]
    assert first["completed_sources"] == ["gallery"]
    encoded = json.dumps(plan)
    assert "pair_token" not in encoded
    assert "physical_qr_token" not in encoded
    assert "https://" not in encoded


def test_offline_plan_filters_scope_and_bundles_prepared_provenance(tmp_path):
    campaign = tmp_path / "campaign"
    write_campaign(campaign)
    cases = load_cases(campaign / "campaign.csv")
    selected = {
        case.label: case
        for case in cases
        if case.quality_condition == "normal" and case.condition_ordinal == 1
    }
    selected_ids = {case.case_id for case in selected.values()}
    attack_hash = "a" * 64
    metadata = {
        selected["adversarial"].case_id: {
            "default_attack_method": "eot_fgsm",
            "default_attack_reference_sha256": attack_hash,
            "expected_payload_sha256": "b" * 64,
        },
        selected["tampered"].case_id: {
            "default_manipulation_method": "sticker_overlay",
            "assigned_split": "test",
        },
    }

    plan = build_plan(
        campaign / "campaign.csv",
        tmp_path / "captures",
        selected_case_ids=selected_ids,
        selected_case_metadata=metadata,
    )

    assert len(plan["cases"]) == 3
    by_id = {item["case_id"]: item for item in plan["cases"]}
    adversarial = by_id[selected["adversarial"].case_id]
    tampered = by_id[selected["tampered"].case_id]
    assert adversarial["default_attack_method"] == "eot_fgsm"
    assert adversarial["default_attack_reference_sha256"] == attack_hash
    assert adversarial["expected_payload_sha256"] == "b" * 64
    assert adversarial["gallery_required_for_test"] is False
    assert tampered["default_manipulation_method"] == "sticker_overlay"
    assert tampered["gallery_required_for_test"] is True


def test_offline_archive_validates_imports_and_audits(tmp_path):
    campaign = tmp_path / "campaign"
    write_campaign(campaign)
    archive = tmp_path / "capture.zip"
    case_id, payload = _write_offline_archive(archive, campaign / "campaign.csv")
    captures = tmp_path / "captures"

    candidates = validate_archive(archive, campaign / "campaign.csv", captures)

    def fake_scan(_image, source):
        return SimpleNamespace(
            payload=payload,
            payload_type="url",
            rule_flags=[],
            verdict="safe",
            risk_score=2,
            branch_scores=SimpleNamespace(
                p_structural=0.02,
                structural_type="clean",
                structural_quality_status="usable",
                structural_quality_conditions=[],
                structural_rescan_reason=None,
            ),
        )

    written = import_candidates(candidates, captures, scan_runner=fake_scan)
    progress = audit_campaign(campaign / "campaign.csv", captures)

    assert len(written) == 1
    metadata = json.loads((written[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["campaign_case_id"] == case_id
    assert metadata["capture_transport"] == "offline_zip_v1"
    assert metadata["desktop_payload_decode_verified"] is True
    assert "payload" not in metadata
    assert progress.valid_planned_sessions == 1
    assert progress.errors == []


def test_offline_archive_rejects_crop_hash_mismatch(tmp_path):
    campaign = tmp_path / "campaign"
    write_campaign(campaign)
    archive = tmp_path / "capture.zip"
    _write_offline_archive(
        archive,
        campaign / "campaign.csv",
        corrupt_crop_hash=True,
    )

    try:
        validate_archive(archive, campaign / "campaign.csv", tmp_path / "captures")
    except ValueError as error:
        assert "crop hash mismatch" in str(error)
    else:
        raise AssertionError("corrupt crop hash was accepted")


def test_offline_import_refuses_a_different_configured_model(monkeypatch, tmp_path):
    monkeypatch.setenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", str(tmp_path))
    image = Image.open(io.BytesIO(_qr_png("https://example.com/?model-guard=1")))

    with pytest.raises(ValueError, match="different model"):
        _default_scan_runner(image, "gallery")
