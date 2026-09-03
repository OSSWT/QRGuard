"""Rebase the verified r07 cache and append verified attack hard positives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_VERSION = "structural-2026.09-r07"
TARGET_VERSION = "structural-r07-corrective-v1"
BASE_MANIFEST_SHA256 = (
    "dbc595a4542dab8490caed4ee2bbd236743d307e849cb4c03d2955c81761ca5b"
)
DEFAULT_BASE = ROOT / "ml_training/datasets/structural/processed" / BASE_VERSION
DEFAULT_TARGET = ROOT / "ml_training/datasets/structural/processed" / TARGET_VERSION
DEFAULT_DEVELOPMENT = (
    ROOT
    / "data/structural_consumed_blind_attack_development/"
    "r07-corrective-v1/manifest.csv"
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
    base_root: Path = DEFAULT_BASE,
    target_root: Path = DEFAULT_TARGET,
    development_manifest: Path = DEFAULT_DEVELOPMENT,
) -> dict[str, Any]:
    source_manifest = base_root / "manifest.csv"
    if _sha256(source_manifest) != BASE_MANIFEST_SHA256:
        raise ValueError("r07 prepared manifest does not match the locked cache")
    if target_root.exists():
        raise FileExistsError(f"refusing to overwrite target cache: {target_root}")
    attack_rows = _read_csv(development_manifest)
    if len(attack_rows) != 10 or Counter(
        (row.get("split"), row.get("label")) for row in attack_rows
    ) != {("train", "adversarial"): 10}:
        raise ValueError("verified attack development manifest contract mismatch")
    if any(
        row.get("physical_attack_survival_verified", "").lower() != "true"
        or row.get("promotion_eligible", "").lower() != "false"
        for row in attack_rows
    ):
        raise ValueError("attack rows escaped their non-promoting survival contract")

    shutil.copytree(base_root, target_root)
    old_prefix = f"ml_training/datasets/structural/processed/{BASE_VERSION}/"
    new_prefix = f"ml_training/datasets/structural/processed/{TARGET_VERSION}/"
    base_rows = _read_csv(source_manifest)
    rebased_rows = []
    for row in base_rows:
        rebased = dict(row)
        path = str(rebased.get("path", ""))
        if path.startswith(old_prefix):
            rebased["path"] = new_prefix + path[len(old_prefix) :]
        rebased_rows.append(rebased)
    combined = [*rebased_rows, *attack_rows]
    if len(combined) != 14240:
        raise ValueError(f"corrective manifest must contain 14,240 rows, got {len(combined)}")
    for row in combined:
        image = ROOT / str(row.get("path", ""))
        if not image.is_file():
            raise FileNotFoundError(f"corrective manifest image missing: {image}")

    destination = target_root / "manifest.csv"
    _write_csv(destination, combined)
    audit = {
        "version": TARGET_VERSION,
        "base_version": BASE_VERSION,
        "base_manifest_sha256": BASE_MANIFEST_SHA256,
        "verified_attack_development_manifest_sha256": _sha256(
            development_manifest
        ),
        "rows": len(combined),
        "added_rows": len(attack_rows),
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
        "verified_attack_development_rows": len(attack_rows),
        "manifest_sha256": _sha256(destination),
        "deployment_note": (
            "All M8 additions are consumed development evidence. A fresh independent "
            "device/display/session holdout remains mandatory for promotion."
        ),
    }
    (target_root / "preparation_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--target-root", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--development-manifest", type=Path, default=DEFAULT_DEVELOPMENT)
    args = parser.parse_args()
    audit = build_manifest(
        args.base_root.resolve(strict=True),
        args.target_root.resolve(),
        args.development_manifest.resolve(strict=True),
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
