"""Build the model-bound fresh blind acceptance pack for r07."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_structural_coverage_development_pack import (
    BaseSpec,
    CaseSpec,
    _payload,
    _pristine_qr,
    build_pack,
)

PACK_ID = "structural-r07-fresh-blind-v1"
DEFAULT_OUTPUT = ROOT.parent / "02_Active_Test_Packs/Structural_R07_Fresh_Blind_v1"
DEFAULT_APP_PLAN = ROOT / "app/assets/capture/structural_r07_fresh_blind_plan.json"
DEFAULT_ARCHIVE = (
    ROOT.parent / "02_Active_Test_Packs/Structural_R07_Fresh_Blind_v1.zip"
)
DEFAULT_CANDIDATE = (
    ROOT
    / "ml_training/structural/runs/structural-r07-corrective-v1/"
    "artifacts/structural_fp32.onnx"
)
DEFAULT_VICTIM = (
    Path.home()
    / ".cache/torch/hub/checkpoints/resnet18-f37072fd.pth"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fresh_base_specs(candidate_sha256: str) -> tuple[BaseSpec, ...]:
    assignments = (
        *((3, mask, "low_v1_v3", "short_1_32", 24) for mask in (0, 1, 2, 3, 4)),
        *((6, mask, "medium_v4_v6", "medium_33_96", 48) for mask in (5, 6, 7, 0, 1)),
        *(
            (10, mask, "high_v7_plus", "long_97_plus", 97)
            for mask in (2, 3, 4, 5, 6, 7)
        ),
    )
    detector = cv2.QRCodeDetector()
    selected: list[BaseSpec] = []
    for index, (version, mask, band, length_bin, target_bytes) in enumerate(
        assignments, start=1
    ):
        for nonce in range(128):
            candidate = BaseSpec(
                base_id=f"R07-BLIND-BASE-{index:02d}",
                qr_version=version,
                module_count=17 + 4 * version,
                mask_pattern=mask,
                version_band=band,
                payload_length_bin=length_bin,
                payload=_payload(
                    index,
                    target_bytes,
                    f"{PACK_ID}:{candidate_sha256}:{nonce}",
                ),
                development_split="blind_holdout",
            )
            image, _ = _pristine_qr(candidate)
            payload, _, _ = detector.detectAndDecode(
                cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
            )
            if payload == candidate.payload:
                selected.append(candidate)
                break
        else:
            raise RuntimeError(
                f"no deterministic decodable payload for {candidate.base_id}"
            )
    return tuple(selected)


def fresh_case_specs(candidate_sha256: str) -> tuple[CaseSpec, ...]:
    candidates = [
        (base, label)
        for base in fresh_base_specs(candidate_sha256)
        for label in ("clean", "adversarial", "tampered")
    ]
    candidates.sort(
        key=lambda item: hashlib.sha256(
            f"{PACK_ID}:{candidate_sha256}:{item[0].base_id}:{item[1]}".encode()
        ).hexdigest()
    )
    return tuple(
        CaseSpec(
            case_id=(
                f"R7B-{index:02d}-"
                + hashlib.sha256(
                    f"{candidate_sha256}:{base.base_id}:{label}".encode()
                )
                .hexdigest()[:6]
                .upper()
            ),
            label=label,
            label_code="R7B",
            base=base,
            attack_profile="screen_robust_alternate",
        )
        for index, (base, label) in enumerate(candidates, start=1)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--app-plan", type=Path, default=DEFAULT_APP_PLAN)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--candidate-artifact", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--victim-checkpoint", type=Path, default=DEFAULT_VICTIM)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidate = args.candidate_artifact.resolve(strict=True)
    candidate_sha256 = _sha256(candidate)
    result = build_pack(
        args.output.resolve(),
        args.app_plan.resolve(),
        args.archive.resolve(),
        args.victim_checkpoint.resolve(strict=True),
        specs=fresh_case_specs(candidate_sha256),
        pack_id=PACK_ID,
        evidence_role="blind_holdout",
        candidate_model_sha256=candidate_sha256,
        readme_text=(
            "# Structural r07 fresh blind acceptance pack\n\n"
            "This active pack is bound to the frozen candidate SHA-256 shown in "
            "MANIFEST.json. Capture every opaque card once at screen 80% in the "
            "supplied order. CAPTURE_ORDER.csv exposes only opaque IDs and card "
            "paths. Before capture, do not open MANIFEST.json, "
            "DIAGNOSTIC_CAPTURE_PLAN.json or raw_references; do not skip cases, "
            "tune thresholds or score the candidate.\n\n"
            "Install the sibling QRGuard_Diagnostic_R07_Fresh_Blind_v1.apk and "
            "open QRGuard Capture. Keep the display viewer and brightness fixed, "
            "open one cards/R7B-*.png at a time in CAPTURE_ORDER.csv order, and "
            "select the matching opaque ID in the app. Arm one session and wait "
            "for its automatic five-frame burst to reach completion before moving "
            "to the next card. Export one ZIP only after the app shows 48/48 "
            "sessions, then return that ZIP without opening or scoring it.\n"
        ),
    )
    print(
        json.dumps(
            {
                "cases": result["manifest"]["case_count"],
                "candidate_model_sha256": candidate_sha256,
                "archive": result["archive"],
                "archive_sha256": result["archive_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
