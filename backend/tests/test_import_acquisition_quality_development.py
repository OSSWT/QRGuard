import csv
import hashlib
import json
from pathlib import Path

from scripts import import_acquisition_quality_development as importer
from scripts.analyze_live_camera_diagnostic import ValidatedFrame


def _frame(index: int, *, clean: bool) -> ValidatedFrame:
    crop = f"crop-{index}".encode()
    clean_index = index if clean else index - 90
    case_index = clean_index // 15 if clean else 0
    session_index = clean_index // 5 if clean else clean_index // 5
    distance_index = session_index % 3
    return ValidatedFrame(
        session_id=f"{'clean' if clean else 'attack'}-{session_index:02d}",
        case_id=f"clean-{case_index}" if clean else "attack",
        ground_truth="clean" if clean else "adversarial",
        distance=f"distance-{distance_index}",
        repeat_index=0,
        frame_index=clean_index % 5,
        crop_name=f"crop-{index}.png",
        crop_sha256=hashlib.sha256(crop).hexdigest(),
        crop_png=crop,
        crop_width=300,
        crop_height=300,
        frame_width=1000,
        frame_height=1000,
        corner_coordinates=(0, 0, 1, 0, 1, 1, 0, 1),
        qr_coverage=0.1,
        payload_sha256=f"{case_index:064x}" if clean else "f" * 64,
    )


def test_importer_admits_only_clean_development_frames(tmp_path: Path, monkeypatch):
    archive = tmp_path / "capture.zip"
    archive.write_bytes(b"validated archive")
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": f"clean-{index}",
                        "metadata": {
                            "qr_version": index + 3,
                            "module_count": 29 + 4 * index,
                            "payload_utf8_bytes": 20 + index,
                        },
                    }
                    for index in range(6)
                ],
                "distances": [
                    {
                        "id": "distance-0",
                        "metadata": {"exposure_role": "baseline"},
                    },
                    {
                        "id": "distance-1",
                        "metadata": {"exposure_role": "overexposure_stress"},
                    },
                    {
                        "id": "distance-2",
                        "metadata": {"exposure_role": "underexposure_stress"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    frames = [
        *[_frame(index, clean=True) for index in range(90)],
        *[_frame(index, clean=False) for index in range(90, 120)],
    ]
    monkeypatch.setattr(importer, "ROOT", tmp_path)
    monkeypatch.setattr(
        importer,
        "EXPECTED_ARCHIVE_SHA256",
        hashlib.sha256(archive.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(importer, "validate_archive", lambda _archive, _plan: frames)

    output = tmp_path / "data/acquisition_quality_development/test"
    audit = importer.import_archive(archive, plan, output)
    rows = list(csv.DictReader((output / "manifest.csv").open(encoding="utf-8")))

    assert audit["admitted_clean_frames"] == 90
    assert audit["admitted_sessions"] == 18
    assert audit["rows_by_quality_condition"] == {
        "normal": 30,
        "overexposure": 30,
        "underexposure": 30,
    }
    assert len(rows) == 90
    assert {row["label"] for row in rows} == {"clean"}
    assert {row["split"] for row in rows} == {"train"}
    assert {row["deployment_holdout_eligible"].lower() for row in rows} == {
        "false"
    }
    assert not {"payload", "payload_text", "raw_payload"} & set(rows[0])
    assert all((tmp_path / row["path"]).is_file() for row in rows)
