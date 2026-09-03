"""Audit QR layout coverage that aggregate Structural metrics can hide.

The promoted r01 holdout was balanced by class and acquisition condition, but
not by QR Version, mask or payload length.  This audit recovers those attributes
from paired Gallery references without persisting decoded payload text, then
combines them with the SEM-11 low-Version physical screen-camera evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = (
    ROOT / "ml_training/configs/structural-coverage-gates-2026.09-r01.json"
)
DEFAULT_RUNTIME_MANIFEST = ROOT / "data/runtime_captures/manifest_v3.csv"
DEFAULT_RUNTIME_ROOT = ROOT / "data/runtime_captures"
DEFAULT_PLAN = ROOT / "app/assets/capture/sem11_root_cause_capture_plan.json"
DEFAULT_DIGITAL = (
    ROOT
    / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r01/M2_AUTOMATED_RESULTS_LOCAL.json"
)
DEFAULT_DEMO_BRANCH_AUDIT = (
    ROOT
    / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r01/M1_BRANCH_AUDIT_LOCAL.json"
)
DEFAULT_PHYSICAL_FRAMES = (
    ROOT
    / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r01/"
    "M2_PHYSICAL_SCREEN_80/FRAME_RESULTS.csv"
)
DEFAULT_PRODUCTION_SESSIONS = (
    ROOT
    / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r01/"
    "M2_PRODUCTION_POLICY_SCREEN_80/SESSION_RESULTS.csv"
)
DEFAULT_OUTPUT = (
    ROOT
    / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r01/M4_QR_COVERAGE_AUDIT"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_from_module_count(module_count: int) -> int:
    if module_count < 21 or (module_count - 17) % 4:
        raise ValueError(f"invalid QR module count: {module_count}")
    version = (module_count - 17) // 4
    if version not in range(1, 41):
        raise ValueError(f"invalid QR Version derived from {module_count}")
    return version


def _format_code(data: int) -> int:
    remainder = data
    for _ in range(10):
        remainder = (remainder << 1) ^ (-(remainder >> 9 & 1) & 0x537)
    return ((data << 10) | remainder) ^ 0x5412


_VALID_FORMAT_CODES = {_format_code(data): data for data in range(32)}


def mask_from_straight_qr(straight: Any) -> int:
    """Read the BCH-protected mask number from OpenCV's straight module grid."""

    if straight is None or len(straight.shape) != 2 or straight.shape[0] != straight.shape[1]:
        raise ValueError("straight QR matrix must be square grayscale")
    side = int(straight.shape[0])
    version_from_module_count(side)
    positions = (
        [(index, 8) for index in range(6)]
        + [(7, 8), (8, 8), (8, 7)]
        + [(8, 14 - index) for index in range(9, 15)]
    )
    observed = sum(
        int(straight[y, x] < 128) << bit
        for bit, (y, x) in enumerate(positions)
    )
    candidate, distance = min(
        (
            (data, (observed ^ code).bit_count())
            for code, data in _VALID_FORMAT_CODES.items()
        ),
        key=lambda item: item[1],
    )
    if distance > 3:
        raise ValueError(f"QR format information exceeds BCH correction: {distance}")
    return candidate & 0b111


def _bucket(value: int, definitions: Iterable[dict[str, Any]], low: str, high: str) -> str:
    for definition in definitions:
        if int(definition[low]) <= value <= int(definition[high]):
            return str(definition["id"])
    return "outside_contract"


def inspect_qr_reference(path: Path) -> dict[str, int]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"unreadable reference image: {path}")
    payload, _, straight = cv2.QRCodeDetector().detectAndDecode(image)
    if not payload or straight is None:
        raise ValueError(f"reference QR could not be decoded: {path}")
    modules = int(straight.shape[0])
    return {
        "module_count": modules,
        "qr_version": version_from_module_count(modules),
        "mask_pattern": mask_from_straight_qr(straight),
        "payload_utf8_bytes": len(payload.encode("utf-8")),
    }


def load_runtime_holdout(
    manifest_path: Path, runtime_root: Path, config: dict[str, Any]
) -> list[dict[str, Any]]:
    with manifest_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    selected = [
        row
        for row in rows
        if row["split"] == "test"
        and row["image_source"] == "gallery"
        and row["is_authoritative"].lower() == "true"
    ]
    records: list[dict[str, Any]] = []
    seen_groups: set[str] = set()
    for row in selected:
        group = row["paired_group"]
        if not group or group in seen_groups:
            raise ValueError(f"invalid or duplicate paired holdout group: {group!r}")
        seen_groups.add(group)
        path = runtime_root / row["sample_path"]
        metadata_path = path.parent / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expected_capture_hash = str(metadata.get("offline_crop_sha256", "")).lower()
        actual_capture_hash = _sha256(path)
        if expected_capture_hash and actual_capture_hash != expected_capture_hash:
            raise ValueError(f"runtime reference hash mismatch: {row['sample_path']}")
        structure = inspect_qr_reference(path)
        records.append(
            {
                "paired_group": group,
                "label": row["label"],
                "source_sha256": actual_capture_hash,
                "capture_hash_verified": bool(expected_capture_hash),
                **structure,
                "version_band": _bucket(
                    structure["qr_version"],
                    config["version_bands"],
                    "minimum_version",
                    "maximum_version",
                ),
                "payload_length_bin": _bucket(
                    structure["payload_utf8_bytes"],
                    config["payload_length_bins"],
                    "minimum_utf8_bytes",
                    "maximum_utf8_bytes",
                ),
            }
        )
    return records


def summarize_runtime(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_class: dict[str, Any] = {}
    for label in sorted({str(row["label"]) for row in records}):
        chosen = [row for row in records if row["label"] == label]
        by_class[label] = {
            "independent_test_groups": len(chosen),
            "versions": dict(sorted(Counter(row["qr_version"] for row in chosen).items())),
            "module_counts": dict(
                sorted(Counter(row["module_count"] for row in chosen).items())
            ),
            "version_bands": dict(Counter(row["version_band"] for row in chosen)),
            "masks": dict(sorted(Counter(row["mask_pattern"] for row in chosen).items())),
            "payload_length_bins": dict(
                Counter(row["payload_length_bin"] for row in chosen)
            ),
            "payload_utf8_bytes_min": min(row["payload_utf8_bytes"] for row in chosen),
            "payload_utf8_bytes_max": max(row["payload_utf8_bytes"] for row in chosen),
        }
    return {
        "groups": len(records),
        "capture_hash_verified_groups": sum(
            bool(row.get("capture_hash_verified")) for row in records
        ),
        "by_class": by_class,
    }


def coverage_failures(summary: dict[str, Any], config: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    minimum_band = int(config["minimum_independent_test_groups_per_class_version_band"])
    minimum_mask = int(config["minimum_independent_test_groups_per_class_mask"])
    minimum_length = int(
        config["minimum_independent_test_groups_per_class_payload_length_bin"]
    )
    for label in config["required_classes"]:
        observed = summary["by_class"].get(label, {})
        bands = observed.get("version_bands", {})
        masks = observed.get("masks", {})
        lengths = observed.get("payload_length_bins", {})
        for definition in config["version_bands"]:
            bucket = definition["id"]
            count = int(bands.get(bucket, 0))
            if count < minimum_band:
                failures.append(
                    f"{label}: version band {bucket} has {count}, requires {minimum_band}"
                )
        for mask in range(8):
            count = int(masks.get(mask, masks.get(str(mask), 0)))
            if count < minimum_mask:
                failures.append(
                    f"{label}: mask {mask} has {count}, requires {minimum_mask}"
                )
        for definition in config["payload_length_bins"]:
            bucket = definition["id"]
            count = int(lengths.get(bucket, 0))
            if count < minimum_length:
                failures.append(
                    f"{label}: payload bin {bucket} has {count}, requires {minimum_length}"
                )
    return failures


def _physical_summary(
    plan_path: Path, frame_results_path: Path, session_results_path: Path
) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cases = {row["case_id"]: row for row in plan["cases"]}
    with frame_results_path.open(newline="", encoding="utf-8-sig") as handle:
        frames = list(csv.DictReader(handle))
    with session_results_path.open(newline="", encoding="utf-8-sig") as handle:
        sessions = list(csv.DictReader(handle))
    by_case: list[dict[str, Any]] = []
    for case_id in sorted(cases):
        case_frames = [row for row in frames if row["case_id"] == case_id]
        case_sessions = [row for row in sessions if row["case_id"] == case_id]
        scores = sorted(float(row["p_structural_effective"]) for row in case_frames)
        by_case.append(
            {
                "case_id": case_id,
                "family": cases[case_id]["metadata"]["family"],
                "qr_version": cases[case_id]["metadata"]["qr_version"],
                "module_count": cases[case_id]["metadata"]["module_count"],
                "mask_pattern": cases[case_id]["metadata"]["mask_pattern"],
                "frames": len(case_frames),
                "sessions": len(case_sessions),
                "p_structural_min": min(scores),
                "p_structural_median": scores[len(scores) // 2],
                "p_structural_max": max(scores),
                "production_outcomes": dict(
                    Counter(row["outcome"] for row in case_sessions)
                ),
            }
        )
    false_blocks = sum(row["outcome"] == "false_block" for row in sessions)
    rescans = sum(row["outcome"] == "rescan" for row in sessions)
    forced_masks = [row for row in by_case if row["family"] == "forced_mask"]
    medians = [row["p_structural_median"] for row in forced_masks]
    return {
        "campaign_id": plan["campaign_id"],
        "sessions": len(sessions),
        "frames": len(frames),
        "production_clean_false_block_rate": false_blocks / len(sessions),
        "production_rescan_rate": rescans / len(sessions),
        "physical_forced_mask_probability_span": max(medians) - min(medians),
        "by_case": by_case,
    }


def _digital_summary(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    masks = [row for row in report["results"] if row["case_id"].startswith("RC-MASK-")]
    scores = [float(row["gallery"]["p_structural"]) for row in masks]
    false_blocks = sum(row["gallery"]["verdict"] == "blocked" for row in masks)
    return {
        "forced_mask_cases": len(masks),
        "clean_false_blocks": false_blocks,
        "forced_mask_probability_span": max(scores) - min(scores),
    }


def _demo_branch_summary(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    summary = report["summary"]
    return {
        "requests": int(summary["request_count"]),
        "masked_branch_errors": int(summary["masked_branch_errors"]),
        "gate_passed": bool(summary["gate_passed"]),
    }


def build_audit(
    config: dict[str, Any],
    runtime_records: list[dict[str, Any]],
    physical: dict[str, Any],
    digital: dict[str, Any],
    demo_branch: dict[str, Any],
) -> dict[str, Any]:
    runtime = summarize_runtime(runtime_records)
    failures = coverage_failures(runtime, config)
    maximum_fpr = float(config["maximum_clean_camera_false_block_rate_per_version_band"])
    if physical["production_clean_false_block_rate"] > maximum_fpr:
        failures.append(
            "low-Version physical clean false-Blocked rate "
            f"{physical['production_clean_false_block_rate']:.4f} exceeds {maximum_fpr:.4f}"
        )
    maximum_span = float(config["maximum_clean_layout_probability_span"])
    for name, value in (
        ("digital forced-mask", digital["forced_mask_probability_span"]),
        ("physical forced-mask", physical["physical_forced_mask_probability_span"]),
    ):
        if value > maximum_span:
            failures.append(f"{name} probability span {value:.4f} exceeds {maximum_span:.4f}")
    maximum_masked = int(config["maximum_masked_demo_branch_errors"])
    if demo_branch["masked_branch_errors"] > maximum_masked:
        failures.append(
            "demo masked branch errors "
            f"{demo_branch['masked_branch_errors']} exceed {maximum_masked}"
        )
    return {
        "schema_version": 1,
        "policy_id": config["policy_id"],
        "gate_passed": not failures,
        "promotion_blocked": bool(failures),
        "gate_failures": failures,
        "runtime_exact_app_test_structure": runtime,
        "sem11_digital_controls": digital,
        "sem11_physical_screen_80": physical,
        "demo_branch_audit": demo_branch,
        "interpretation": {
            "primary_root_cause": (
                "exact-app holdout lacks low/medium QR Versions; the model also "
                "responds strongly to legal mask/layout changes"
            ),
            "not_payload_length_alone": (
                "same-length layouts diverge and forced Version 4 also fails after "
                "physical screen capture"
            ),
            "consensus_limit": (
                "temporal consensus cannot correct a systematic content/domain bias"
            ),
        },
    }


def _markdown(audit: dict[str, Any]) -> str:
    runtime = audit["runtime_exact_app_test_structure"]
    physical = audit["sem11_physical_screen_80"]
    digital = audit["sem11_digital_controls"]
    lines = [
        "# QR structural coverage audit",
        "",
        f"Policy: `{audit['policy_id']}`",
        "",
        (
            f"Gate passed: **{audit['gate_passed']}**; promotion blocked: "
            f"**{audit['promotion_blocked']}**."
        ),
        "",
        "## Existing exact-app test coverage",
        "",
        "| Class | Groups | Versions | Masks | Payload byte range |",
        "|---|---:|---|---|---:|",
    ]
    for label, row in runtime["by_class"].items():
        lines.append(
            f"| {label} | {row['independent_test_groups']} | {row['versions']} | "
            f"{row['masks']} | {row['payload_utf8_bytes_min']}-"
            f"{row['payload_utf8_bytes_max']} |"
        )
    lines.extend(
        [
            "",
            "## New low-Version evidence",
            "",
            (
                "- Physical production-policy clean false-Blocked rate: "
                f"{physical['production_clean_false_block_rate']:.1%}."
            ),
            f"- Physical rescan rate: {physical['production_rescan_rate']:.1%}.",
            (
                "- Demo masked branch errors (SEM-05-style): "
                f"{audit['demo_branch_audit']['masked_branch_errors']}."
            ),
            (
                "- Digital forced-mask probability span: "
                f"{digital['forced_mask_probability_span']:.3f}."
            ),
            (
                "- Physical forced-mask probability span: "
                f"{physical['physical_forced_mask_probability_span']:.3f}."
            ),
            "",
            "## Blocking failures",
            "",
        ]
    )
    lines.extend(f"- {failure}" for failure in audit["gate_failures"])
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            (
                "The failure is not explained by 29x29 or payload length alone. The "
                "existing exact-app test set is concentrated in high-Version QR layouts; "
                "legal mask/layout differences already move the clean score materially, "
                "and screen-camera artefacts amplify that content shortcut. Multi-frame "
                "voting repeats the bias and therefore is not a sufficient fix."
            ),
            "",
            (
                "The next Structural candidate must satisfy every Version band, every "
                "mask and every payload-length bin for all three classes, then pass the "
                "branch-level demo audit before promotion."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--digital", type=Path, default=DEFAULT_DIGITAL)
    parser.add_argument(
        "--demo-branch-audit", type=Path, default=DEFAULT_DEMO_BRANCH_AUDIT
    )
    parser.add_argument("--physical-frames", type=Path, default=DEFAULT_PHYSICAL_FRAMES)
    parser.add_argument(
        "--production-sessions", type=Path, default=DEFAULT_PRODUCTION_SESSIONS
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-fail", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    records = load_runtime_holdout(args.runtime_manifest, args.runtime_root, config)
    physical = _physical_summary(args.plan, args.physical_frames, args.production_sessions)
    digital = _digital_summary(args.digital)
    demo_branch = _demo_branch_summary(args.demo_branch_audit)
    audit = build_audit(config, records, physical, digital, demo_branch)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "AUDIT.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "SUMMARY.md").write_text(_markdown(audit), encoding="utf-8")
    print(json.dumps({"gate_passed": audit["gate_passed"], "failures": len(audit["gate_failures"])}, indent=2))
    if audit["promotion_blocked"] and not args.allow_fail:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
