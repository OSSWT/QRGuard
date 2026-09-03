"""Rebase the verified r06 prepared cache and append r07 clean evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
R06_VERSION = "structural-2026.09-r06"
R07_VERSION = "structural-2026.09-r07"
R06_MANIFEST_SHA256 = (
    "c553efd57c707d1f60457ade0ffa2d2675e225727b95d8cea17820ed56a96d16"
)
DEFAULT_R06 = ROOT / "ml_training/datasets/structural/processed" / R06_VERSION
DEFAULT_R07 = ROOT / "ml_training/datasets/structural/processed" / R07_VERSION
DEFAULT_DEVELOPMENT = (
    ROOT / "data/structural_consumed_blind_development/consumed_blind_clean_release_r01/manifest.csv"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_manifest(
    r06_root: Path = DEFAULT_R06,
    r07_root: Path = DEFAULT_R07,
    development_manifest: Path = DEFAULT_DEVELOPMENT,
) -> dict[str, Any]:
    source_manifest = r06_root / "manifest.csv"
    if _sha256(source_manifest) != R06_MANIFEST_SHA256:
        raise ValueError("r06 prepared manifest does not match the locked cache")
    if not r07_root.is_dir():
        raise FileNotFoundError(
            f"copy the verified r06 prepared directory before rebasing: {r07_root}"
        )
    development_rows = _read_csv(development_manifest)
    if len(development_rows) != 80 or Counter(
        (row.get("split"), row.get("label")) for row in development_rows
    ) != {("train", "clean"): 60, ("validation", "clean"): 20}:
        raise ValueError("r07 consumed clean development manifest contract mismatch")

    old_prefix = (
        "ml_training/datasets/structural/processed/"
        f"{R06_VERSION}/"
    )
    new_prefix = (
        "ml_training/datasets/structural/processed/"
        f"{R07_VERSION}/"
    )
    base_rows = _read_csv(source_manifest)
    rebased_rows = []
    for row in base_rows:
        rebased = dict(row)
        path = str(rebased.get("path", ""))
        if path.startswith(old_prefix):
            rebased["path"] = new_prefix + path[len(old_prefix) :]
        rebased_rows.append(rebased)
    combined = [*rebased_rows, *development_rows]
    if len(combined) != 14230:
        raise ValueError(f"r07 manifest must contain 14,230 rows, got {len(combined)}")
    for row in combined:
        image = ROOT / str(row.get("path", ""))
        if not image.is_file():
            raise FileNotFoundError(f"r07 manifest image missing: {image}")

    destination = r07_root / "manifest.csv"
    _write_csv(destination, combined)
    audit = {
        "version": R07_VERSION,
        "base_version": R06_VERSION,
        "base_manifest_sha256": R06_MANIFEST_SHA256,
        "consumed_blind_clean_development_manifest_sha256": _sha256(
            development_manifest
        ),
        "rows": len(combined),
        "added_rows": len(development_rows),
        "counts": {
            f"{split}/{label}": sum(
                row.get("split") == split and row.get("label") == label
                for row in combined
            )
            for split in sorted({str(row.get("split")) for row in combined})
            for label in ("clean", "adversarial", "tampered")
        },
        "groups": {
            split: len(
                {
                    str(row.get("group_id"))
                    for row in combined
                    if row.get("split") == split
                }
            )
            for split in sorted({str(row.get("split")) for row in combined})
        },
        "exact_app_crop_rows": sum(
            str(row.get("is_exact_app_crop", "")).lower() == "true"
            for row in combined
        ),
        "consumed_blind_clean_development_rows": len(development_rows),
        "manifest_sha256": _sha256(destination),
        "deployment_note": (
            "The consumed M8 rows are development-only. A newly generated blind "
            "device/display/session holdout remains mandatory for promotion."
        ),
    }
    (r07_root / "preparation_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r06-root", type=Path, default=DEFAULT_R06)
    parser.add_argument("--r07-root", type=Path, default=DEFAULT_R07)
    parser.add_argument(
        "--development-manifest", type=Path, default=DEFAULT_DEVELOPMENT
    )
    args = parser.parse_args()
    audit = build_manifest(
        args.r06_root.resolve(strict=True),
        args.r07_root.resolve(strict=True),
        args.development_manifest.resolve(strict=True),
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
