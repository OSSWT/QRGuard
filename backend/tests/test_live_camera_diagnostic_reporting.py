from pathlib import Path

from scripts.analyze_live_camera_diagnostic import (
    FrameResult,
    SessionResult,
    build_summary,
)
from scripts.evaluate_live_camera_candidate import CandidateSession, _summary


def _frame() -> FrameResult:
    return FrameResult(
        session_id="a" * 24,
        case_id="RC-MASK-4",
        ground_truth="clean",
        distance="screen-80",
        repeat_index=1,
        frame_index=0,
        crop_sha256="b" * 64,
        crop_width=280,
        crop_height=280,
        frame_width=960.0,
        frame_height=1280.0,
        qr_coverage=0.08,
        payload_decode_status="decoded",
        payload_hash_matches=True,
        quality_status="marginal",
        quality_conditions="overexposure",
        p05_luminance=90.0,
        p95_luminance=235.0,
        dynamic_range=145.0,
        laplacian_variance=500.0,
        p_structural_raw=0.8,
        p_structural_effective=0.8,
        structural_type="adversarial",
        structural_status="completed",
        semantic_status="not_applicable",
        p_url=None,
        risk_score=76,
        verdict="blocked",
        partial_analysis=False,
        elapsed_ms=40,
    )


def _session() -> SessionResult:
    return SessionResult(
        session_id="a" * 24,
        case_id="RC-MASK-4",
        ground_truth="clean",
        distance="screen-80",
        repeat_index=1,
        frame_count=5,
        usable_frame_count=5,
        decoded_frame_count=5,
        safe_frames=0,
        warning_frames=0,
        blocked_frames=5,
        clean_type_frames=0,
        nonclean_type_frames=5,
        current_first_verdict="blocked",
        majority_verdict="blocked",
        median_risk_verdict="blocked",
        median_risk_score=76.0,
        median_p_structural=0.8,
        p_structural_range=0.1,
        majority_detects_ground_truth=False,
    )


def test_frame_report_uses_conditions_present_in_custom_plan(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "model_metadata.json").write_text(
        '{"version":"test","artifact_sha256":"abc"}', encoding="utf-8"
    )

    summary = build_summary(
        Path("capture.zip"), "c" * 64, [_frame()], [_session()], artifacts
    )

    assert [(row["case_id"], row["distance"]) for row in summary["matrix"]] == [
        ("RC-MASK-4", "screen-80")
    ]


def test_candidate_report_uses_conditions_present_in_custom_plan(tmp_path: Path) -> None:
    archive = tmp_path / "capture.zip"
    archive.write_bytes(b"diagnostic")
    artifacts = Path("training/artifacts/structural").resolve()
    session = CandidateSession(
        session_id="a" * 24,
        case_id="RC-MASK-4",
        ground_truth="clean",
        distance="screen-80",
        repeat_index=1,
        frames_captured=5,
        frames_received=3,
        frames_at_least_256px=3,
        frames_analyzed=3,
        minimum_crop_side=260,
        maximum_crop_side=280,
        consensus="median_score_majority_class",
        quality_status="marginal",
        quality_conditions="overexposure",
        p_structural_raw=0.8,
        p_structural_effective=0.8,
        structural_type="adversarial",
        verdict="blocked",
        outcome="false_block",
        elapsed_ms=120,
    )

    summary = _summary(archive, [session], artifacts, 3)

    assert [(row["case_id"], row["distance"]) for row in summary["matrix"]] == [
        ("RC-MASK-4", "screen-80")
    ]
