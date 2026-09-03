"""Build the compact r02 screen-only acquisition validation pack.

This is a development/release-candidate check, not an independent holdout. It
combines the two regression sentinels (SEM-05 and SEM-11), exposure-stressed
Structural demo cases, and clean long-payload Version 10/14 controls. The plan
never asks the operator to print a reference or use viewer zoom above 100%.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import cv2
import qrcode
from qrcode.constants import ERROR_CORRECT_M

ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "ml_training/datasets/qr_codes_demo"
DEMO_MANIFEST = DEMO_ROOT / "MANIFEST.json"
DEFAULT_OUTPUT = ROOT.parent / "90_Rebuildable_Caches/Acquisition_Validation_2026-09-r02"
DEFAULT_PLAN = ROOT / "app/assets/capture/acquisition_validation_plan.json"
DEFAULT_ARCHIVE = DEFAULT_OUTPUT.with_suffix(".zip")
CAMPAIGN_ID = "acquisition-quality-exposure-module-scale-2026-09-r02"

DEMO_CASES = (
    "SEM-05-USERINFO",
    "SEM-11-PLAIN-TEXT",
    "STR-CLN-OVEREXP",
    "STR-CLN-UNDEREXP",
    "STR-ADV-NORMAL",
    "STR-TMP-NORMAL",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _qr_structure(path: Path) -> dict[str, int]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"unreadable QR card: {path}")
    payload, _, straight = cv2.QRCodeDetector().detectAndDecode(image)
    if not payload or straight is None:
        raise RuntimeError(f"QR card does not decode: {path}")
    modules = int(straight.shape[0])
    if modules < 21 or (modules - 17) % 4:
        raise RuntimeError(f"invalid module count {modules}: {path}")
    return {
        "module_count": modules,
        "qr_version": (modules - 17) // 4,
        "payload_utf8_bytes": len(payload.encode("utf-8")),
    }


def _high_version_card(path: Path, *, version: int, payload_bytes: int) -> str:
    prefix = f"QRGuard acquisition V{version:02d} "
    fill = hashlib.sha256(prefix.encode()).hexdigest()
    payload = prefix + (fill * 8)[: payload_bytes - len(prefix)]
    if len(payload.encode("utf-8")) != payload_bytes:
        raise RuntimeError("high-Version payload length construction failed")
    code = qrcode.QRCode(
        version=version,
        error_correction=ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    code.add_data(payload)
    code.make(fit=False)
    code.make_image(fill_color="black", back_color="white").convert("RGB").save(path)
    return payload


def _condition_plan() -> list[dict[str, Any]]:
    return [
        {
            "id": "screen-80-brightness-50",
            "label": "80% / B50",
            "instruction": "Viewer zoom 80%; display brightness about 50%. Do not print.",
            "metadata": {
                "capture_medium": "screen",
                "screen_scale_percent": 80,
                "display_brightness_percent": 50,
                "exposure_role": "baseline",
            },
        },
        {
            "id": "screen-100-brightness-100",
            "label": "100% / B100",
            "instruction": "Viewer zoom exactly 100%; display brightness 100%. Do not exceed 100%.",
            "metadata": {
                "capture_medium": "screen",
                "screen_scale_percent": 100,
                "display_brightness_percent": 100,
                "exposure_role": "overexposure_stress",
            },
        },
        {
            "id": "screen-100-brightness-30",
            "label": "100% / B30",
            "instruction": "Viewer zoom exactly 100%; display brightness about 30%. Do not print.",
            "metadata": {
                "capture_medium": "screen",
                "screen_scale_percent": 100,
                "display_brightness_percent": 30,
                "exposure_role": "underexposure_stress",
            },
        },
    ]


def build_pack(
    output: Path = DEFAULT_OUTPUT,
    *,
    plan_path: Path = DEFAULT_PLAN,
    archive_path: Path | None = DEFAULT_ARCHIVE,
) -> dict[str, Any]:
    manifest = json.loads(DEMO_MANIFEST.read_text(encoding="utf-8"))
    demo = {row["case_id"]: row for row in manifest["cases"]}
    if any(case_id not in demo for case_id in DEMO_CASES):
        raise RuntimeError("canonical QR demo manifest is incomplete")

    if output.exists():
        shutil.rmtree(output)
    cards = output / "cards"
    cards.mkdir(parents=True)
    plan_cases: list[dict[str, Any]] = []
    pack_rows: list[dict[str, Any]] = []

    for case_id in DEMO_CASES:
        source = demo[case_id]
        source_path = DEMO_ROOT / source["image_path"]
        target = cards / f"{case_id}.png"
        if _sha256(source_path) != source["image_sha256"]:
            raise RuntimeError(f"source hash drift: {case_id}")
        shutil.copy2(source_path, target)
        structure = _qr_structure(target)
        structural_label = source["structural_ground_truth"]
        metadata = {
            **structure,
            "source_case_id": case_id,
            "source_pack_id": manifest["pack_id"],
            "source_image_sha256": source["image_sha256"],
            "intended_app_verdict": source["intended_verdict"],
            "semantic_regression_sentinel": case_id == "SEM-05-USERINFO",
            "sem11_regression_sentinel": case_id == "SEM-11-PLAIN-TEXT",
            "development_only": True,
            "deployment_holdout_eligible": False,
            "case_identity_source": "operator_selection_plus_payload_hash",
        }
        plan_cases.append(
            {
                "case_id": case_id,
                "label": f"{case_id} - V{structure['qr_version']}",
                "ground_truth": structural_label,
                "expected_payload_sha256": source["payload_sha256"],
                "instruction": f"Display only cards/{case_id}.png under the selected screen condition.",
                "metadata": metadata,
            }
        )
        pack_rows.append(
            {
                "case_id": case_id,
                "card_path": f"cards/{case_id}.png",
                "card_sha256": _sha256(target),
                "structural_ground_truth": structural_label,
                **structure,
            }
        )

    for case_id, version, payload_bytes in (
        ("ACQ-CLN-V10-LONG", 10, 112),
        ("ACQ-CLN-V14-LONG", 14, 180),
    ):
        target = cards / f"{case_id}.png"
        payload = _high_version_card(
            target, version=version, payload_bytes=payload_bytes
        )
        structure = _qr_structure(target)
        if structure["qr_version"] != version:
            raise RuntimeError(f"forced Version drift: {case_id}")
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()
        plan_cases.append(
            {
                "case_id": case_id,
                "label": f"{case_id} - clean V{version}",
                "ground_truth": "clean",
                "expected_payload_sha256": payload_hash,
                "instruction": f"Display only cards/{case_id}.png under the selected screen condition.",
                "metadata": {
                    **structure,
                    "payload_length_bin": "long_97_plus",
                    "generated_for": "module_scale_and_long_payload_control",
                    "development_only": True,
                    "deployment_holdout_eligible": False,
                    "case_identity_source": "operator_selection_plus_payload_hash",
                },
            }
        )
        pack_rows.append(
            {
                "case_id": case_id,
                "card_path": f"cards/{case_id}.png",
                "card_sha256": _sha256(target),
                "structural_ground_truth": "clean",
                **structure,
            }
        )

    plan = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "frames_per_session": 5,
        "repeats_per_distance": 1,
        "distances": _condition_plan(),
        "privacy": {
            "raw_payload_stored": False,
            "payload_identifier": "sha256 of on-device decoded text",
        },
        "cases": plan_cases,
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_bytes = (json.dumps(plan, indent=2, ensure_ascii=False) + "\n").encode()
    plan_path.write_bytes(plan_bytes)
    (output / "DIAGNOSTIC_CAPTURE_PLAN.json").write_bytes(plan_bytes)

    readme = """# QRGuard acquisition validation r02

Screen-only validation; printing is neither needed nor allowed for this run.
Use the diagnostic APK built for this plan. For each selected condition, show
one named card only, arm one session, and let the app automatically accept five
post-metering/post-exposure quality-gated frames. Viewer zoom must be 80% or
100% exactly and must never exceed 100%.

This is development/release-candidate evidence, not a fresh blind holdout and
not permission to promote a new model.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")
    with (output / "CAPTURE_ORDER.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("condition_id", "case_id", "card_path"),
        )
        writer.writeheader()
        for condition in plan["distances"]:
            for row in pack_rows:
                writer.writerow(
                    {
                        "condition_id": condition["id"],
                        "case_id": row["case_id"],
                        "card_path": row["card_path"],
                    }
                )

    pack_manifest = {
        "schema_version": 1,
        "pack_id": CAMPAIGN_ID,
        "role": "development_release_candidate_validation",
        "independent_holdout": False,
        "screen_only": True,
        "maximum_viewer_scale_percent": 100,
        "case_count": len(pack_rows),
        "condition_count": len(plan["distances"]),
        "target_sessions": len(pack_rows) * len(plan["distances"]),
        "target_frames": len(pack_rows) * len(plan["distances"]) * 5,
        "capture_plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "cases": pack_rows,
    }
    (output / "MANIFEST.json").write_text(
        json.dumps(pack_manifest, indent=2) + "\n", encoding="utf-8"
    )

    if archive_path is not None:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(
            archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in sorted(output.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(output.parent).as_posix())
    return pack_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    args = parser.parse_args()
    report = build_pack(args.output, plan_path=args.plan, archive_path=args.archive)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
