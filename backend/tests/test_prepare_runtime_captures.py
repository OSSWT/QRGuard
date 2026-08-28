"""Tests for the privacy-safe Structural RUN 6 capture manifest."""

import json

from PIL import Image

from ml_training.structural.src.prepare_runtime_captures import audit_rows, discover


def _session(
    root, label, name, payload_hash, source="camera", frames=3, distinct=True
):
    session = root / label / name
    session.mkdir(parents=True)
    metadata = {
        "ground_truth": label,
        "payload_sha256": payload_hash,
        "image_source": source,
    }
    (session / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    for index in range(frames):
        image = Image.new("RGB", (80, 80), "white")
        if distinct:
            image.putpixel((index, 0), (250 - index, 250 - index, 250 - index))
        image.save(session / f"crop_{index:02d}.png")


def test_same_payload_never_leaks_across_splits(tmp_path):
    shared_hash = "a" * 64
    _session(tmp_path, "clean", "scan_clean", shared_hash)
    _session(tmp_path, "tampered", "scan_tampered", shared_hash)

    rows, rejected = discover(tmp_path)
    audit = audit_rows(rows, rejected, 0, 0)

    assert len(rows) == 6
    assert len({row.split for row in rows}) == 1
    assert audit.leakage_groups == []


def test_invalid_or_non_camera_sessions_are_rejected(tmp_path):
    _session(tmp_path, "clean", "scan_gallery", "b" * 64, source="gallery")
    _session(tmp_path, "clean", "scan_short", "c" * 64, frames=1)

    rows, rejected = discover(tmp_path)

    assert rows == []
    assert rejected["not_live_camera"] == 1
    assert rejected["requires_3_to_5_frames"] == 1


def test_audit_fails_closed_when_real_data_is_missing(tmp_path):
    rows, rejected = discover(tmp_path)
    audit = audit_rows(rows, rejected)

    assert audit.strict_ready is False
    assert any("clean" in failure for failure in audit.strict_failures)


def test_duplicate_pixel_frames_are_rejected(tmp_path):
    _session(tmp_path, "clean", "scan_replayed", "d" * 64, distinct=False)

    rows, rejected = discover(tmp_path)

    assert rows == []
    assert rejected["duplicate_frames"] == 1
