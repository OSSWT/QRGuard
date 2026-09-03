"""Run the controlled SEM-11 pack through the locked local production stack."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "dist/SEM11_Root_Cause_Test_Pack"
DEFAULT_ARTIFACTS = ROOT / "training/artifacts/structural"


def _crop(card: Path, payload: str) -> Image.Image:
    sys.path.insert(0, str(ROOT / "backend"))
    from structural.qr_decoder import decode_and_crop_qrs

    with Image.open(card) as image:
        detections = decode_and_crop_qrs(image.convert("RGB"))
    if len(detections) != 1 or detections[0][0] != payload:
        raise RuntimeError(f"Could not recover expected QR from {card}")
    return detections[0][1].convert("RGB")


def _png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _result(response: Any) -> dict[str, Any]:
    body = response.json()
    if response.status_code != 200:
        return {"http_status": response.status_code, "error": body}
    branch = body["branch_scores"]
    return {
        "http_status": 200,
        "verdict": body["verdict"],
        "risk_score": body["risk_score"],
        "reasons": body["reasons"],
        "structural_type": branch["structural_type"],
        "p_structural": branch["p_structural"],
        "p_structural_raw": branch["p_structural_raw"],
        "semantic_status": branch["semantic_status"],
        "structural_frames_analyzed": branch["structural_frames_analyzed"],
    }


def evaluate(pack: Path, artifacts: Path, output: Path) -> dict[str, Any]:
    manifest = json.loads((pack / "MANIFEST.json").read_text(encoding="utf-8"))
    artifacts = artifacts.resolve(strict=True)
    os.environ["QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS"] = str(artifacts)
    sys.path.insert(0, str(ROOT / "backend"))
    from app.main import app
    from fastapi.testclient import TestClient

    rows = []
    with TestClient(app) as client:
        for case in manifest["cases"]:
            card = pack / case["image_path"]
            gallery = _result(
                client.post(
                    "/scan",
                    data={"image_source": "gallery"},
                    files={"image": (card.name, card.read_bytes(), "image/png")},
                )
            )
            crop = _crop(card, case["payload"])
            frames = []
            for index in range(3):
                frame = crop.copy()
                frame.putpixel((index, 0), (250 - index, 250 - index, 250 - index))
                frames.append(_png(frame))
            camera = _result(
                client.post(
                    "/scan",
                    data={
                        "payload": case["payload"],
                        "image_source": "camera",
                        "camera_evidence_policy": "temporal_consensus_v1",
                    },
                    files=[
                        ("images", (f"{case['case_id']}-{index}.png", raw, "image/png"))
                        for index, raw in enumerate(frames)
                    ],
                )
            )
            rows.append(
                {
                    "case_id": case["case_id"],
                    "actual_version": case["actual_version"],
                    "actual_mask": case["actual_mask"],
                    "gallery": gallery,
                    "camera_simulation": camera,
                }
            )

    def passes(result: dict[str, Any]) -> bool:
        return (
            result.get("http_status") == 200
            and result.get("verdict") == "safe"
            and result.get("structural_type") == "clean"
            and result.get("semantic_status") == "not_applicable"
        )

    request_count = len(rows) * 2
    passed = sum(
        passes(row[source])
        for row in rows
        for source in ("gallery", "camera_simulation")
    )
    report = {
        "schema_version": 1,
        "pack_id": manifest["pack_id"],
        "artifacts": str(artifacts),
        "model_sha256": hashlib.sha256(
            (artifacts / "structural_fp32.onnx").read_bytes()
        ).hexdigest(),
        "mode": "digital baseline; camera simulation is not physical Live Camera evidence",
        "summary": {
            "case_count": len(rows),
            "request_count": request_count,
            "branch_contract_matches": passed,
            "gate_passed": passed == request_count,
        },
        "results": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pack = args.pack.resolve(strict=True)
    output = (
        args.output.resolve() if args.output else pack / "AUTOMATED_RESULTS_LOCAL.json"
    )
    report = evaluate(pack, args.artifacts, output)
    print(f"Wrote {output}")
    print(json.dumps(report["summary"], indent=2))
    if not report["summary"]["gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
