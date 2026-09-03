"""Audit r02 on-device acquisition telemetry without extracting the ZIP.

The general diagnostic replay remains responsible for model/verdict metrics.
This audit proves that the Android collector itself applied the locked r02
metering, exposure, quality, and QR module-scale evidence contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_live_camera_diagnostic import validate_archive

DEFAULT_PLAN = ROOT / "app/assets/capture/acquisition_validation_plan.json"
DEFAULT_OUTPUT = (
    ROOT
    / "research_evidence/structural/performance/"
    "screen-camera-robustness-2026-09-r02/ACQUISITION_VALIDATION"
)
POLICY_VERSION = "qrguard-camera-acquisition-2026-09-r02"
MINIMUM_MODULE_PIXELS = 5.0


@dataclass(frozen=True)
class AcquisitionFrame:
    session_id: str
    case_id: str
    ground_truth: str
    condition_id: str
    frame_index: int
    structural_quality_status: str
    structural_quality_conditions: str
    raw_quality_status: str
    raw_quality_conditions: str
    exposure_supported: bool
    exposure_index: int | None
    exposure_ev: float | None
    exposure_adjusted_during_session: bool
    expected_module_count: int
    observed_pixels_per_module: float


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_acquisition_frames(
    archive_path: Path, plan_path: Path
) -> list[AcquisitionFrame]:
    # Complete transport, hashes, privacy, geometry, and telemetry types are
    # checked by the shared untrusted-ZIP validator before values are consumed.
    validate_archive(archive_path, plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cases = {row["case_id"]: row for row in plan["cases"]}
    frames: list[AcquisitionFrame] = []
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("archive_manifest.json"))
        for session in manifest["sessions"]:
            metadata = json.loads(
                archive.read(f"{session['base_path']}/metadata.json")
            )
            if metadata["selection_policy"] != (
                "automatic_post_exposure_quality_gated_temporal_burst"
            ):
                raise ValueError("archive was not collected with the r02 policy")
            if metadata["acquisition_policy"]["policy_version"] != POLICY_VERSION:
                raise ValueError("acquisition policy version mismatch")
            case_id = str(metadata["case_id"])
            version = cases[case_id]["metadata"]["qr_version"]
            expected_modules = 17 + 4 * int(version)
            session_rows: list[AcquisitionFrame] = []
            for row in metadata["frames"]:
                raw = row["raw_acquisition_quality"]
                structural = row["structural_crop_quality"]
                session_rows.append(
                    AcquisitionFrame(
                        session_id=str(metadata["diagnostic_session_id"]),
                        case_id=case_id,
                        ground_truth=str(metadata["ground_truth"]),
                        condition_id=str(metadata["condition_id"]),
                        frame_index=int(row["frame_index"]),
                        structural_quality_status=str(structural["status"]),
                        structural_quality_conditions=";".join(
                            str(item) for item in structural["conditions"]
                        ),
                        raw_quality_status=str(raw["status"]),
                        raw_quality_conditions=";".join(
                            str(item) for item in raw["conditions"]
                        ),
                        exposure_supported=bool(
                            row["exposure_compensation_supported"]
                        ),
                        exposure_index=(
                            int(row["exposure_compensation_index"])
                            if row["exposure_compensation_index"] is not None
                            else None
                        ),
                        exposure_ev=(
                            float(row["exposure_compensation_ev"])
                            if row["exposure_compensation_ev"] is not None
                            else None
                        ),
                        exposure_adjusted_during_session=bool(
                            row["exposure_adjusted_during_session"]
                        ),
                        expected_module_count=int(row["expected_module_count"]),
                        observed_pixels_per_module=float(
                            row["observed_pixels_per_module"]
                        ),
                    )
                )
            if any(row.expected_module_count != expected_modules for row in session_rows):
                raise ValueError(f"module count mismatch in {case_id}")
            if len({row.exposure_supported for row in session_rows}) != 1 or len(
                {row.exposure_adjusted_during_session for row in session_rows}
            ) != 1:
                raise ValueError(f"exposure state changed inside saved burst: {case_id}")
            frames.extend(session_rows)
    return frames


def build_summary(
    archive_path: Path,
    frames: list[AcquisitionFrame],
    *,
    target_sessions: int,
    target_frames: int,
) -> dict[str, Any]:
    sessions = {row.session_id for row in frames}
    below_scale = [
        row
        for row in frames
        if row.observed_pixels_per_module < MINIMUM_MODULE_PIXELS
    ]
    unusable = [
        row for row in frames if row.structural_quality_status == "unusable"
    ]
    adjusted_sessions = {
        row.session_id for row in frames if row.exposure_adjusted_during_session
    }
    supported_sessions = {
        row.session_id for row in frames if row.exposure_supported
    }
    condition_rows: list[dict[str, Any]] = []
    for condition in sorted({row.condition_id for row in frames}):
        selected = [row for row in frames if row.condition_id == condition]
        condition_sessions = {row.session_id for row in selected}
        condition_rows.append(
            {
                "condition_id": condition,
                "sessions": len(condition_sessions),
                "frames": len(selected),
                "adjusted_sessions": len(
                    condition_sessions & adjusted_sessions
                ),
                "raw_quality_statuses": dict(
                    Counter(row.raw_quality_status for row in selected)
                ),
                "structural_quality_statuses": dict(
                    Counter(row.structural_quality_status for row in selected)
                ),
                "minimum_observed_pixels_per_module": min(
                    row.observed_pixels_per_module for row in selected
                ),
                "median_observed_pixels_per_module": statistics.median(
                    row.observed_pixels_per_module for row in selected
                ),
            }
        )
    gates = {
        "complete_session_matrix": len(sessions) == target_sessions,
        "complete_frame_matrix": len(frames) == target_frames,
        "unusable_structural_crops_saved_max_0": len(unusable) == 0,
        "frames_below_5_pixels_per_module_max_0": len(below_scale) == 0,
    }
    return {
        "schema_version": 1,
        "audit": "qrguard_r02_acquisition_telemetry",
        "source": {
            "filename": archive_path.name,
            "sha256": _sha256(archive_path),
            "sessions": len(sessions),
            "frames": len(frames),
        },
        "policy": {
            "version": POLICY_VERSION,
            "minimum_observed_module_pixels": MINIMUM_MODULE_PIXELS,
            "model_or_attack_label_used_for_frame_selection": False,
        },
        "telemetry": {
            "exposure_supported_sessions": len(supported_sessions),
            "exposure_adjusted_sessions": len(adjusted_sessions),
            "structural_quality_statuses": dict(
                Counter(row.structural_quality_status for row in frames)
            ),
            "raw_quality_statuses": dict(
                Counter(row.raw_quality_status for row in frames)
            ),
            "minimum_observed_pixels_per_module": min(
                row.observed_pixels_per_module for row in frames
            ),
            "frames_below_minimum_module_scale": len(below_scale),
            "conditions": condition_rows,
        },
        "gates": gates,
        "acquisition_gate_passed": all(gates.values()),
        "model_replay_still_required": True,
        "promotion_eligible": False,
        "non_promotion_reason": (
            "development acquisition matrix; r02 training and a fresh "
            "device/display/session blind holdout remain mandatory"
        ),
    }


def _markdown(summary: dict[str, Any]) -> str:
    source = summary["source"]
    telemetry = summary["telemetry"]
    lines = [
        "# r02 acquisition telemetry audit",
        "",
        f"- Sessions / frames: {source['sessions']} / {source['frames']}.",
        f"- Exposure-supported sessions: {telemetry['exposure_supported_sessions']}.",
        f"- Exposure-adjusted sessions: {telemetry['exposure_adjusted_sessions']}.",
        (
            "- Minimum observed pixels/module: "
            f"{telemetry['minimum_observed_pixels_per_module']:.3f}."
        ),
        (
            "- Frames below 5 pixels/module: "
            f"{telemetry['frames_below_minimum_module_scale']}."
        ),
        f"- Acquisition gate passed: {summary['acquisition_gate_passed']}.",
        "",
        (
            "This development audit cannot promote a model. Model replay, r02 GPU "
            "training, and a fresh device/display/session blind holdout remain required."
        ),
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive = args.archive.resolve(strict=True)
    plan_path = args.plan.resolve(strict=True)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    target_sessions = (
        len(plan["cases"])
        * len(plan["distances"])
        * int(plan["repeats_per_distance"])
    )
    target_frames = target_sessions * int(plan["frames_per_session"])
    frames = read_acquisition_frames(archive, plan_path)
    summary = build_summary(
        archive,
        frames,
        target_sessions=target_sessions,
        target_frames=target_frames,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "ACQUISITION_FRAMES.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        rows = [asdict(row) for row in frames]
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "ACQUISITION_AUDIT.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "ACQUISITION_AUDIT.md").write_text(
        _markdown(summary), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
