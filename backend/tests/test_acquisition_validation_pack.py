from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_acquisition_validation_pack import CAMPAIGN_ID, build_pack


def test_compact_screen_only_acquisition_pack(tmp_path: Path) -> None:
    output = tmp_path / "pack"
    plan_path = tmp_path / "capture_plan.json"
    report = build_pack(output, plan_path=plan_path, archive_path=None)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert report["pack_id"] == CAMPAIGN_ID
    assert report["case_count"] == 8
    assert report["condition_count"] == 3
    assert report["target_sessions"] == 24
    assert report["target_frames"] == 120
    assert report["screen_only"] is True
    assert report["maximum_viewer_scale_percent"] == 100
    assert plan["frames_per_session"] == 5
    assert plan["repeats_per_distance"] == 1
    assert {row["metadata"]["screen_scale_percent"] for row in plan["distances"]} == {80, 100}

    cases = {row["case_id"]: row for row in plan["cases"]}
    assert cases["SEM-11-PLAIN-TEXT"]["metadata"]["module_count"] == 29
    assert cases["SEM-05-USERINFO"]["metadata"]["semantic_regression_sentinel"] is True
    assert cases["ACQ-CLN-V10-LONG"]["metadata"]["qr_version"] == 10
    assert cases["ACQ-CLN-V14-LONG"]["metadata"]["qr_version"] == 14
    assert {row["ground_truth"] for row in plan["cases"]} == {
        "clean",
        "adversarial",
        "tampered",
    }
    for row in report["cases"]:
        card = output / row["card_path"]
        assert hashlib.sha256(card.read_bytes()).hexdigest() == row["card_sha256"]
