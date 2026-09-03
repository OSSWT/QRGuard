"""Build the r02 paired physical-attack survival development pack.

Each of 16 QR identities has one clean reference and two stronger adversarial
references with distinct projection profiles.  The physical capture is still
development evidence: only attacks that pass the separate post-capture victim
survival audit may enter training.  No case in this pack is a deployment
holdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_structural_coverage_development_pack import (
    BaseSpec,
    CaseSpec,
    build_pack,
)

PACK_ID = "structural-physical-attack-development-2026-09-r02"
DEFAULT_OUTPUT = ROOT / "dist/Structural_Physical_Attack_Development_2026-09-r02"
DEFAULT_APP_PLAN = (
    ROOT / "app/assets/capture/structural_physical_attack_development_plan.json"
)
DEFAULT_ARCHIVE = (
    ROOT.parent
    / "90_Rebuildable_Caches/Structural_Physical_Attack_Development_2026-09-r02.zip"
)


def _payload(index: int, target_bytes: int) -> str:
    prefix = f"P{index:02d}"
    digest = hashlib.sha256(f"physical-r02:{index}".encode()).hexdigest()
    required = target_bytes - len(prefix)
    if required < 0:
        raise ValueError("payload prefix exceeds target length")
    return prefix + (digest * ((required + len(digest) - 1) // len(digest)))[:required]


def _version_band(version: int) -> str:
    if version <= 3:
        return "low_v1_v3"
    if version <= 6:
        return "medium_v4_v6"
    return "high_v7_plus"


def _payload_bin(length: int) -> str:
    if length <= 32:
        return "short_1_32"
    if length <= 96:
        return "medium_33_96"
    return "long_97_plus"


def base_specs() -> tuple[BaseSpec, ...]:
    # All masks occur twice. Unlike r01, each Version band contains several
    # actual Versions, and the higher bands also contain shorter payloads.
    assignments = (
        (1, 0, 7),
        (2, 3, 14),
        (2, 6, 12),
        (3, 1, 24),
        (3, 4, 20),
        (4, 7, 33),
        (4, 2, 24),
        (5, 5, 40),
        (6, 0, 48),
        (6, 3, 24),
        (7, 6, 64),
        (8, 1, 80),
        (9, 4, 48),
        (10, 7, 112),
        (12, 2, 132),
        (14, 5, 180),
    )
    validation_indices = {5, 10, 15, 16}
    return tuple(
        BaseSpec(
            base_id=f"PHY-R02-BASE-{index:02d}",
            qr_version=version,
            module_count=17 + 4 * version,
            mask_pattern=mask,
            version_band=_version_band(version),
            payload_length_bin=_payload_bin(target_bytes),
            payload=_payload(index, target_bytes),
            development_split=(
                "validation" if index in validation_indices else "train"
            ),
        )
        for index, (version, mask, target_bytes) in enumerate(assignments, start=1)
    )


def case_specs() -> tuple[CaseSpec, ...]:
    rows: list[CaseSpec] = []
    for base in base_specs():
        suffix = base.base_id[-2:]
        rows.extend(
            (
                CaseSpec(
                    case_id=f"PHY-CLN-{suffix}",
                    label="clean",
                    label_code="CLN",
                    base=base,
                ),
                CaseSpec(
                    case_id=f"PHY-ADV-F-{suffix}",
                    label="adversarial",
                    label_code="ADV",
                    base=base,
                    attack_profile="screen_robust_function",
                ),
                CaseSpec(
                    case_id=f"PHY-ADV-X-{suffix}",
                    label="adversarial",
                    label_code="ADV",
                    base=base,
                    attack_profile="screen_robust_alternate",
                ),
            )
        )
    return tuple(rows)


def validate_distribution(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 48:
        raise RuntimeError(f"expected 48 cases, got {len(rows)}")
    clean = [row for row in rows if row["label"] == "clean"]
    adversarial = [row for row in rows if row["label"] == "adversarial"]
    if len(clean) != 16 or len(adversarial) != 32:
        raise RuntimeError("expected 16 clean and 32 adversarial cases")
    if Counter(row["version_band"] for row in clean) != {
        "low_v1_v3": 5,
        "medium_v4_v6": 5,
        "high_v7_plus": 6,
    }:
        raise RuntimeError("clean Version bands are not 5/5/6")
    if Counter(row["mask_pattern"] for row in clean) != {mask: 2 for mask in range(8)}:
        raise RuntimeError("clean masks must occur twice")
    for base_id in {row["base_id"] for row in rows}:
        selected = [row for row in rows if row["base_id"] == base_id]
        if Counter(row["label"] for row in selected) != {
            "clean": 1,
            "adversarial": 2,
        }:
            raise RuntimeError(f"invalid paired cases for {base_id}")
        if {
            row.get("attack_profile")
            for row in selected
            if row["label"] == "adversarial"
        } != {
            "screen_robust_function",
            "screen_robust_alternate",
        }:
            raise RuntimeError(f"invalid attack profiles for {base_id}")


README = """# Structural physical-attack development pack r02

This pack contains 48 development cases: 16 clean QR identities paired with 32
stronger digital EOT attack candidates. Versions 1, 2, 3, 4, 5, 6, 7, 8, 9,
10, 12 and 14 are represented; every mask occurs twice in the clean identities.

Capture every card once at screen 80%. Keep the viewer, brightness, camera
distance and angle fixed. Export one ZIP after all 48 cases are complete.

Important: an adversarial reference is not automatically a valid physical
adversarial sample. After capture, the victim survival audit compares every
attack burst with its paired clean burst. Only independently verified surviving
attacks may enter r02 training. This entire pack is development evidence and can
never serve as the later blinded deployment holdout.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--app-plan", type=Path, default=DEFAULT_APP_PLAN)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--victim-checkpoint", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_pack(
        args.output.resolve(),
        args.app_plan.resolve(),
        args.archive.resolve(),
        args.victim_checkpoint.resolve(strict=True),
        specs=case_specs(),
        pack_id=PACK_ID,
        evidence_role="physical_attack_development_only",
        distribution_validator=validate_distribution,
        readme_text=README,
    )
    print(
        json.dumps(
            {
                "cases": result["manifest"]["case_count"],
                "archive": result["archive"],
                "archive_sha256": result["archive_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
