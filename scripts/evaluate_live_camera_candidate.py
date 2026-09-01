"""Evaluate the production multi-frame candidate on a validated diagnostic ZIP.

This report is session-level on purpose. It can compare the five captured crops
with the three strongest geometry-ranked crops that the phone can upload. A
neutral non-URL payload is supplied so the result measures Structural acquisition
and consensus without URL evidence. No archive member is extracted and no decoded
payload text is persisted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analyze_live_camera_diagnostic import ValidatedFrame, validate_archive


@dataclass(frozen=True)
class CandidateSession:
    session_id: str
    case_id: str
    ground_truth: str
    distance: str
    repeat_index: int
    frames_captured: int
    frames_received: int
    frames_at_least_256px: int
    frames_analyzed: int
    minimum_crop_side: int
    maximum_crop_side: int
    consensus: str
    quality_status: str
    quality_conditions: str
    p_structural_raw: float | None
    p_structural_effective: float | None
    structural_type: str
    verdict: str
    outcome: str
    elapsed_ms: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _geometry_quality(frame: ValidatedFrame) -> float:
    points = list(zip(frame.corner_coordinates[::2], frame.corner_coordinates[1::2]))
    edges = [
        ((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2) ** 0.5
        for left, right in zip(points, points[1:] + points[:1], strict=True)
    ]
    edge_balance = min(edges) / max(edges) if edges and max(edges) > 0 else 0.0
    # Mirrors the dominant, cheap terms used by Home before full-resolution crop
    # work. The capture ZIP intentionally contains rectified crops, not raw frame
    # bytes, so its small byte-density tie-breaker cannot be reproduced exactly.
    return frame.qr_coverage * 4.0 + edge_balance


def _evaluate(
    frames: list[ValidatedFrame], artifacts: Path, maximum_frames: int
) -> list[CandidateSession]:
    os.environ["QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS"] = str(artifacts.resolve())
    from app.pipeline import run_scan

    grouped: dict[str, list[ValidatedFrame]] = {}
    for frame in frames:
        grouped.setdefault(frame.session_id, []).append(frame)

    results: list[CandidateSession] = []
    for session_id, captured_rows in grouped.items():
        captured_rows.sort(key=lambda item: item.frame_index)
        ranked_rows = sorted(
            captured_rows,
            key=lambda item: (
                _geometry_quality(item),
                min(item.crop_width, item.crop_height),
                -item.frame_index,
            ),
            reverse=True,
        )
        rows = (
            [
                row
                for row in ranked_rows
                if min(row.crop_width, row.crop_height) >= 256
            ][:maximum_frames]
            if maximum_frames == 3
            else ranked_rows[:maximum_frames]
        )
        images = [Image.open(io.BytesIO(row.crop_png)).convert("RGB") for row in rows]
        scan = run_scan(
            payload="QRGuard structural diagnostic",
            images=images,
            image_source="camera",
            image_expected=True,
            require_camera_consensus=True,
        )
        branch = scan.branch_scores
        structural_type = branch.structural_type or "abstained"
        ground_truth = captured_rows[0].ground_truth
        if branch.structural_status in {"inconclusive", "unavailable"}:
            outcome = "rescan"
        elif (
            ground_truth == "clean" and structural_type == "clean"
        ) or (
            ground_truth != "clean"
            and structural_type in {"adversarial", "tampered"}
        ):
            outcome = "correct"
        elif ground_truth == "clean":
            outcome = "false_block"
        else:
            outcome = "false_safe"
        sides = [min(row.crop_width, row.crop_height) for row in captured_rows]
        results.append(
            CandidateSession(
                session_id=session_id,
                case_id=captured_rows[0].case_id,
                ground_truth=ground_truth,
                distance=captured_rows[0].distance,
                repeat_index=captured_rows[0].repeat_index,
                frames_captured=len(captured_rows),
                frames_received=branch.structural_frames_received,
                frames_at_least_256px=sum(
                    min(row.crop_width, row.crop_height) >= 256 for row in rows
                ),
                frames_analyzed=branch.structural_frames_analyzed,
                minimum_crop_side=min(sides),
                maximum_crop_side=max(sides),
                consensus=branch.structural_consensus or "not_reported",
                quality_status=branch.structural_quality_status or "not_reported",
                quality_conditions=";".join(branch.structural_quality_conditions),
                p_structural_raw=branch.p_structural_raw,
                p_structural_effective=branch.p_structural,
                structural_type=structural_type,
                verdict=scan.verdict,
                outcome=outcome,
                elapsed_ms=scan.elapsed_ms,
            )
        )
    return sorted(
        results, key=lambda row: (row.case_id, row.distance, row.repeat_index)
    )


def _summary(
    archive: Path,
    sessions: list[CandidateSession],
    artifacts: Path,
    maximum_frames: int,
) -> dict[str, object]:
    clean = [row for row in sessions if row.ground_truth == "clean"]
    attack = [row for row in sessions if row.ground_truth != "clean"]
    matrix = []
    for case_id in sorted({row.case_id for row in sessions}):
        for distance in ("near", "medium", "far"):
            selected = [
                row
                for row in sessions
                if row.case_id == case_id and row.distance == distance
            ]
            if selected:
                matrix.append(
                    {
                        "case_id": case_id,
                        "ground_truth": selected[0].ground_truth,
                        "distance": distance,
                        "sessions": len(selected),
                        "eligible_frames": sum(
                            row.frames_at_least_256px for row in selected
                        ),
                        "analyzed_frames": sum(row.frames_analyzed for row in selected),
                        "outcomes": dict(Counter(row.outcome for row in selected)),
                        "verdicts": dict(Counter(row.verdict for row in selected)),
                        "structural_types": dict(
                            Counter(row.structural_type for row in selected)
                        ),
                    }
                )
    denominator = lambda rows: max(len(rows), 1)
    elapsed = sorted(row.elapsed_ms for row in sessions)
    definitive_elapsed = sorted(
        row.elapsed_ms for row in sessions if row.outcome != "rescan"
    )
    p95_index = max(0, min(len(elapsed) - 1, (len(elapsed) * 95 + 99) // 100 - 1))
    definitive_p95_index = max(
        0,
        min(
            len(definitive_elapsed) - 1,
            (len(definitive_elapsed) * 95 + 99) // 100 - 1,
        ),
    )
    return {
        "schema_version": 1,
        "evaluation": "production_multi_frame_candidate",
        "payload_policy": "neutral_non_url_structural_only",
        "source": {
            "filename": archive.name,
            "sha256": _sha256(archive),
            "session_count": len(sessions),
            "captured_frame_count": sum(row.frames_captured for row in sessions),
            "evaluated_frame_count": sum(row.frames_received for row in sessions),
            "raw_payload_stored": False,
        },
        "candidate": {
            "minimum_crop_side": 256,
            "minimum_analyzable_frames": 3,
            "maximum_frames": maximum_frames,
            "selection": "best_geometry_before_rectification_proxy",
            "aggregation": "median_score_majority_class",
            "artifact_path": str(artifacts.relative_to(ROOT)).replace("\\", "/"),
        },
        "metrics": {
            "correct_session_rate": sum(row.outcome == "correct" for row in sessions)
            / len(sessions),
            "rescan_session_rate": sum(row.outcome == "rescan" for row in sessions)
            / len(sessions),
            "clean_false_block_rate": sum(row.outcome == "false_block" for row in clean)
            / denominator(clean),
            "adversarial_false_safe_rate": sum(
                row.outcome == "false_safe" for row in attack
            )
            / denominator(attack),
            "definitive_clean_correct_rate": sum(
                row.outcome == "correct" for row in clean
            )
            / max(sum(row.outcome != "rescan" for row in clean), 1),
            "definitive_adversarial_correct_rate": sum(
                row.outcome == "correct" for row in attack
            )
            / max(sum(row.outcome != "rescan" for row in attack), 1),
            "pipeline_elapsed_ms_mean": statistics.mean(elapsed),
            "pipeline_elapsed_ms_median": statistics.median(elapsed),
            "pipeline_elapsed_ms_p95": elapsed[p95_index],
            "definitive_pipeline_elapsed_ms_mean": statistics.mean(
                definitive_elapsed
            ),
            "definitive_pipeline_elapsed_ms_median": statistics.median(
                definitive_elapsed
            ),
            "definitive_pipeline_elapsed_ms_p95": definitive_elapsed[
                definitive_p95_index
            ],
        },
        "matrix": matrix,
    }


def _markdown(summary: dict[str, object]) -> str:
    source = summary["source"]
    metrics = summary["metrics"]
    assert isinstance(source, dict) and isinstance(metrics, dict)
    lines = [
        "# Multi-frame production candidate replay",
        "",
        f"Source SHA-256: `{source['sha256']}`",
        "",
        (
            f"The best {summary['candidate']['maximum_frames']} geometry-ranked "
            "automatic crops in each session were evaluated together. A neutral "
            "non-URL payload isolates Structural behaviour; no decoded payload "
            "was stored."
        ),
        "",
        "## Result",
        "",
        f"- Correct session rate: {metrics['correct_session_rate']:.1%}",
        f"- Rescan rate: {metrics['rescan_session_rate']:.1%}",
        f"- Clean false-Blocked rate: {metrics['clean_false_block_rate']:.1%}",
        f"- Adversarial false-Safe rate: {metrics['adversarial_false_safe_rate']:.1%}",
        (
            "- Definitive decisions correct: clean "
            f"{metrics['definitive_clean_correct_rate']:.1%}; adversarial "
            f"{metrics['definitive_adversarial_correct_rate']:.1%}"
        ),
        (
            "- Pipeline latency: mean "
            f"{metrics['pipeline_elapsed_ms_mean']:.1f} ms; median "
            f"{metrics['pipeline_elapsed_ms_median']} ms; P95 "
            f"{metrics['pipeline_elapsed_ms_p95']} ms"
        ),
        (
            "- Definitive-session pipeline latency: mean "
            f"{metrics['definitive_pipeline_elapsed_ms_mean']:.1f} ms; median "
            f"{metrics['definitive_pipeline_elapsed_ms_median']} ms; P95 "
            f"{metrics['definitive_pipeline_elapsed_ms_p95']} ms"
        ),
        "",
        "## Case x distance",
        "",
        "| Case | Distance | >=256 px frames | Analysed | Outcomes |",
        "|---|---|---:|---:|---|",
    ]
    matrix = summary["matrix"]
    assert isinstance(matrix, list)
    for row in matrix:
        assert isinstance(row, dict)
        lines.append(
            f"| {row['case_id']} | {row['distance']} | {row['eligible_frames']} | "
            f"{row['analyzed_frames']} | {row['outcomes']} |"
        )
    lines.extend(
        [
            "",
            (
                "A rescan is an intentional abstention, not a correct classification. "
                "This captured matrix used smaller QR crops than the promoted exact-app "
                "holdout, so it validates fail-closed acquisition behaviour but cannot "
                "replace the independent deployment gate."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument(
        "--plan",
        type=Path,
        default=ROOT / "app" / "assets" / "capture" / "diagnostic_capture_plan.json",
    )
    parser.add_argument(
        "--artifacts", type=Path, default=ROOT / "training" / "artifacts" / "structural"
    )
    parser.add_argument("--maximum-frames", type=int, choices=(3, 5), default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "research_evidence"
        / "structural"
        / "performance"
        / "live-camera-repeatability-2026-09-r01"
        / "candidate-multiframe",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive = args.archive.resolve(strict=True)
    frames = validate_archive(archive, args.plan.resolve(strict=True))
    sessions = _evaluate(
        frames, args.artifacts.resolve(strict=True), args.maximum_frames
    )
    summary = _summary(
        archive,
        sessions,
        args.artifacts.resolve(strict=True),
        args.maximum_frames,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    rows = [asdict(row) for row in sessions]
    with (args.output / "SESSION_RESULTS.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "ANALYSIS.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "SUMMARY.md").write_text(_markdown(summary), encoding="utf-8")
    print(json.dumps(summary["metrics"], indent=2))
    print(f"wrote reports to {args.output}")


if __name__ == "__main__":
    main()
