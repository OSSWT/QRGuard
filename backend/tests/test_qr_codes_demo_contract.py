"""Integrity checks for the public supervisor QR demonstration pack."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "ml_training/datasets/qr_codes_demo"
SEM_11_SHA256 = "77c08242bc486c603a995108b1b7f2ac945f5b8acd01a3398abff030f568415e"


def _json(name: str) -> dict:
    return json.loads((PACK / name).read_text(encoding="utf-8"))


def test_demo_manifest_has_the_declared_scope_and_no_training_role():
    manifest = _json("MANIFEST.json")
    cases = manifest["cases"]
    assert manifest["pack_id"] == "qrguard-presentation-demo-r07"
    assert manifest["model_lock"] == {
        "structural": "structural-r07-corrective-v1",
        "semantic": "semantic-2026.02",
        "decision": "decision-2026.03-r05",
    }
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


def test_quick_presentation_covers_every_declared_demo_type():
    with (PACK / "QUICK_DEMO_ORDER.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        rows = list(csv.DictReader(handle))
    ids = {row["case_id"] for row in rows}
    assert len(rows) == 15
    assert {"STR-CLN-NORMAL", "STR-ADV-NORMAL", "STR-TMP-NORMAL"} <= ids
    assert {f"SEM-{index:02d}-{suffix}" for index, suffix in (
        (1, "SAFE-HTTPS"),
        (2, "BRAND-PHISH"),
        (3, "RAW-IP"),
        (4, "PUNYCODE"),
        (5, "USERINFO"),
        (6, "DEEP-SUBDOMAINS"),
        (7, "SHORTENER"),
        (8, "JAVASCRIPT"),
        (9, "WIFI-OPEN"),
        (10, "WIFI-SECURE"),
        (11, "PLAIN-TEXT"),
        (12, "DUITNOW-DUMMY"),
    )} <= ids
    assert (PACK / "PRESENTATION_DEMO.html").is_file()
    assert (PACK / "PRESENTATION_GUIDE.md").is_file()


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


def test_canonical_sem_11_is_safe_across_three_temporal_consensus_scans():
    from PIL import Image
    from structural.qr_decoder import decode_and_crop_qrs

    sem_11 = PACK / "Semantic_and_Payload_Cases/SEM-11-PLAIN-TEXT.png"
    assert hashlib.sha256(sem_11.read_bytes()).hexdigest() == SEM_11_SHA256
    with Image.open(sem_11) as card:
        detections = decode_and_crop_qrs(card.convert("RGB"))
    assert len(detections) == 1
    payload, crop = detections[0]
    assert payload == "QRGuard demo order 4471"

    frames = []
    for index in range(3):
        frame = crop.copy().convert("RGB")
        frame.putpixel((index, 0), (250 - index, 250 - index, 250 - index))
        output = io.BytesIO()
        frame.save(output, "PNG")
        frames.append(output.getvalue())

    os.environ["QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS"] = str(
        (ROOT / "training/artifacts/structural").resolve()
    )
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        for _ in range(3):
            response = client.post(
                "/scan",
                data={
                    "payload": payload,
                    "image_source": "camera",
                    "camera_evidence_policy": "temporal_consensus_v1",
                },
                files=[
                    ("images", (f"sem-11-{index}.png", raw, "image/png"))
                    for index, raw in enumerate(frames)
                ],
            )
            assert response.status_code == 200
            body = response.json()
            assert body["verdict"] == "safe"
            assert body["branch_scores"]["structural_type"] == "clean"
            assert body["branch_scores"]["structural_frames_analyzed"] == 3
