"""Validate and replay QRGuard multi-frame Diagnostic Capture ZIPs.

The ZIP is treated as an untrusted transport container. Validation is completed
before model inference, no archive member is extracted, and raw decoded payload
text is never written to a report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import statistics
import sys
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

ARCHIVE_SCHEMA = 1
METADATA_SCHEMA = 1
COLLECTOR = "qrguard_android_diagnostic_capture"
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
SESSION_ID_LENGTH = 24
SHA256_LENGTH = 64


@dataclass(frozen=True)
class ValidatedFrame:
    session_id: str
    case_id: str
    ground_truth: str
    distance: str
    repeat_index: int
    frame_index: int
    crop_name: str
    crop_sha256: str
    crop_png: bytes
    crop_width: int
    crop_height: int
    frame_width: float
    frame_height: float
    corner_coordinates: tuple[float, ...]
    qr_coverage: float
    payload_sha256: str


@dataclass(frozen=True)
class FrameResult:
    session_id: str
    case_id: str
    ground_truth: str
    distance: str
    repeat_index: int
    frame_index: int
    crop_sha256: str
    crop_width: int
    crop_height: int
    frame_width: float
    frame_height: float
    qr_coverage: float
    payload_decode_status: str
    payload_hash_matches: bool
    quality_status: str
    quality_conditions: str
    p05_luminance: float
    p95_luminance: float
    dynamic_range: float
    laplacian_variance: float
    p_structural_raw: float | None
    p_structural_effective: float | None
    structural_type: str
    structural_status: str
    semantic_status: str
    p_url: float | None
    risk_score: int
    verdict: str
    partial_analysis: bool
    elapsed_ms: int


@dataclass(frozen=True)
class SessionResult:
    session_id: str
    case_id: str
    ground_truth: str
    distance: str
    repeat_index: int
    frame_count: int
    usable_frame_count: int
    decoded_frame_count: int
    safe_frames: int
    warning_frames: int
    blocked_frames: int
    clean_type_frames: int
    nonclean_type_frames: int
    current_first_verdict: str
    majority_verdict: str
    median_risk_verdict: str
    median_risk_score: float
    median_p_structural: float | None
    p_structural_range: float | None
    majority_detects_ground_truth: bool


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_json(raw: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {description} JSON") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{description} must be a JSON object")
    return value


def _is_hex(value: object, length: int) -> bool:
    text = str(value)
    return len(text) == length and all(char in "0123456789abcdef" for char in text)


def _aware_timestamp(value: object, description: str) -> str:
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid timestamp for {description}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone for {description}")
    return text


def _has_raw_payload_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in {"payload", "raw_payload", "payload_text"}:
                return True
            if _has_raw_payload_key(nested):
                return True
    elif isinstance(value, list):
        return any(_has_raw_payload_key(item) for item in value)
    return False


def _coverage(corners: tuple[float, ...], width: float, height: float) -> float:
    points = list(zip(corners[::2], corners[1::2], strict=True))
    area = abs(
        sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True)
        )
    ) / 2.0
    return area / (width * height)


def _validate_member_table(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in archive.infolist():
        name = info.filename
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or info.is_dir()
            or info.flag_bits & 0x1
        ):
            raise ValueError(f"unsafe or unsupported ZIP member: {name!r}")
        if name in members:
            raise ValueError(f"duplicate ZIP member: {name}")
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise ValueError(f"symbolic link is not allowed: {name}")
        limit = MAX_MANIFEST_BYTES if name == "archive_manifest.json" else MAX_MEMBER_BYTES
        if info.file_size > limit:
            raise ValueError(f"ZIP member exceeds its size limit: {name}")
        total += info.file_size
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError("archive exceeds the uncompressed size limit")
        members[name] = info
    return members


def _load_plan(plan_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cases = {row["case_id"]: row for row in plan["cases"]}
    distances = {row["id"]: row for row in plan["distances"]}
    return plan, {"cases": cases, "distances": distances}


def validate_archive(archive_path: Path, plan_path: Path) -> list[ValidatedFrame]:
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("archive exceeds the compressed size limit")
    plan, lookups = _load_plan(plan_path)
    cases = lookups["cases"]
    distances = lookups["distances"]
    frames_per_session = int(plan["frames_per_session"])
    repeats = int(plan["repeats_per_distance"])
    expected_sessions = len(cases) * len(distances) * repeats

    with zipfile.ZipFile(archive_path) as archive:
        members = _validate_member_table(archive)
        if "archive_manifest.json" not in members:
            raise ValueError("archive_manifest.json is missing")
        manifest_raw = archive.read(members["archive_manifest.json"])
        manifest = _load_json(manifest_raw, "archive manifest")
        expected_manifest = {
            "diagnostic_archive_schema_version": ARCHIVE_SCHEMA,
            "collector": COLLECTOR,
            "campaign_id": plan["campaign_id"],
            "session_count": expected_sessions,
            "frame_count": expected_sessions * frames_per_session,
            "raw_payload_stored": False,
        }
        for key, expected in expected_manifest.items():
            if manifest.get(key) != expected:
                raise ValueError(f"archive manifest {key} mismatch")
        _aware_timestamp(manifest.get("exported_at"), "archive export")
        rows = manifest.get("sessions")
        if not isinstance(rows, list) or len(rows) != expected_sessions:
            raise ValueError("archive session rows do not match the locked matrix")

        used = {"archive_manifest.json"}
        matrix: Counter[tuple[str, str, int]] = Counter()
        session_ids: set[str] = set()
        validated: list[ValidatedFrame] = []
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError("each archive session row must be an object")
            session_id = str(row.get("diagnostic_session_id", ""))
            case_id = str(row.get("case_id", ""))
            distance = str(row.get("distance", ""))
            repeat_index = int(row.get("repeat_index", 0))
            base = str(row.get("base_path", ""))
            if not _is_hex(session_id, SESSION_ID_LENGTH) or session_id in session_ids:
                raise ValueError(f"invalid or duplicate session ID: {session_id!r}")
            if case_id not in cases or distance not in distances:
                raise ValueError(f"unknown matrix coordinate: {case_id}/{distance}")
            if repeat_index not in range(1, repeats + 1):
                raise ValueError(f"invalid repeat index for {case_id}/{distance}")
            expected_base = (
                f"sessions/{case_id}/{distance}/"
                f"run_{repeat_index:02d}_{session_id}"
            )
            if base != expected_base:
                raise ValueError(f"unexpected base path for {case_id}/{distance}")
            if row.get("frame_count") != frames_per_session:
                raise ValueError(f"frame count mismatch for {base}")
            metadata_name = f"{base}/metadata.json"
            if metadata_name not in members:
                raise ValueError(f"metadata is missing for {base}")
            metadata_raw = archive.read(members[metadata_name])
            if row.get("metadata_sha256") != _sha256(metadata_raw):
                raise ValueError(f"metadata hash mismatch for {base}")
            metadata = _load_json(metadata_raw, f"metadata for {base}")
            if _has_raw_payload_key(metadata):
                raise ValueError(f"raw payload field found in {base}")
            expected_metadata = {
                "diagnostic_capture_schema_version": METADATA_SCHEMA,
                "collector": COLLECTOR,
                "diagnostic_session_id": session_id,
                "campaign_id": plan["campaign_id"],
                "case_id": case_id,
                "ground_truth": cases[case_id]["ground_truth"],
                "distance": distance,
                "repeat_index": repeat_index,
                "payload_sha256": cases[case_id]["expected_payload_sha256"],
                "payload_hash_source": "on_device_mlkit_decode",
                "raw_payload_stored": False,
                "image_source": "camera",
                "frames_per_session": frames_per_session,
                "selection_policy": "automatic_temporal_burst_no_cherry_pick",
                "analysis_pending": True,
            }
            for key, expected in expected_metadata.items():
                if metadata.get(key) != expected:
                    raise ValueError(f"{base}: {key} mismatch")
            _aware_timestamp(metadata.get("captured_at"), base)
            metadata_frames = metadata.get("frames")
            if not isinstance(metadata_frames, list) or len(metadata_frames) != frames_per_session:
                raise ValueError(f"metadata frame rows mismatch for {base}")

            session_hashes: set[str] = set()
            for frame_index, frame_row in enumerate(metadata_frames):
                if not isinstance(frame_row, dict) or frame_row.get("frame_index") != frame_index:
                    raise ValueError(f"invalid frame index in {base}")
                _aware_timestamp(frame_row.get("captured_at"), f"{base}/{frame_index}")
                crop_name = f"{base}/crop_{frame_index:02d}.png"
                if crop_name not in members:
                    raise ValueError(f"crop is missing: {crop_name}")
                crop = archive.read(members[crop_name])
                crop_hash = _sha256(crop)
                if frame_row.get("crop_sha256") != crop_hash:
                    raise ValueError(f"crop hash mismatch: {crop_name}")
                if crop_hash in session_hashes:
                    raise ValueError(f"duplicate crop inside session: {base}")
                session_hashes.add(crop_hash)
                try:
                    image = Image.open(io.BytesIO(crop))
                    image.load()
                except Exception as exc:
                    raise ValueError(f"unreadable crop: {crop_name}") from exc
                if image.format != "PNG" or min(image.size) < 24:
                    raise ValueError(f"invalid crop image: {crop_name}")
                crop_size = frame_row.get("crop_size")
                if crop_size != [image.width, image.height]:
                    raise ValueError(f"crop dimensions mismatch: {crop_name}")
                frame_size = frame_row.get("frame_size")
                corners = frame_row.get("corner_coordinates")
                if (
                    not isinstance(frame_size, list)
                    or len(frame_size) != 2
                    or not all(isinstance(item, (int, float)) and item > 0 for item in frame_size)
                    or not isinstance(corners, list)
                    or len(corners) != 8
                    or not all(isinstance(item, (int, float)) and math.isfinite(item) for item in corners)
                ):
                    raise ValueError(f"invalid frame geometry: {crop_name}")
                coordinates = tuple(float(item) for item in corners)
                frame_width, frame_height = (float(item) for item in frame_size)
                coverage = _coverage(coordinates, frame_width, frame_height)
                if not 0 < coverage <= 1:
                    raise ValueError(f"invalid QR coverage: {crop_name}")
                validated.append(
                    ValidatedFrame(
                        session_id=session_id,
                        case_id=case_id,
                        ground_truth=str(cases[case_id]["ground_truth"]),
                        distance=distance,
                        repeat_index=repeat_index,
                        frame_index=frame_index,
                        crop_name=crop_name,
                        crop_sha256=crop_hash,
                        crop_png=crop,
                        crop_width=image.width,
                        crop_height=image.height,
                        frame_width=frame_width,
                        frame_height=frame_height,
                        corner_coordinates=coordinates,
                        qr_coverage=coverage,
                        payload_sha256=str(metadata["payload_sha256"]),
                    )
                )
                used.add(crop_name)
            used.add(metadata_name)
            matrix[(case_id, distance, repeat_index)] += 1
            session_ids.add(session_id)

        expected_matrix = {
            (case_id, distance, repeat_index)
            for case_id in cases
            for distance in distances
            for repeat_index in range(1, repeats + 1)
        }
        if set(matrix) != expected_matrix or any(count != 1 for count in matrix.values()):
            raise ValueError("archive does not contain the complete unique matrix")
        unused = set(members) - used
        if unused:
            raise ValueError(f"archive contains unreferenced members: {sorted(unused)[:3]}")
        return validated


def replay_frames(frames: list[ValidatedFrame], artifacts: Path) -> list[FrameResult]:
    os.environ["QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS"] = str(artifacts.resolve())
    from app.pipeline import run_scan
    from structural.image_quality import assess_image_quality

    results: list[FrameResult] = []
    for index, frame in enumerate(frames, start=1):
        image = Image.open(io.BytesIO(frame.crop_png)).convert("RGB")
        quality = assess_image_quality(image)
        scan = run_scan(image=image, image_source="camera", image_expected=True)
        decoded = (scan.payload or "").strip()
        decoded_hash = hashlib.sha256(decoded.encode()).hexdigest() if decoded else ""
        branch = scan.branch_scores
        results.append(
            FrameResult(
                session_id=frame.session_id,
                case_id=frame.case_id,
                ground_truth=frame.ground_truth,
                distance=frame.distance,
                repeat_index=frame.repeat_index,
                frame_index=frame.frame_index,
                crop_sha256=frame.crop_sha256,
                crop_width=frame.crop_width,
                crop_height=frame.crop_height,
                frame_width=frame.frame_width,
                frame_height=frame.frame_height,
                qr_coverage=frame.qr_coverage,
                payload_decode_status=scan.payload_source,
                payload_hash_matches=bool(decoded) and decoded_hash == frame.payload_sha256,
                quality_status=branch.structural_quality_status or "not_reported",
                quality_conditions=";".join(branch.structural_quality_conditions),
                p05_luminance=quality.p05_luminance,
                p95_luminance=quality.p95_luminance,
                dynamic_range=quality.dynamic_range,
                laplacian_variance=quality.laplacian_variance,
                p_structural_raw=branch.p_structural_raw,
                p_structural_effective=branch.p_structural,
                structural_type=branch.structural_type or "abstained",
                structural_status=branch.structural_status,
                semantic_status=branch.semantic_status,
                p_url=branch.p_url,
                risk_score=scan.risk_score,
                verdict=scan.verdict,
                partial_analysis=scan.partial_analysis,
                elapsed_ms=scan.elapsed_ms,
            )
        )
        if index % 10 == 0:
            print(f"replayed {index}/{len(frames)} frames", flush=True)
    return results


def _tier(score: float) -> str:
    if score < 30:
        return "safe"
    if score < 70:
        return "warning"
    return "blocked"


def aggregate_sessions(frames: list[FrameResult]) -> list[SessionResult]:
    grouped: dict[str, list[FrameResult]] = {}
    for frame in frames:
        grouped.setdefault(frame.session_id, []).append(frame)
    sessions: list[SessionResult] = []
    verdict_rank = {"safe": 0, "warning": 1, "blocked": 2}
    for session_id, rows in grouped.items():
        rows.sort(key=lambda item: item.frame_index)
        verdicts = Counter(row.verdict for row in rows)
        maximum = max(verdicts.values())
        majority = max(
            (verdict for verdict, count in verdicts.items() if count == maximum),
            key=verdict_rank.__getitem__,
        )
        scores = [
            row.p_structural_effective
            for row in rows
            if row.p_structural_effective is not None
        ]
        median_score = statistics.median(row.risk_score for row in rows)
        nonclean = sum(row.structural_type in {"adversarial", "tampered"} for row in rows)
        clean = sum(row.structural_type == "clean" for row in rows)
        ground_truth = rows[0].ground_truth
        sessions.append(
            SessionResult(
                session_id=session_id,
                case_id=rows[0].case_id,
                ground_truth=ground_truth,
                distance=rows[0].distance,
                repeat_index=rows[0].repeat_index,
                frame_count=len(rows),
                usable_frame_count=len(scores),
                decoded_frame_count=sum(row.payload_hash_matches for row in rows),
                safe_frames=verdicts["safe"],
                warning_frames=verdicts["warning"],
                blocked_frames=verdicts["blocked"],
                clean_type_frames=clean,
                nonclean_type_frames=nonclean,
                current_first_verdict=rows[0].verdict,
                majority_verdict=majority,
                median_risk_verdict=_tier(median_score),
                median_risk_score=float(median_score),
                median_p_structural=float(statistics.median(scores)) if scores else None,
                p_structural_range=float(max(scores) - min(scores)) if scores else None,
                majority_detects_ground_truth=(nonclean >= 3)
                if ground_truth != "clean"
                else (clean >= 3),
            )
        )
    return sorted(sessions, key=lambda row: (row.case_id, row.distance, row.repeat_index))


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def build_summary(
    archive_path: Path,
    archive_sha256: str,
    frames: list[FrameResult],
    sessions: list[SessionResult],
    artifacts: Path,
) -> dict[str, Any]:
    artifact_metadata = json.loads(
        (artifacts / "model_metadata.json").read_text(encoding="utf-8")
    )
    global_hash_counts = Counter(frame.crop_sha256 for frame in frames)
    matrix: list[dict[str, Any]] = []
    for case_id in sorted({row.case_id for row in frames}):
        for distance in ("near", "medium", "far"):
            selected_frames = [
                row for row in frames if row.case_id == case_id and row.distance == distance
            ]
            selected_sessions = [
                row for row in sessions if row.case_id == case_id and row.distance == distance
            ]
            if not selected_frames:
                continue
            scores = [
                row.p_structural_effective
                for row in selected_frames
                if row.p_structural_effective is not None
            ]
            matrix.append(
                {
                    "case_id": case_id,
                    "ground_truth": selected_frames[0].ground_truth,
                    "distance": distance,
                    "frames": len(selected_frames),
                    "sessions": len(selected_sessions),
                    "decoded_hash_matches": sum(row.payload_hash_matches for row in selected_frames),
                    "quality": dict(Counter(row.quality_status for row in selected_frames)),
                    "verdicts": dict(Counter(row.verdict for row in selected_frames)),
                    "structural_types": dict(
                        Counter(row.structural_type for row in selected_frames)
                    ),
                    "p_structural_min": min(scores) if scores else None,
                    "p_structural_median": statistics.median(scores) if scores else None,
                    "p_structural_max": max(scores) if scores else None,
                    "qr_coverage_median": statistics.median(
                        row.qr_coverage for row in selected_frames
                    ),
                    "session_first_verdicts": dict(
                        Counter(row.current_first_verdict for row in selected_sessions)
                    ),
                    "session_majority_verdicts": dict(
                        Counter(row.majority_verdict for row in selected_sessions)
                    ),
                    "session_median_verdicts": dict(
                        Counter(row.median_risk_verdict for row in selected_sessions)
                    ),
                }
            )

    clean_frames = [row for row in frames if row.ground_truth == "clean"]
    attack_frames = [row for row in frames if row.ground_truth != "clean"]
    clean_sessions = [row for row in sessions if row.ground_truth == "clean"]
    attack_sessions = [row for row in sessions if row.ground_truth != "clean"]
    return {
        "schema_version": 1,
        "source": {
            "filename": archive_path.name,
            "sha256": archive_sha256,
            "session_count": len(sessions),
            "frame_count": len(frames),
            "raw_payload_stored": False,
        },
        "model": {
            "version": artifact_metadata.get("version"),
            "artifact_sha256": artifact_metadata.get("artifact_sha256"),
            "path": "training/artifacts/structural",
        },
        "integrity": {
            "decoded_payload_hash_matches": sum(row.payload_hash_matches for row in frames),
            "globally_unique_crops": len(global_hash_counts),
            "duplicate_crop_instances": sum(count - 1 for count in global_hash_counts.values()),
        },
        "frame_metrics": {
            "clean_false_block_rate": _rate(
                sum(row.verdict == "blocked" for row in clean_frames), len(clean_frames)
            ),
            "clean_non_safe_rate": _rate(
                sum(row.verdict != "safe" for row in clean_frames), len(clean_frames)
            ),
            "adversarial_false_safe_rate": _rate(
                sum(row.verdict == "safe" for row in attack_frames), len(attack_frames)
            ),
            "adversarial_block_rate": _rate(
                sum(row.verdict == "blocked" for row in attack_frames), len(attack_frames)
            ),
            "quality_abstention_rate": _rate(
                sum(row.structural_status == "inconclusive" for row in frames), len(frames)
            ),
        },
        "session_metrics": {
            "single_first_clean_false_block_rate": _rate(
                sum(row.current_first_verdict == "blocked" for row in clean_sessions),
                len(clean_sessions),
            ),
            "single_first_adversarial_false_safe_rate": _rate(
                sum(row.current_first_verdict == "safe" for row in attack_sessions),
                len(attack_sessions),
            ),
            "majority_clean_false_block_rate": _rate(
                sum(row.majority_verdict == "blocked" for row in clean_sessions),
                len(clean_sessions),
            ),
            "majority_adversarial_false_safe_rate": _rate(
                sum(row.majority_verdict == "safe" for row in attack_sessions),
                len(attack_sessions),
            ),
            "median_clean_false_block_rate": _rate(
                sum(row.median_risk_verdict == "blocked" for row in clean_sessions),
                len(clean_sessions),
            ),
            "median_adversarial_false_safe_rate": _rate(
                sum(row.median_risk_verdict == "safe" for row in attack_sessions),
                len(attack_sessions),
            ),
            "majority_structural_ground_truth_detection_rate": _rate(
                sum(row.majority_detects_ground_truth for row in sessions), len(sessions)
            ),
        },
        "matrix": matrix,
    }


def _write_csv(path: Path, rows: list[object]) -> None:
    if not rows:
        raise ValueError(f"cannot write an empty report: {path}")
    dictionaries = [asdict(row) for row in rows]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def _summary_markdown(summary: dict[str, Any]) -> str:
    frame = summary["frame_metrics"]
    session = summary["session_metrics"]
    integrity = summary["integrity"]
    lines = [
        "# Live-camera repeatability results",
        "",
        f"Source SHA-256: `{summary['source']['sha256']}`",
        "",
        (
            f"Model: `{summary['model']['version']}` / "
            f"`{summary['model']['artifact_sha256']}`"
        ),
        "",
        "## Integrity",
        "",
        (
            f"- Sessions / frames: {summary['source']['session_count']} / "
            f"{summary['source']['frame_count']}"
        ),
        (
            "- Crops whose independently decoded payload hash matched: "
            f"{integrity['decoded_payload_hash_matches']}/"
            f"{summary['source']['frame_count']}"
        ),
        (
            f"- Globally unique crops: {integrity['globally_unique_crops']}; "
            f"duplicate instances: {integrity['duplicate_crop_instances']}"
        ),
        "- Raw decoded payload text stored: no",
        "",
        "## Observed error rates",
        "",
        "| Level/policy | Clean false Blocked | Adversarial false Safe |",
        "|---|---:|---:|",
        (
            f"| Individual frame | {frame['clean_false_block_rate']:.1%} | "
            f"{frame['adversarial_false_safe_rate']:.1%} |"
        ),
        (
            "| Session first frame | "
            f"{session['single_first_clean_false_block_rate']:.1%} | "
            f"{session['single_first_adversarial_false_safe_rate']:.1%} |"
        ),
        (
            "| Majority of five verdicts | "
            f"{session['majority_clean_false_block_rate']:.1%} | "
            f"{session['majority_adversarial_false_safe_rate']:.1%} |"
        ),
        (
            "| Median of five risk scores | "
            f"{session['median_clean_false_block_rate']:.1%} | "
            f"{session['median_adversarial_false_safe_rate']:.1%} |"
        ),
        "",
        f"Quality abstention rate: {frame['quality_abstention_rate']:.1%}.",
        "",
        "## Case × distance",
        "",
        (
            "| Case | Distance | Quality | Frame verdicts | "
            "p_structural min / median / max | First | Majority | Median |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in summary["matrix"]:
        scores = (
            "n/a"
            if row["p_structural_median"] is None
            else f"{row['p_structural_min']:.3f} / {row['p_structural_median']:.3f} / "
            f"{row['p_structural_max']:.3f}"
        )
        lines.append(
            f"| {row['case_id']} | {row['distance']} | {row['quality']} | "
            f"{row['verdicts']} | {scores} | {row['session_first_verdicts']} | "
            f"{row['session_majority_verdicts']} | {row['session_median_verdicts']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation constraint",
            "",
            (
                "These two QR references are exposed diagnostic cases, not an "
                "independent deployment test set. They can identify a live-camera "
                "failure mode and compare aggregation behaviour, but no production "
                "threshold may be promoted until the chosen rule also passes the "
                "existing held-out Structural gates."
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
        "--artifacts",
        type=Path,
        default=ROOT / "training" / "artifacts" / "structural",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "research_evidence"
        / "structural"
        / "performance"
        / "live-camera-repeatability-2026-09-r01",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive = args.archive.resolve(strict=True)
    frames = validate_archive(archive, args.plan.resolve(strict=True))
    print(f"validated {len(frames)} frames across {len({f.session_id for f in frames})} sessions")
    replayed = replay_frames(frames, args.artifacts.resolve(strict=True))
    sessions = aggregate_sessions(replayed)
    archive_hash = _sha256(archive.read_bytes())
    summary = build_summary(archive, archive_hash, replayed, sessions, args.artifacts)

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "FRAME_RESULTS.csv", replayed)
    _write_csv(output / "SESSION_RESULTS.csv", sessions)
    (output / "ANALYSIS.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "SUMMARY.md").write_text(_summary_markdown(summary), encoding="utf-8")
    (output / "SOURCE_SHA256.txt").write_text(
        f"{archive_hash}  {archive.name}\n", encoding="ascii"
    )
    print(json.dumps(summary["frame_metrics"], indent=2))
    print(json.dumps(summary["session_metrics"], indent=2))
    print(f"wrote reports to {output}")


if __name__ == "__main__":
    main()
