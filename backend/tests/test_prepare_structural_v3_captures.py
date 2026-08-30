import json
from csv import DictWriter

from PIL import Image

from ml_training.structural.src import structural_recipes
from ml_training.structural.src.prepare_structural_v3_captures import (
    audit_rows,
    discover,
)


def _session(
    root,
    label,
    name,
    payload_hash,
    *,
    source="camera",
    pair_hash=None,
    condition="normal",
    frames=1,
):
    session = root / label / name
    session.mkdir(parents=True)
    metadata = {
        "ground_truth": label,
        "payload_sha256": payload_hash,
        "paired_group_sha256": pair_hash or payload_hash,
        "physical_qr_sha256": pair_hash or payload_hash,
        "image_source": source,
        "quality_condition": condition,
        "quality_severity": "none" if condition == "normal" else "mild",
        "selected_frame_index": 0,
    }
    (session / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    for index in range(frames):
        image = Image.new("RGB", (80, 80), "white")
        image.putpixel((index, 0), (250 - index, 250 - index, 250 - index))
        image.save(session / f"crop_{index:02d}.png")


def test_one_authoritative_crop_is_valid_for_current_app_contract(tmp_path):
    _session(tmp_path, "clean", "scan_camera", "a" * 64)

    rows, rejected = discover(tmp_path)

    assert not rejected
    assert len(rows) == 1
    assert rows[0].is_authoritative is True
    assert rows[0].image_source == "camera"


def test_gallery_and_camera_pair_is_counted_without_double_counting_sessions(tmp_path):
    pair = "b" * 64
    payload = "c" * 64
    _session(
        tmp_path, "tampered", "scan_gallery", payload, source="gallery", pair_hash=pair
    )
    _session(
        tmp_path, "tampered", "scan_camera", payload, source="camera", pair_hash=pair
    )

    rows, rejected = discover(tmp_path)
    audit = audit_rows(rows, rejected, 0, 0, 0)

    assert audit.accepted_sessions == 2
    assert audit.camera_sessions_per_class["tampered"] == 1
    assert audit.gallery_sessions_per_class["tampered"] == 1
    assert audit.paired_groups_per_class["tampered"] == 1
    assert len({row.split for row in rows}) == 1


def test_invalid_quality_condition_is_rejected(tmp_path):
    _session(
        tmp_path,
        "clean",
        "scan_invalid",
        "d" * 64,
        condition="malicious_exposure",
    )

    rows, rejected = discover(tmp_path)

    assert rows == []
    assert rejected["invalid_quality_condition"] == 1


def test_strict_audit_requires_real_camera_and_paired_test_evidence(tmp_path):
    rows, rejected = discover(tmp_path)
    audit = audit_rows(rows, rejected)

    assert audit.strict_ready is False
    assert any("camera sessions" in failure for failure in audit.strict_failures)
    assert any("paired test groups" in failure for failure in audit.strict_failures)


def test_audit_rejects_duplicate_authoritative_source_within_pair(tmp_path):
    pair = "e" * 64
    payload = "f" * 64
    _session(tmp_path, "clean", "scan_camera_1", payload, pair_hash=pair)
    _session(tmp_path, "clean", "scan_camera_2", payload, pair_hash=pair)

    rows, rejected = discover(tmp_path)
    audit = audit_rows(rows, rejected, 0, 0, 0)

    assert audit.strict_ready is False
    assert any(
        "multiple authoritative rows" in failure for failure in audit.strict_failures
    )


def test_v3_training_rows_use_authoritative_nonsevere_captures_only(
    tmp_path, monkeypatch
):
    capture_root = tmp_path / "data" / "runtime_captures"
    capture_root.mkdir(parents=True)
    Image.new("RGB", (80, 80), "white").save(capture_root / "usable.png")
    Image.new("RGB", (80, 80), "white").save(capture_root / "severe.png")
    rows = [
        {
            "sample_path": "usable.png",
            "label": "clean",
            "split": "validation",
            "is_authoritative": "true",
            "payload_hash": "1" * 64,
            "image_source": "camera",
            "capture_session": "clean/scan_usable",
            "device": "phone-a",
            "quality_condition": "glare",
            "quality_severity": "moderate",
            "paired_group": "2" * 64,
            "physical_qr": "3" * 64,
        },
        {
            "sample_path": "severe.png",
            "label": "tampered",
            "split": "train",
            "is_authoritative": "true",
            "payload_hash": "4" * 64,
            "image_source": "gallery",
            "capture_session": "tampered/scan_severe",
            "device": "phone-a",
            "quality_condition": "defocus_blur",
            "quality_severity": "severe",
            "paired_group": "5" * 64,
            "physical_qr": "6" * 64,
        },
    ]
    with (capture_root / "manifest_v3.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(structural_recipes, "ROOT", tmp_path)
    monkeypatch.setattr(structural_recipes, "IS_V3", True)

    training_rows = structural_recipes._runtime_capture_rows()

    assert len(training_rows) == 1
    assert training_rows[0]["split"] == "validation"
    assert training_rows[0]["source"] == "qrguard_runtime_v3_camera"
    assert training_rows[0]["quality_condition"] == "glare"
