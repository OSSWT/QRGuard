import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from ml_training.structural.src import structural_recipes
from ml_training.structural.src.train_local import (
    _deployment_validation_metrics,
    _sampler,
)
from scripts.import_prepared_gallery_references import import_references


def _pack_row(
    number: int, case_id: str, label: str, split: str, payload: str, image: Path
):
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    return {
        "number": number,
        "case_id": case_id,
        "label": label,
        "quality_condition": "normal",
        "quality_severity": "none",
        "assigned_split": split,
        "gallery_reference": f"scan_with_gallery/{image.name}",
        "payload_sha256": payload,
        "reference_sha256": digest,
        "attack_method": "none",
        "manipulation_method": "none",
    }


def test_importer_verifies_references_and_excludes_locked_test(tmp_path: Path):
    pack = tmp_path / "pack"
    gallery = pack / "scan_with_gallery"
    gallery.mkdir(parents=True)
    rows = []
    for number, (case_id, label, split) in enumerate(
        (
            ("cln-normal-01", "clean", "train"),
            ("adv-normal-01", "adversarial", "validation"),
            ("tmp-normal-01", "tampered", "test"),
        ),
        start=1,
    ):
        image = gallery / f"{number}.png"
        image.write_bytes(f"reference-{number}".encode())
        rows.append(_pack_row(number, case_id, label, split, f"{number:064x}", image))
    (pack / "capture_index.json").write_text(
        json.dumps(
            {
                "campaign_id": "structural-v3-real-2026.03-r01",
                "scope_name": "test-pack",
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "data/prepared_gallery_references/structural-2026.03-r01"
    audit = import_references([pack], output, root=tmp_path)
    imported = list(csv.DictReader((output / "manifest.csv").open(encoding="utf-8")))

    assert [row["split"] for row in imported] == ["validation", "train"]
    assert all(row["split"] != "test" for row in imported)
    assert audit["imported_references"] == 2
    assert audit["excluded_test_references"] == 1
    assert audit["test_rows_written"] == 0


def test_prepared_gallery_loader_rejects_test_rows(tmp_path: Path, monkeypatch):
    root = tmp_path
    reference = root / "data/prepared_gallery_references/v3/images/clean/case.png"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"reference")
    manifest = reference.parents[2] / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "label", "split", "payload_hash", "case_id"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "path": reference.relative_to(root).as_posix(),
                "label": "clean",
                "split": "test",
                "payload_hash": "a" * 64,
                "case_id": "cln-normal-01",
            }
        )
    monkeypatch.setattr(structural_recipes, "ROOT", root)
    monkeypatch.setattr(structural_recipes, "VERSION", "v3")
    monkeypatch.setattr(structural_recipes, "IS_V3", True)

    with pytest.raises(ValueError, match="exclude the locked test split"):
        structural_recipes._prepared_gallery_reference_rows()


def test_sampler_allocates_mass_by_domain_not_sparse_source():
    rows = []
    for class_id, label in enumerate(("clean", "adversarial", "tampered")):
        sources = (
            ["qrguard_runtime_v3_camera"] * 2
            + ["qrguard_prepared_gallery_reference"] * 3
            + ["qrguard_runtime_v3_gallery"]
            + ["procedural_qrguard"] * 5
        )
        rows.extend(
            {"class_id": class_id, "label": label, "source": source}
            for source in sources
        )
    frame = pd.DataFrame(rows)
    weights = _sampler(frame).weights.numpy()

    for class_id in (0, 1, 2):
        class_mask = frame.class_id.to_numpy() == class_id
        sources = frame.source.to_numpy()
        camera = class_mask & (sources == "qrguard_runtime_v3_camera")
        gallery = (
            class_mask
            & pd.Series(sources)
            .isin(
                [
                    "qrguard_prepared_gallery_reference",
                    "qrguard_runtime_v3_gallery",
                ]
            )
            .to_numpy()
        )
        other = class_mask & (sources == "procedural_qrguard")
        assert weights[camera].sum() == pytest.approx((1 / 3) * 0.40)
        assert weights[gallery].sum() == pytest.approx((1 / 3) * 0.30)
        assert weights[other].sum() == pytest.approx((1 / 3) * 0.30)
        assert len(set(weights[gallery])) == 1


def test_checkpoint_selection_uses_only_non_test_paired_domains():
    frame = pd.DataFrame(
        [
            {
                "class_id": 0,
                "source": "qrguard_runtime_v3_camera",
                "group_id": "clean",
            },
            {
                "class_id": 0,
                "source": "qrguard_prepared_gallery_reference",
                "group_id": "clean",
            },
            {
                "class_id": 2,
                "source": "qrguard_runtime_v3_camera",
                "group_id": "tampered",
            },
            {
                "class_id": 2,
                "source": "qrguard_prepared_gallery_reference",
                "group_id": "tampered",
            },
            {"class_id": 0, "source": "QR-DN1.0", "group_id": "external"},
        ]
    )
    probabilities = pd.DataFrame(
        [
            [0.9, 0.05, 0.05],
            [0.8, 0.1, 0.1],
            [0.0, 0.0, 1.0],
            [0.1, 0.1, 0.8],
            [0.0, 1.0, 0.0],
        ]
    ).to_numpy()

    metrics = _deployment_validation_metrics(frame, probabilities)

    assert metrics["rows"] == 4
    assert metrics["paired_groups"] == 2
    assert metrics["paired_verdict_agreement"] == 1.0
    assert metrics["macro_f1"] == pytest.approx(2 / 3)
