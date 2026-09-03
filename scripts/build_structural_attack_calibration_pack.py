"""Build development pairs for calibrating screen-camera attack survival.

The pack is never a deployment holdout.  Each QR identity has a clean card and
two attacks generated with different projections under the stronger,
deterministic screen-camera EOT suite.  Post-capture victim verification remains
mandatory: generation-time attack success is not physical-survival evidence.
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

PACK_ID = "structural-attack-calibration-v1"
DEFAULT_OUTPUT = ROOT / "dist/Structural_Attack_Calibration_v1"
DEFAULT_APP_PLAN = ROOT / "app/assets/capture/structural_attack_calibration_plan.json"
DEFAULT_ARCHIVE = ROOT.parent / "90_Rebuildable_Caches/Structural_Attack_Calibration_v1.zip"


def _payload(index: int, target_bytes: int) -> str:
    prefix = f"A{index:02d}"
    if len(prefix) > target_bytes:
        raise ValueError("payload prefix exceeds target length")
    digest = hashlib.sha256(f"attack-calibration:{index}".encode()).hexdigest()
    needed = target_bytes - len(prefix)
    return prefix + (digest * ((needed + len(digest) - 1) // len(digest)))[:needed]


def _payload_bin(length: int) -> str:
    if length <= 32:
        return "short_1_32"
    if length <= 96:
        return "medium_33_96"
    return "long_97_plus"


def calibration_base_specs() -> tuple[BaseSpec, ...]:
    # Eight identities per Version band and each mask once per band.  Payload
    # lengths stay within fixed Version-H capacity while varying density.
    assignments = (
        *((1, 0, 7), (2, 1, 12), (2, 2, 14), (3, 3, 18)),
        *((3, 4, 20), (3, 5, 22), (3, 6, 24), (3, 7, 16)),
        *((4, 0, 24), (4, 1, 30), (5, 2, 34), (5, 3, 40)),
        *((5, 4, 44), (6, 5, 48), (6, 6, 54), (6, 7, 36)),
        *((7, 0, 56), (8, 1, 72), (9, 2, 88), (10, 3, 97)),
        *((11, 4, 112), (12, 5, 132), (13, 6, 152), (14, 7, 176)),
    )
    rows = []
    for index, (version, mask, target_bytes) in enumerate(assignments, start=1):
        band = (
            "low_v1_v3"
            if version <= 3
            else "medium_v4_v6"
            if version <= 6
            else "high_v7_plus"
        )
        rows.append(
            BaseSpec(
                base_id=f"ATK-CAL-BASE-{index:02d}",
                qr_version=version,
                module_count=17 + 4 * version,
                mask_pattern=mask,
                version_band=band,
                payload_length_bin=_payload_bin(target_bytes),
                payload=_payload(index, target_bytes),
                development_split=("validation" if mask in {6, 7} else "train"),
            )
        )
    return tuple(rows)


def calibration_case_specs() -> tuple[CaseSpec, ...]:
    rows: list[CaseSpec] = []
    for base in calibration_base_specs():
        suffix = base.base_id[-2:]
        rows.extend(
            (
                CaseSpec(
                    case_id=f"ATK-CAL-CLN-{suffix}",
                    label="clean",
                    label_code="CLN",
                    base=base,
                ),
                CaseSpec(
                    case_id=f"ATK-CAL-F-{suffix}",
                    label="adversarial",
                    label_code="ADV",
                    base=base,
                    attack_profile="screen_camera_robust_v2_function",
                ),
                CaseSpec(
                    case_id=f"ATK-CAL-X-{suffix}",
                    label="adversarial",
                    label_code="ADV",
                    base=base,
                    attack_profile="screen_camera_robust_v2_alternate",
                ),
            )
        )
    return tuple(rows)


def validate_distribution(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 72:
        raise RuntimeError(f"expected 72 cases, got {len(rows)}")
    clean = [row for row in rows if row["label"] == "clean"]
    adversarial = [row for row in rows if row["label"] == "adversarial"]
    if len(clean) != 24 or len(adversarial) != 48:
        raise RuntimeError("expected 24 clean and 48 adversarial cases")
    for label, selected, expected in (
        ("clean", clean, 8),
        ("adversarial", adversarial, 16),
    ):
        bands = Counter(row["version_band"] for row in selected)
        if bands != {
            "low_v1_v3": expected,
            "medium_v4_v6": expected,
            "high_v7_plus": expected,
        }:
            raise RuntimeError(f"{label} Version-band imbalance: {bands}")
    if Counter(row["mask_pattern"] for row in clean) != {
        mask: 3 for mask in range(8)
    }:
        raise RuntimeError("clean masks must occur three times")
    for base_id in {row["base_id"] for row in rows}:
        selected = [row for row in rows if row["base_id"] == base_id]
        if Counter(row["label"] for row in selected) != {
            "clean": 1,
            "adversarial": 2,
        }:
            raise RuntimeError(f"invalid paired cases for {base_id}")


README = """# Structural attack calibration pack

This is development evidence, not a blind holdout. It contains 24 clean QR
identities paired with 48 attacks from two deterministic screen-camera EOT
profiles. Each Version band has eight clean identities and sixteen attacks.

Capture every case with one unchanged screen/camera setup. The post-capture
victim audit decides which attacks physically survived. A digital attack label
alone never qualifies a captured image as adversarial training or test data.
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
        specs=calibration_case_specs(),
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
