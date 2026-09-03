"""Build the post-freeze blinded M8 Structural acceptance pack.

The current candidate must never score these references before physical capture.
Attacks are generated against the previously accepted victim checkpoint, while
case identifiers and capture order are opaque to the operator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_structural_coverage_development_pack import (
    BaseSpec,
    CaseSpec,
    _payload,
    build_pack,
)

PACK_ID = "structural-coverage-blind-holdout-2026-09-r01"
DEFAULT_OUTPUT = ROOT / "dist/Structural_Coverage_Blind_Holdout_2026-09-r01"
DEFAULT_APP_PLAN = (
    ROOT / "app/assets/capture/structural_coverage_blind_holdout_plan.json"
)
DEFAULT_ARCHIVE = (
    ROOT.parent
    / "90_Rebuildable_Caches/Structural_Coverage_Blind_Holdout_2026-09-r01.zip"
)


def blind_base_specs() -> tuple[BaseSpec, ...]:
    assignments = (
        *((3, mask, "low_v1_v3", "short_1_32", 24) for mask in (7, 6, 5, 4, 3)),
        *((6, mask, "medium_v4_v6", "medium_33_96", 48) for mask in (2, 1, 0, 7, 6)),
        *(
            (12, mask, "high_v7_plus", "long_97_plus", 132)
            for mask in (5, 4, 3, 2, 1, 0)
        ),
    )
    return tuple(
        BaseSpec(
            base_id=f"BLIND-BASE-{index:02d}",
            qr_version=version,
            module_count=17 + 4 * version,
            mask_pattern=mask,
            version_band=band,
            payload_length_bin=length_bin,
            payload=_payload(index, target_bytes, "blind-holdout-2026-09-r01"),
            development_split="blind_holdout",
        )
        for index, (version, mask, band, length_bin, target_bytes) in enumerate(
            assignments, start=1
        )
    )


def blind_case_specs() -> tuple[CaseSpec, ...]:
    candidates = [
        (base, label)
        for base in blind_base_specs()
        for label in ("clean", "adversarial", "tampered")
    ]
    candidates.sort(
        key=lambda item: hashlib.sha256(
            f"opaque-order:{item[0].base_id}:{item[1]}".encode()
        ).hexdigest()
    )
    return tuple(
        CaseSpec(
            case_id=(
                f"BLD-{index:02d}-"
                + hashlib.sha256(f"opaque-id:{base.base_id}:{label}".encode())
                .hexdigest()[:6]
                .upper()
            ),
            label=label,
            label_code="BLD",
            base=base,
        )
        for index, (base, label) in enumerate(candidates, start=1)
    )


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
        specs=blind_case_specs(),
        pack_id=PACK_ID,
        evidence_role="blind_holdout",
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
