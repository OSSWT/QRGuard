"""Contracts for the reproducible SEM-11 root-cause pack."""

from __future__ import annotations

import json

import cv2

from scripts.build_sem11_diagnostic_plan import build_capture_plan
from scripts.build_sem11_root_cause_pack import BASE_PAYLOAD, build_pack


def test_root_cause_pack_controls_layout_mask_and_version(tmp_path):
    output = tmp_path / "pack"
    manifest = build_pack(output)
    assert manifest["case_count"] == 12
    by_id = {case["case_id"]: case for case in manifest["cases"]}
    assert set(by_id) == {
        "RC-LAYOUT-4470",
        "RC-LAYOUT-4471",
        "RC-LAYOUT-4472",
        *(f"RC-MASK-{mask}" for mask in range(8)),
        "RC-VERSION-4",
    }

    for suffix in (4470, 4471, 4472):
        case = by_id[f"RC-LAYOUT-{suffix}"]
        assert case["actual_version"] == 3
        assert case["module_count"] == 29
    for mask in range(8):
        case = by_id[f"RC-MASK-{mask}"]
        assert case["payload"] == BASE_PAYLOAD
        assert case["actual_version"] == 3
        assert case["actual_mask"] == mask
    assert by_id["RC-VERSION-4"]["payload"] == BASE_PAYLOAD
    assert by_id["RC-VERSION-4"]["actual_version"] == 4
    assert by_id["RC-VERSION-4"]["module_count"] == 33

    canonical = by_id["RC-LAYOUT-4471"]
    matching_mask = by_id[f"RC-MASK-{canonical['actual_mask']}"]
    assert canonical["qr_matrix_sha256"] == matching_mask["qr_matrix_sha256"]

    for case in manifest["cases"]:
        image = cv2.imread(str(output / case["image_path"]))
        payload, points, _ = cv2.QRCodeDetector().detectAndDecode(image)
        assert points is not None
        assert payload == case["payload"]

    saved = json.loads((output / "MANIFEST.json").read_text(encoding="utf-8"))
    assert saved == manifest

    plan = build_capture_plan(manifest)
    assert plan["campaign_id"] == "sem11-root-cause-screen-80-2026-09-r01"
    assert plan["frames_per_session"] == 5
    assert plan["repeats_per_distance"] == 3
    assert plan["distances"][0]["metadata"]["screen_scale_percent"] == 80
    assert len(plan["cases"]) * len(plan["distances"]) * 3 == 36
    assert {case["metadata"]["mask_pattern"] for case in plan["cases"]} >= set(
        range(8)
    )
