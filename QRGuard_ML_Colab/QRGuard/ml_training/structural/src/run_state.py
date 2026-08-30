"""Version-locked run identity and state helpers for Structural training."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUN_MODES = ("fresh", "resume", "evaluate_only", "report_only")
IDENTITY_KEYS = ("version", "config_sha256", "manifest_sha256")


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for a required file."""
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_run_identity(version: str, config: Path, manifest: Path) -> dict[str, str]:
    """Fingerprint everything that makes a checkpoint safe to resume."""
    return {
        "version": version,
        "config_sha256": sha256_file(config),
        "manifest_sha256": sha256_file(manifest),
    }


def validate_run_identity(expected: dict[str, str], recorded: dict[str, Any]) -> None:
    """Reject a checkpoint produced by another version, config, or manifest."""
    mismatches = [
        f"{key}: expected {expected.get(key)!r}, recorded {recorded.get(key)!r}"
        for key in IDENTITY_KEYS
        if expected.get(key) != recorded.get(key)
    ]
    if mismatches:
        raise ValueError("checkpoint identity mismatch; " + "; ".join(mismatches))


def write_run_state(path: Path, state: dict[str, Any]) -> None:
    """Atomically publish a small human-readable run-state document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_run_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise TypeError(f"run state must be a JSON object: {path}")
    return result
