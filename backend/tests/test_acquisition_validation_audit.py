from __future__ import annotations

from pathlib import Path

from scripts.audit_acquisition_validation import AcquisitionFrame, build_summary


def _frame(
    session: str,
    *,
    condition: str,
    ppm: float = 6.0,
    quality: str = "usable",
) -> AcquisitionFrame:
    return AcquisitionFrame(
        session_id=session,
        case_id="SEM-11-PLAIN-TEXT",
        ground_truth="clean",
        condition_id=condition,
        frame_index=0,
        structural_quality_status=quality,
        structural_quality_conditions="normal",
        raw_quality_status="usable",
        raw_quality_conditions="normal",
        exposure_supported=True,
        exposure_index=-1,
        exposure_ev=-0.33,
        exposure_adjusted_during_session=True,
        expected_module_count=29,
        observed_pixels_per_module=ppm,
    )


def test_acquisition_summary_passes_complete_usable_module_scale(tmp_path: Path) -> None:
    archive = tmp_path / "capture.zip"
    archive.write_bytes(b"capture")
    frames = [
        _frame("a" * 24, condition="baseline"),
        _frame("b" * 24, condition="bright"),
    ]
    summary = build_summary(
        archive, frames, target_sessions=2, target_frames=2
    )
    assert summary["acquisition_gate_passed"] is True
    assert summary["telemetry"]["exposure_adjusted_sessions"] == 2
    assert summary["promotion_eligible"] is False


def test_acquisition_summary_fails_unusable_or_under_scale(tmp_path: Path) -> None:
    archive = tmp_path / "capture.zip"
    archive.write_bytes(b"capture")
    frames = [
        _frame(
            "a" * 24,
            condition="bright",
            ppm=4.9,
            quality="unusable",
        )
    ]
    summary = build_summary(
        archive, frames, target_sessions=1, target_frames=1
    )
    assert summary["acquisition_gate_passed"] is False
    assert summary["gates"]["unusable_structural_crops_saved_max_0"] is False
    assert summary["gates"]["frames_below_5_pixels_per_module_max_0"] is False
