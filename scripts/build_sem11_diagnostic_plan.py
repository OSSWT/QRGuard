"""Translate the SEM-11 root-cause manifest into an Android capture plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "dist/SEM11_Root_Cause_Test_Pack"
DEFAULT_MANIFEST = DEFAULT_PACK / "MANIFEST.json"
DEFAULT_APP_OUTPUT = ROOT / "app/assets/capture/sem11_root_cause_capture_plan.json"
DEFAULT_PACK_OUTPUT = DEFAULT_PACK / "DIAGNOSTIC_CAPTURE_PLAN.json"


def build_capture_plan(manifest: dict[str, Any]) -> dict[str, Any]:
    cases = []
    for case in manifest["cases"]:
        cases.append(
            {
                "case_id": case["case_id"],
                "label": (
                    f"{case['case_id']} · V{case['actual_version']} "
                    f"mask {case['actual_mask']}"
                ),
                "ground_truth": "clean",
                "expected_payload_sha256": case["payload_sha256"],
                "instruction": (
                    f"Display only {case['image_path']}. Keep the viewer at 80%, "
                    "brightness and camera pose fixed for the three repeats."
                ),
                "metadata": {
                    "family": case["family"],
                    "qr_version": case["actual_version"],
                    "mask_pattern": case["actual_mask"],
                    "module_count": case["module_count"],
                    "dark_module_ratio": case["dark_module_ratio"],
                    "qr_matrix_sha256": case["qr_matrix_sha256"],
                    "reference_image_path": case["image_path"],
                    "case_identity_source": (
                        "operator_selection_plus_payload_hash; shared-payload "
                        "mask/version controls require visual selection discipline"
                    ),
                },
            }
        )
    return {
        "schema_version": 1,
        "campaign_id": "sem11-root-cause-screen-80-2026-09-r01",
        "frames_per_session": 5,
        "repeats_per_distance": 3,
        "distances": [
            {
                "id": "screen-80",
                "label": "Screen 80%",
                "instruction": (
                    "Keep the reference viewer at 80%. Use the same display, "
                    "brightness, distance and angle throughout screening."
                ),
                "metadata": {
                    "capture_medium": "screen",
                    "screen_scale_percent": 80,
                    "controlled_variables": [
                        "display",
                        "brightness",
                        "camera_distance",
                        "camera_angle",
                    ],
                },
            }
        ],
        "privacy": {
            "raw_payload_stored": False,
            "payload_identifier": "sha256 of on-device decoded text",
        },
        "cases": cases,
    }


def _write(path: Path, plan: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--app-output", type=Path, default=DEFAULT_APP_OUTPUT)
    parser.add_argument("--pack-output", type=Path, default=DEFAULT_PACK_OUTPUT)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    plan = build_capture_plan(manifest)
    _write(args.app_output, plan)
    _write(args.pack_output, plan)
    print(
        f"Wrote {len(plan['cases'])} cases to {args.app_output} "
        f"and {args.pack_output}"
    )


if __name__ == "__main__":
    main()
