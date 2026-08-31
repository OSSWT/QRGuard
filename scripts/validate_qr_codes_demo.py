"""Validate the QR_Codes_Demo pack through QRGuard's production scan contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "ml_training/datasets/qr_codes_demo"
MANIFEST = PACK / "MANIFEST.json"
ACTUAL_RESULTS = PACK / "ACTUAL_RESULTS.csv"
DEFAULT_REMOTE_URL = "https://qrguard-api-osswt.onrender.com"

RESULT_FIELDS = (
    "case_id",
    "local_gallery",
    "local_camera_simulation",
    "remote_gallery",
    "remote_camera_simulation",
    "live_camera",
    "screenshot",
    "notes",
)


class LocalClient:
    """Small adapter so local TestClient and remote httpx share one interface."""

    def __init__(self) -> None:
        artifact_dir = (ROOT / "training/artifacts/structural").resolve()
        os.environ["QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS"] = str(artifact_dir)
        sys.path.insert(0, str(ROOT / "backend"))
        from app.main import app
        from fastapi.testclient import TestClient

        self._client = TestClient(app)

    def post(self, path: str, **kwargs: Any):
        return self._client.post(path, **kwargs)

    def close(self) -> None:
        self._client.close()


def _camera_crop(path: Path, expected_payload: str) -> bytes:
    sys.path.insert(0, str(ROOT / "backend"))
    from structural.qr_decoder import decode_and_crop_qrs

    with Image.open(path) as image:
        detections = decode_and_crop_qrs(image)
    if len(detections) != 1:
        raise RuntimeError(
            f"Expected exactly one readable QR in {path}, got {len(detections)}"
        )
    payload, crop = detections[0]
    if payload != expected_payload:
        raise RuntimeError(f"Decoded payload mismatch for {path}")
    output = io.BytesIO()
    crop.save(output, format="PNG")
    return output.getvalue()


def _request(client: Any, case: dict[str, Any], source: str) -> dict[str, Any]:
    image_path = PACK / case["image_path"]
    if source == "gallery":
        data = {"image_source": "gallery"}
        image_bytes = image_path.read_bytes()
        filename = image_path.name
    else:
        data = {
            "payload": case["decoded_payload"],
            "image_source": "camera",
        }
        image_bytes = _camera_crop(image_path, case["decoded_payload"])
        filename = f"{case['case_id']}-camera-crop.png"

    started = datetime.now(UTC)
    response = client.post(
        "/scan",
        data=data,
        files={"image": (filename, image_bytes, "image/png")},
    )
    elapsed_ms = round((datetime.now(UTC) - started).total_seconds() * 1000)
    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text[:500]}

    result: dict[str, Any] = {
        "http_status": response.status_code,
        "request_elapsed_ms": elapsed_ms,
    }
    if response.status_code != 200:
        result["error"] = body
        return result

    branch = body.get("branch_scores", {})
    result.update(
        {
            "verdict": body.get("verdict"),
            "risk_score": body.get("risk_score"),
            "partial_analysis": body.get("partial_analysis"),
            "payload_source": body.get("payload_source"),
            "payload_type": body.get("payload_type"),
            "rule_flags": body.get("rule_flags", []),
            "reasons": body.get("reasons", []),
            "structural_status": branch.get("structural_status"),
            "structural_type": branch.get("structural_type"),
            "p_structural": branch.get("p_structural"),
            "p_structural_raw": branch.get("p_structural_raw"),
            "structural_quality_status": branch.get("structural_quality_status"),
            "structural_quality_conditions": branch.get(
                "structural_quality_conditions", []
            ),
            "structural_rescan_reason": branch.get("structural_rescan_reason"),
            "semantic_status": branch.get("semantic_status"),
            "p_url": branch.get("p_url"),
            "server_elapsed_ms": body.get("elapsed_ms"),
        }
    )
    return result


def _display(result: dict[str, Any]) -> str:
    if result["http_status"] != 200:
        return f"HTTP {result['http_status']}"
    partial = "; partial" if result.get("partial_analysis") else ""
    return f"{result['verdict']} ({result['risk_score']}){partial}"


def _matches_intended(result: dict[str, Any], intended: str) -> bool:
    return (
        result.get("http_status") == 200 and result.get("verdict") == intended.lower()
    )


def _write_hashes() -> None:
    rows = []
    for path in sorted(PACK.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(f"{digest} *{path.relative_to(PACK).as_posix()}")
    (PACK / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _load_actual_rows(case_ids: list[str]) -> list[dict[str, str]]:
    existing: dict[str, dict[str, str]] = {}
    if ACTUAL_RESULTS.exists():
        with ACTUAL_RESULTS.open(newline="", encoding="utf-8-sig") as handle:
            existing = {row["case_id"]: row for row in csv.DictReader(handle)}
    rows = []
    for case_id in case_ids:
        old = existing.get(case_id, {})
        rows.append(
            {
                field: (
                    case_id
                    if field == "case_id"
                    else old.get(field, "pending")
                    if field not in {"notes"}
                    else old.get(field, "")
                )
                for field in RESULT_FIELDS
            }
        )
    return rows


def _save_actual_rows(rows: list[dict[str, str]]) -> None:
    with ACTUAL_RESULTS.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _validate(target: str, remote_url: str) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = manifest["cases"]
    if target == "local":
        client: Any = LocalClient()
        target_label = (
            "in-process locked production stack with "
            "QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS=training/artifacts/structural"
        )
    else:
        client = httpx.Client(base_url=remote_url.rstrip("/"), timeout=90.0)
        target_label = remote_url.rstrip("/")

    results = []
    try:
        for index, case in enumerate(cases, start=1):
            gallery = _request(client, case, "gallery")
            camera = _request(client, case, "camera")
            results.append(
                {
                    "case_id": case["case_id"],
                    "category": case["category"],
                    "intended_verdict": case["intended_verdict"],
                    "gallery_matches_intended": _matches_intended(
                        gallery, case["intended_verdict"]
                    ),
                    "camera_simulation_matches_intended": _matches_intended(
                        camera, case["intended_verdict"]
                    ),
                    "gallery": gallery,
                    "camera_simulation": camera,
                }
            )
            print(
                f"[{index:02d}/{len(cases)}] {case['case_id']}: "
                f"gallery={_display(gallery)} camera={_display(camera)}",
                flush=True,
            )
    finally:
        client.close()

    generated_at = datetime.now(UTC).isoformat()
    gallery_matches = sum(row["gallery_matches_intended"] for row in results)
    camera_matches = sum(row["camera_simulation_matches_intended"] for row in results)
    output = {
        "schema_version": 1,
        "pack_id": manifest["pack_id"],
        "generated_at": generated_at,
        "target": target,
        "target_label": target_label,
        "camera_mode": (
            "API simulation using the manifest payload plus a locally decoded and "
            "perspective-corrected QR crop; not physical Live Camera evidence"
        ),
        "case_count": len(results),
        "request_count": len(results) * 2,
        "summary": {
            "gallery_matches_intended": gallery_matches,
            "camera_simulation_matches_intended": camera_matches,
            "all_requests_http_200": all(
                result[source]["http_status"] == 200
                for result in results
                for source in ("gallery", "camera_simulation")
            ),
        },
        "results": results,
    }
    output_path = PACK / f"AUTOMATED_RESULTS_{target.upper()}.json"
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    actual_rows = _load_actual_rows([case["case_id"] for case in cases])
    row_by_id = {row["case_id"]: row for row in actual_rows}
    for result in results:
        row = row_by_id[result["case_id"]]
        row[f"{target}_gallery"] = _display(result["gallery"])
        row[f"{target}_camera_simulation"] = _display(result["camera_simulation"])
    _save_actual_rows(actual_rows)
    _write_hashes()
    print(
        f"Wrote {output_path.relative_to(ROOT)} and updated {ACTUAL_RESULTS.relative_to(ROOT)}"
    )
    if gallery_matches != len(results) or camera_matches != len(results):
        raise SystemExit(
            f"Intended-result mismatch: gallery {gallery_matches}/{len(results)}, "
            f"camera simulation {camera_matches}/{len(results)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("local", "remote"), default="local")
    parser.add_argument("--remote-url", default=DEFAULT_REMOTE_URL)
    args = parser.parse_args()
    _validate(args.target, args.remote_url)


if __name__ == "__main__":
    main()
