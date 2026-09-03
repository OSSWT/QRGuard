"""Audit whether digital adversarial labels survive a physical screen capture.

The coverage packs verify attacks before display.  This audit adds the missing
post-capture check: it compares each adversarial burst with the clean burst for
the same QR identity under the frozen ImageNet victim.  It does not score or
modify the QRGuard candidate and never stores decoded payload text.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_live_camera_diagnostic import ValidatedFrame, validate_archive
from scripts.prepare_scoped_capture_references import (
    ATTACK_SIZE,
    _eot_views,
    _load_victim,
    _normalise,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return document


def _load_reference_manifest(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        document = json.loads(archive.read("MANIFEST.json").decode("utf-8"))
    if not isinstance(document, dict):
        raise TypeError("reference MANIFEST.json must be an object")
    return document


def _predict_views(victim: Any, frame: ValidatedFrame) -> list[int]:
    import torch

    image = (
        Image.open(io.BytesIO(frame.crop_png))
        .convert("RGB")
        .resize((ATTACK_SIZE, ATTACK_SIZE), Image.Resampling.BILINEAR)
    )
    array = np.asarray(image, dtype=np.float32) / 255.0
    tensor = torch.from_numpy(array.transpose(2, 0, 1)).unsqueeze(0)
    with torch.no_grad():
        predictions = victim(_normalise(_eot_views(tensor))).argmax(1)
    return [int(value) for value in predictions.tolist()]


def _wilson_lower_bound(successes: int, trials: int, z: float = 1.9599639845) -> float:
    if trials <= 0:
        return 0.0
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    centre = proportion + z * z / (2.0 * trials)
    radius = z * math.sqrt(
        proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials)
    )
    return max(0.0, (centre - radius) / denominator)


def _binomial_probability_at_least(
    trials: int, required_successes: int, success_probability: float
) -> float:
    if required_successes <= 0:
        return 1.0
    if trials < required_successes or success_probability <= 0:
        return 0.0
    if success_probability >= 1:
        return 1.0
    return sum(
        math.comb(trials, successes)
        * success_probability**successes
        * (1.0 - success_probability) ** (trials - successes)
        for successes in range(required_successes, trials + 1)
    )


def _required_planned_attacks(
    success_probability: float,
    required_survivors: int,
    target_probability: float,
    maximum_trials: int = 1000,
) -> int | None:
    for trials in range(required_survivors, maximum_trials + 1):
        if (
            _binomial_probability_at_least(
                trials, required_survivors, success_probability
            )
            >= target_probability
        ):
            return trials
    return None


def summarise_survival(
    rows: list[dict[str, Any]],
    *,
    minimum_survivors_per_band: int = 5,
    planning_confidence: float = 0.95,
) -> dict[str, Any]:
    bands = ("low_v1_v3", "medium_v4_v6", "high_v7_plus")
    by_band: dict[str, Any] = {}
    for band in bands:
        selected = [row for row in rows if row.get("version_band") == band]
        verified = sum(
            row.get("physical_attack_survival_verified") is True for row in selected
        )
        observed_rate = verified / len(selected) if selected else 0.0
        lower_bound = _wilson_lower_bound(verified, len(selected))
        by_band[band] = {
            "planned_attacks": len(selected),
            "verified_surviving_attacks": verified,
            "verified_survival_rate": observed_rate,
            "wilson_95_lower_bound": lower_bound,
            "minimum_required_survivors": minimum_survivors_per_band,
            "gate_passed": verified >= minimum_survivors_per_band,
            "planned_attacks_for_target_using_observed_rate": (
                _required_planned_attacks(
                    observed_rate,
                    minimum_survivors_per_band,
                    planning_confidence,
                )
            ),
            "planned_attacks_for_target_using_wilson_lower_bound": (
                _required_planned_attacks(
                    lower_bound,
                    minimum_survivors_per_band,
                    planning_confidence,
                )
            ),
        }
    profiles: dict[str, Any] = {}
    for profile in sorted({str(row.get("attack_profile", "unknown")) for row in rows}):
        selected = [row for row in rows if str(row.get("attack_profile", "unknown")) == profile]
        verified = sum(
            row.get("physical_attack_survival_verified") is True for row in selected
        )
        profiles[profile] = {
            "planned_attacks": len(selected),
            "verified_surviving_attacks": verified,
            "verified_survival_rate": verified / len(selected) if selected else 0.0,
        }
    band_profiles: dict[str, Any] = {}
    for band in bands:
        band_profiles[band] = {}
        for profile in profiles:
            selected = [
                row
                for row in rows
                if row.get("version_band") == band
                and str(row.get("attack_profile", "unknown")) == profile
            ]
            verified = sum(
                row.get("physical_attack_survival_verified") is True
                for row in selected
            )
            band_profiles[band][profile] = {
                "planned_attacks": len(selected),
                "verified_surviving_attacks": verified,
                "verified_survival_rate": (
                    verified / len(selected) if selected else 0.0
                ),
            }
    return {
        "minimum_survivors_per_version_band": minimum_survivors_per_band,
        "planning_target_probability": planning_confidence,
        "gate_passed": all(row["gate_passed"] for row in by_band.values()),
        "by_version_band": by_band,
        "by_attack_profile": profiles,
        "by_version_band_and_attack_profile": band_profiles,
        "planning_note": (
            "Planning counts estimate capture volume only; physical survival must "
            "still be verified and candidate scoring must remain separate."
        ),
    }


def audit(
    frames: list[ValidatedFrame],
    plan: dict[str, Any],
    reference_manifest: dict[str, Any],
    victim_checkpoint: Path,
    minimum_survivors_per_band: int = 5,
    planning_confidence: float = 0.95,
) -> dict[str, Any]:
    cases = {str(row["case_id"]): row for row in plan["cases"]}
    references = {str(row["case_id"]): row for row in reference_manifest["cases"]}
    if set(cases) != set(references):
        raise ValueError("capture plan and reference manifest cases differ")
    expected_victim_hash = str(reference_manifest["victim_checkpoint_sha256"])
    actual_victim_hash = _sha256(victim_checkpoint)
    if actual_victim_hash != expected_victim_hash:
        raise ValueError("victim checkpoint hash does not match reference manifest")

    frames_by_case: dict[str, list[ValidatedFrame]] = {}
    for frame in frames:
        frames_by_case.setdefault(frame.case_id, []).append(frame)
    victim = _load_victim(victim_checkpoint)
    predictions = {
        case_id: [
            prediction
            for frame in sorted(rows, key=lambda item: item.frame_index)
            for prediction in _predict_views(victim, frame)
        ]
        for case_id, rows in frames_by_case.items()
    }

    by_base: dict[str, dict[str, list[str]]] = {}
    for case_id, case in cases.items():
        base_id = str(case["metadata"]["base_identity"])
        label = str(case["ground_truth"])
        by_base.setdefault(base_id, {}).setdefault(label, []).append(case_id)

    rows: list[dict[str, Any]] = []
    for base_id, labels in sorted(by_base.items()):
        if "clean" not in labels or "adversarial" not in labels:
            raise ValueError(f"missing clean/adversarial pair for {base_id}")
        if len(labels["clean"]) != 1:
            raise ValueError(f"expected one clean reference for {base_id}")
        clean_case = labels["clean"][0]
        clean_predictions = predictions[clean_case]
        baseline_label, baseline_count = Counter(clean_predictions).most_common(1)[0]
        clean_consistency = baseline_count / len(clean_predictions)
        clean_self_flip_rate = 1.0 - clean_consistency
        for adversarial_case in sorted(labels["adversarial"]):
            adversarial_predictions = predictions[adversarial_case]
            paired_success_rate = sum(
                value != baseline_label for value in adversarial_predictions
            ) / len(adversarial_predictions)
            survival_margin = paired_success_rate - clean_self_flip_rate

            reference = references[adversarial_case]
            digital_baseline = int(reference["victim_baseline_class"])
            clean_digital_consistency = sum(
                value == digital_baseline for value in clean_predictions
            ) / len(clean_predictions)
            digital_baseline_success_rate = sum(
                value != digital_baseline for value in adversarial_predictions
            ) / len(adversarial_predictions)
            verified = (
                clean_consistency >= 0.5
                and paired_success_rate >= 0.5
                and survival_margin >= 0.25
            )
            metadata = cases[adversarial_case]["metadata"]
            rows.append(
                {
                    "base_identity": base_id,
                    "qr_version": int(metadata["qr_version"]),
                    "version_band": str(metadata["version_band"]),
                    "mask_pattern": int(metadata["mask_pattern"]),
                    "attack_profile": str(metadata.get("attack_profile", "unknown")),
                    "clean_case_id": clean_case,
                    "adversarial_case_id": adversarial_case,
                    "views_per_class": len(clean_predictions),
                    "physical_clean_baseline_label": baseline_label,
                    "physical_clean_baseline_consistency": clean_consistency,
                    "physical_clean_self_flip_rate": clean_self_flip_rate,
                    "paired_physical_attack_success_rate": paired_success_rate,
                    "paired_physical_attack_success_margin": survival_margin,
                    "digital_baseline_label": digital_baseline,
                    "physical_clean_digital_baseline_consistency": (
                        clean_digital_consistency
                    ),
                    "physical_attack_digital_baseline_success_rate": (
                        digital_baseline_success_rate
                    ),
                    "physical_attack_survival_verified": verified,
                }
            )

    verified_count = sum(row["physical_attack_survival_verified"] for row in rows)
    coverage = summarise_survival(
        rows,
        minimum_survivors_per_band=minimum_survivors_per_band,
        planning_confidence=planning_confidence,
    )
    return {
        "schema_version": 1,
        "evaluation": "paired_post_capture_adversarial_survival",
        "campaign_id": plan.get("campaign_id"),
        "victim_checkpoint_sha256": actual_victim_hash,
        "frames": len(frames),
        "paired_identities": len(by_base),
        "adversarial_pairs": len(rows),
        "survival_rule": {
            "minimum_physical_clean_baseline_consistency": 0.5,
            "minimum_paired_attack_success_rate": 0.5,
            "minimum_success_margin_over_clean_instability": 0.25,
        },
        "verified_surviving_attacks": verified_count,
        "verified_survival_rate": verified_count / len(rows) if rows else 0.0,
        "coverage_gate": coverage,
        "rows": rows,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--reference-pack", type=Path, required=True)
    parser.add_argument("--victim-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-survivors-per-band", type=int, default=5)
    parser.add_argument("--planning-confidence", type=float, default=0.95)
    parser.add_argument("--require-coverage-gate", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive = args.archive.resolve(strict=True)
    plan_path = args.plan.resolve(strict=True)
    reference_pack = args.reference_pack.resolve(strict=True)
    victim_checkpoint = args.victim_checkpoint.resolve(strict=True)
    frames = validate_archive(archive, plan_path)
    report = audit(
        frames,
        _load_json(plan_path),
        _load_reference_manifest(reference_pack),
        victim_checkpoint,
        minimum_survivors_per_band=args.minimum_survivors_per_band,
        planning_confidence=args.planning_confidence,
    )
    report["source_archive_sha256"] = _sha256(archive)
    report["reference_pack_sha256"] = _sha256(reference_pack)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "ANALYSIS.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(output / "PAIRED_RESULTS.csv", report["rows"])
    print(
        json.dumps(
            {
                "paired_identities": report["paired_identities"],
                "verified_surviving_attacks": report["verified_surviving_attacks"],
                "verified_survival_rate": report["verified_survival_rate"],
                "coverage_gate_passed": report["coverage_gate"]["gate_passed"],
            },
            indent=2,
        )
    )
    if args.require_coverage_gate and not report["coverage_gate"]["gate_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
