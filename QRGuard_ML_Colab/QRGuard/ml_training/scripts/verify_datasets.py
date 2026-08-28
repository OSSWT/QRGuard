"""Verify official dataset archives before extraction or training."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "qr_surfaces": {
        "path": ROOT / "ml_training/datasets/structural/downloads/qr_surfaces/qr_codes_in_surfaces.zip",
        "bytes": 384_232_282,
        "sha256": "706352654a744217b6853c77362f4a32cc318d941b715423948ba2108aae7523",
        "doi": "10.17632/m6mfwc52vk.1",
    },
    "qrdn": {
        "path": ROOT / "ml_training/datasets/structural/downloads/qrdn/QR-DN1.0.zip",
        "bytes": 1_025_545_184,
        "sha256": "1f175a62239646bd7d6b179245cb0970c03b179c2baf1a5e8e59ba0b156cdf61",
        "doi": "10.17632/t2bdr663ms.2",
    },
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    results = {}
    failed = False
    for name, source in SOURCES.items():
        path = source["path"]
        record = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "expected_bytes": source["bytes"],
            "expected_sha256": source["sha256"],
            "doi": source["doi"],
            "exists": path.is_file(),
        }
        if path.is_file():
            record["actual_bytes"] = path.stat().st_size
            if path.stat().st_size == source["bytes"]:
                record["actual_sha256"] = digest(path)
            else:
                record["actual_sha256"] = None
            record["passed"] = (
                record["actual_bytes"] == source["bytes"]
                and record["actual_sha256"] == source["sha256"]
            )
        else:
            record["passed"] = False
        failed |= not record["passed"]
        results[name] = record
        print(name, "PASS" if record["passed"] else "NOT READY")

    output = ROOT / "ml_training/datasets/download_verification.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
