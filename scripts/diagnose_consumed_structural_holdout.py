"""Diagnose frame-level instability in a consumed Structural capture.

This tool is intentionally post-unblinding.  It first validates the collector
archive, then joins its acquisition telemetry to an existing all-frame replay.
It never scores a model, changes a threshold, or makes evidence promotion-
eligible.  Raw decoded payload text is neither expected nor emitted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_live_camera_diagnostic import validate_archive


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: object) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _rank(values: list[float]) -> list[float]:
    """Return average ranks, including deterministic handling of ties."""

    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for index, _ in ordered[start:end]:
            ranks[index] = rank
        start = end
    return ranks


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum(
        (x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True)
    )
    left_scale = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_scale = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    if left_scale == 0 or right_scale == 0:
        return None
    return numerator / (left_scale * right_scale)


def _spearman(left: list[float], right: list[float]) -> float | None:
    return _pearson(_rank(left), _rank(right))


def _side_ratio(corners: list[float]) -> float:
    points = list(zip(corners[::2], corners[1::2], strict=True))
    lengths = [
        math.dist(first, second)
        for first, second in zip(points, points[1:] + points[:1], strict=True)
    ]
    minimum = min(lengths)
    return max(lengths) / minimum if minimum > 0 else math.inf


def _archive_telemetry(archive_path: Path, plan_path: Path) -> list[dict[str, Any]]:
    validated = validate_archive(archive_path, plan_path)
    validated_by_hash = {frame.crop_sha256: frame for frame in validated}
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("archive_manifest.json"))
        for session in manifest["sessions"]:
            metadata_name = f"{session['base_path']}/metadata.json"
            metadata = json.loads(archive.read(metadata_name))
            case = metadata["case_metadata"]
            for frame in metadata["frames"]:
                crop_hash = str(frame["crop_sha256"])
                checked = validated_by_hash.get(crop_hash)
                if checked is None:
                    raise ValueError(f"validated frame is missing for {crop_hash}")
                raw_quality = frame["raw_acquisition_quality"]
                crop_quality = frame["structural_crop_quality"]
                corners = [float(value) for value in frame["corner_coordinates"]]
                rows.append(
                    {
                        "session_id": metadata["diagnostic_session_id"],
                        "case_id": metadata["case_id"],
                        "ground_truth": metadata["ground_truth"],
                        "frame_index": int(frame["frame_index"]),
                        "crop_sha256": crop_hash,
                        "qr_version": int(case["qr_version"]),
                        "module_count": int(case["module_count"]),
                        "mask_pattern": int(case["mask_pattern"]),
                        "version_band": case["version_band"],
                        "payload_length_bin": case["payload_length_bin"],
                        "payload_utf8_bytes": int(case["payload_utf8_bytes"]),
                        "crop_width": checked.crop_width,
                        "crop_height": checked.crop_height,
                        "observed_pixels_per_module": float(
                            frame["observed_pixels_per_module"]
                        ),
                        "qr_coverage": checked.qr_coverage,
                        "quadrilateral_side_ratio": _side_ratio(corners),
                        "exposure_compensation_supported": bool(
                            frame["exposure_compensation_supported"]
                        ),
                        "exposure_compensation_ev": _float(
                            frame.get("exposure_compensation_ev")
                        ),
                        "exposure_adjusted_during_session": bool(
                            frame["exposure_adjusted_during_session"]
                        ),
                        "raw_quality_status": raw_quality["status"],
                        "raw_quality_conditions": ";".join(
                            str(value) for value in raw_quality["conditions"]
                        ),
                        "raw_mean_luminance": float(raw_quality["mean_luminance"]),
                        "raw_p05_luminance": float(raw_quality["p05_luminance"]),
                        "raw_p95_luminance": float(raw_quality["p95_luminance"]),
                        "raw_dynamic_range": float(raw_quality["dynamic_range"]),
                        "raw_laplacian_variance": float(
                            raw_quality["laplacian_variance"]
                        ),
                        "raw_dark_fraction": float(raw_quality["dark_fraction"]),
                        "raw_bright_fraction": float(
                            raw_quality["bright_fraction"]
                        ),
                        "structural_quality_status": crop_quality["status"],
                        "structural_mean_luminance": float(
                            crop_quality["mean_luminance"]
                        ),
                        "structural_dynamic_range": float(
                            crop_quality["dynamic_range"]
                        ),
                        "structural_laplacian_variance": float(
                            crop_quality["laplacian_variance"]
                        ),
                        "structural_dark_fraction": float(
                            crop_quality["dark_fraction"]
                        ),
                        "structural_bright_fraction": float(
                            crop_quality["bright_fraction"]
                        ),
                    }
                )
    if len(rows) != len(validated):
        raise ValueError("telemetry frame count differs from validated archive")
    return rows


def _join_frame_results(
    telemetry: list[dict[str, Any]], frame_results: list[dict[str, str]]
) -> list[dict[str, Any]]:
    results = {str(row["crop_sha256"]): row for row in frame_results}
    if len(results) != len(frame_results):
        raise ValueError("frame replay contains duplicate crop hashes")
    joined: list[dict[str, Any]] = []
    for row in telemetry:
        replay = results.get(str(row["crop_sha256"]))
        if replay is None:
            raise ValueError(f"replay result is missing for {row['crop_sha256']}")
        for key in ("session_id", "case_id", "ground_truth"):
            if str(replay[key]) != str(row[key]):
                raise ValueError(f"frame replay {key} mismatch for {row['crop_sha256']}")
        if int(replay["frame_index"]) != row["frame_index"]:
            raise ValueError(f"frame replay index mismatch for {row['crop_sha256']}")
        joined.append(
            {
                **row,
                "payload_decode_status": replay["payload_decode_status"],
                "payload_hash_matches": replay["payload_hash_matches"].lower()
                == "true",
                "quality_status": replay["quality_status"],
                "quality_conditions": replay["quality_conditions"],
                "p_structural_raw": _float(replay["p_structural_raw"]),
                "p_structural_effective": _float(
                    replay["p_structural_effective"]
                ),
                "structural_type": replay["structural_type"],
                "verdict": replay["verdict"],
                "risk_score": int(replay["risk_score"]),
            }
        )
    if len(joined) != len(frame_results):
        raise ValueError("archive and replay frame sets differ")
    return joined


def build_report(
    rows: list[dict[str, Any]],
    session_results: list[dict[str, str]],
    reference_span_limit: float,
) -> dict[str, Any]:
    clean = [row for row in rows if row["ground_truth"] == "clean"]
    clean_scores = [
        float(row["p_structural_raw"])
        for row in clean
        if row["p_structural_raw"] is not None
    ]
    if not clean_scores:
        raise ValueError("no scored clean frames")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in clean:
        grouped[str(row["case_id"])].append(row)

    cases: list[dict[str, Any]] = []
    for case_id, selected in grouped.items():
        scores = sorted(
            float(row["p_structural_raw"])
            for row in selected
            if row["p_structural_raw"] is not None
        )
        first = selected[0]
        cases.append(
            {
                "case_id": case_id,
                "qr_version": first["qr_version"],
                "module_count": first["module_count"],
                "mask_pattern": first["mask_pattern"],
                "version_band": first["version_band"],
                "payload_length_bin": first["payload_length_bin"],
                "payload_utf8_bytes": first["payload_utf8_bytes"],
                "frames": len(selected),
                "p_structural_min": min(scores),
                "p_structural_median": statistics.median(scores),
                "p_structural_max": max(scores),
                "p_structural_range": max(scores) - min(scores),
                "blocked_frames": sum(row["verdict"] == "blocked" for row in selected),
                "non_safe_frames": sum(row["verdict"] != "safe" for row in selected),
                "mean_pixels_per_module": _mean(
                    [float(row["observed_pixels_per_module"]) for row in selected]
                ),
                "mean_luminance": _mean(
                    [float(row["raw_mean_luminance"]) for row in selected]
                ),
                "mean_dynamic_range": _mean(
                    [float(row["raw_dynamic_range"]) for row in selected]
                ),
            }
        )
    cases.sort(key=lambda row: row["p_structural_median"], reverse=True)
    global_median_minimum = min(row["p_structural_median"] for row in cases)
    global_frame_minimum = min(clean_scores)
    for row in cases:
        row["median_exceeds_reference_span_from_clean_median_minimum"] = (
            row["p_structural_median"] - global_median_minimum
            > reference_span_limit
        )
        row["maximum_exceeds_reference_span_from_clean_frame_minimum"] = (
            row["p_structural_max"] - global_frame_minimum > reference_span_limit
        )

    telemetry_fields = (
        "raw_mean_luminance",
        "raw_p05_luminance",
        "raw_p95_luminance",
        "raw_dynamic_range",
        "raw_laplacian_variance",
        "raw_dark_fraction",
        "raw_bright_fraction",
        "observed_pixels_per_module",
        "qr_coverage",
        "quadrilateral_side_ratio",
    )
    correlations: dict[str, Any] = {}
    for field in telemetry_fields:
        paired = [
            (float(row[field]), float(row["p_structural_raw"]))
            for row in clean
            if row.get(field) is not None and row.get("p_structural_raw") is not None
        ]
        correlations[field] = {
            "frames": len(paired),
            "pearson": _pearson(
                [row[0] for row in paired], [row[1] for row in paired]
            ),
            "spearman": _spearman(
                [row[0] for row in paired], [row[1] for row in paired]
            ),
        }

    clean_sessions = [
        row for row in session_results if row.get("ground_truth") == "clean"
    ]
    false_block_frames = [
        {
            "case_id": row["case_id"],
            "frame_index": row["frame_index"],
            "p_structural_raw": row["p_structural_raw"],
            "raw_mean_luminance": row["raw_mean_luminance"],
            "raw_dynamic_range": row["raw_dynamic_range"],
            "raw_laplacian_variance": row["raw_laplacian_variance"],
            "observed_pixels_per_module": row["observed_pixels_per_module"],
            "qr_version": row["qr_version"],
            "mask_pattern": row["mask_pattern"],
        }
        for row in clean
        if row["verdict"] == "blocked"
    ]
    elevated = [
        row
        for row in cases
        if row["maximum_exceeds_reference_span_from_clean_frame_minimum"]
    ]
    elevated_correlations: dict[str, Any] = {}
    for case in elevated:
        selected = [row for row in clean if row["case_id"] == case["case_id"]]
        scores = [float(row["p_structural_raw"]) for row in selected]
        elevated_correlations[case["case_id"]] = {
            field: {
                "pearson": _pearson(
                    [float(row[field]) for row in selected], scores
                ),
                "spearman": _spearman(
                    [float(row[field]) for row in selected], scores
                ),
            }
            for field in telemetry_fields
        }
    consensus_safe = all(
        row.get("median_risk_verdict") == "safe" for row in clean_sessions
    )
    return {
        "schema_version": 1,
        "evidence_role": "consumed_holdout_diagnosis_only",
        "promotion_eligible": False,
        "threshold_or_model_mutation_performed": False,
        "reference_clean_layout_span_limit": reference_span_limit,
        "clean_frames": len(clean),
        "clean_sessions": len(clean_sessions),
        "clean_frame_false_blocks": len(false_block_frames),
        "clean_frame_false_block_rate": len(false_block_frames) / len(clean),
        "clean_session_consensus_safe": consensus_safe,
        "clean_session_false_blocks": sum(
            row.get("median_risk_verdict") == "blocked" for row in clean_sessions
        ),
        "elevated_clean_layouts": elevated,
        "false_block_frames": false_block_frames,
        "clean_cases_ranked": cases,
        "clean_frame_telemetry_correlations": correlations,
        "elevated_layout_within_case_correlations": elevated_correlations,
        "diagnostic_classification": (
            "single_frame_instability_rescued_by_temporal_consensus"
            if false_block_frames and consensus_safe
            else "session_level_instability"
            if not consensus_safe
            else "no_clean_false_block_observed"
        ),
        "interpretation_limits": [
            "Correlations are descriptive and do not establish causation.",
            "The capture is consumed development evidence and cannot promote a model.",
            "Layout, display, camera, luminance and module scale remain confounded in one pass.",
        ],
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Consumed Structural holdout diagnosis",
        "",
        "This report is development diagnosis only. It cannot be used for promotion.",
        "",
        "## Outcome",
        "",
        f"- Classification: `{report['diagnostic_classification']}`",
        f"- Clean session consensus safe: {report['clean_session_consensus_safe']}",
        f"- Clean single-frame false blocks: {report['clean_frame_false_blocks']}/{report['clean_frames']}",
        f"- Elevated clean layouts: {len(report['elevated_clean_layouts'])}",
        "- Model or threshold mutation: none",
        "",
        "## Elevated clean layouts",
        "",
        "| Case | Version | Modules | Mask | Payload bytes | p min / median / max | Blocked frames |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["elevated_clean_layouts"]:
        lines.append(
            f"| {row['case_id']} | {row['qr_version']} | {row['module_count']} | "
            f"{row['mask_pattern']} | {row['payload_utf8_bytes']} | "
            f"{row['p_structural_min']:.3f} / {row['p_structural_median']:.3f} / "
            f"{row['p_structural_max']:.3f} | {row['blocked_frames']} |"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            *[f"- {value}" for value in report["interpretation_limits"]],
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--frame-results", type=Path, required=True)
    parser.add_argument("--session-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-span-limit", type=float, default=0.15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive = args.archive.resolve(strict=True)
    plan = args.plan.resolve(strict=True)
    frame_results_path = args.frame_results.resolve(strict=True)
    session_results_path = args.session_results.resolve(strict=True)
    telemetry = _archive_telemetry(archive, plan)
    joined = _join_frame_results(telemetry, _read_csv(frame_results_path))
    report = build_report(
        joined,
        _read_csv(session_results_path),
        args.reference_span_limit,
    )
    report["source_archive_sha256"] = _sha256(archive)
    report["frame_results_sha256"] = _sha256(frame_results_path)
    report["session_results_sha256"] = _sha256(session_results_path)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "FRAME_DIAGNOSTICS.csv", joined)
    _write_csv(output / "CLEAN_CASE_DIAGNOSTICS.csv", report["clean_cases_ranked"])
    (output / "ANALYSIS.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "SUMMARY.md").write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "classification": report["diagnostic_classification"],
                "clean_frame_false_blocks": report["clean_frame_false_blocks"],
                "clean_session_consensus_safe": report[
                    "clean_session_consensus_safe"
                ],
                "elevated_clean_layouts": [
                    row["case_id"] for row in report["elevated_clean_layouts"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
