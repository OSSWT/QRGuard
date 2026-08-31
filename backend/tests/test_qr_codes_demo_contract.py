"""Integrity checks for the public supervisor QR demonstration pack."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "ml_training/datasets/qr_codes_demo"


def _json(name: str) -> dict:
    return json.loads((PACK / name).read_text(encoding="utf-8"))


def test_demo_manifest_has_the_declared_scope_and_no_training_role():
    manifest = _json("MANIFEST.json")
    cases = manifest["cases"]
    assert manifest["pack_id"] == "qr-codes-demo-2026-08-31-r01-r05"
    assert manifest["case_count"] == 42 == len(cases)
    assert manifest["independent_performance_claim"] is False
    assert sum(case["category"] == "structural" for case in cases) == 30
    assert sum(case["category"] == "semantic_or_payload" for case in cases) == 12
    assert len({case["case_id"] for case in cases}) == 42
    assert all(case["demo_role"] == "demo_only" for case in cases)
    assert not any(case["independent_evaluation"] for case in cases)

    for case in cases:
        image = PACK / case["image_path"]
        assert image.is_file()
        assert hashlib.sha256(image.read_bytes()).hexdigest() == case["image_sha256"]


def test_local_and_deployed_automated_results_match_all_intended_outcomes():
    manifest_ids = {case["case_id"] for case in _json("MANIFEST.json")["cases"]}
    for target in ("LOCAL", "REMOTE"):
        evidence = _json(f"AUTOMATED_RESULTS_{target}.json")
        assert evidence["case_count"] == 42
        assert evidence["request_count"] == 84
        assert evidence["summary"] == {
            "gallery_matches_intended": 42,
            "camera_simulation_matches_intended": 42,
            "all_requests_http_200": True,
        }
        assert {row["case_id"] for row in evidence["results"]} == manifest_ids


def test_physical_live_camera_results_remain_honestly_pending():
    with (PACK / "ACTUAL_RESULTS.csv").open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 42
    assert all(row["local_gallery"] != "pending" for row in rows)
    assert all(row["remote_gallery"] != "pending" for row in rows)
    assert all(row["live_camera"] == "pending" for row in rows)
    assert all(row["screenshot"] == "pending" for row in rows)


def test_demo_sha256_manifest_matches_every_pack_file():
    declared = {}
    for line in (PACK / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split(" *", 1)
        declared[relative] = digest
    actual = {
        path.relative_to(PACK).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in PACK.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS.txt"
    }
    assert declared == actual
