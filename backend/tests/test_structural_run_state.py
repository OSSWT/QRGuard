from __future__ import annotations

import json
from pathlib import Path

import pytest

from ml_training.structural.src.run_state import (
    build_run_identity,
    read_run_state,
    validate_run_identity,
    write_run_state,
)


def test_run_identity_changes_when_manifest_changes(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    manifest = tmp_path / "manifest.csv"
    config.write_text('{"seed": 42}', encoding="utf-8")
    manifest.write_text("path,label\na.png,clean\n", encoding="utf-8")

    first = build_run_identity("structural-test", config, manifest)
    manifest.write_text("path,label\nb.png,tampered\n", encoding="utf-8")
    second = build_run_identity("structural-test", config, manifest)

    assert first["config_sha256"] == second["config_sha256"]
    assert first["manifest_sha256"] != second["manifest_sha256"]


def test_validate_run_identity_rejects_stale_checkpoint(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    manifest = tmp_path / "manifest.csv"
    config.write_text("{}", encoding="utf-8")
    manifest.write_text("path,label\n", encoding="utf-8")
    expected = build_run_identity("structural-new", config, manifest)

    with pytest.raises(ValueError, match="version"):
        validate_run_identity(expected, {**expected, "version": "structural-old"})


def test_run_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "run_state.json"
    write_run_state(path, {"mode": "resume", "last_completed_epoch": 3})

    state = read_run_state(path)
    assert state["mode"] == "resume"
    assert state["last_completed_epoch"] == 3
    assert "updated_at" in state
    assert json.loads(path.read_text(encoding="utf-8")) == state
