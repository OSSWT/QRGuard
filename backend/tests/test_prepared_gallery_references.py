import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml_training.structural.src import structural_recipes
from ml_training.structural.src.train_local import (
    _deployment_validation_metrics,
    _fit_temperature,
    _sampler,
    _sampling_weights,
    _validate_candidate_manifest_contract,
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


def test_prepared_gallery_loader_uses_configured_frozen_version(
    tmp_path: Path, monkeypatch
):
    root = tmp_path
    config = root / "ml_training/configs/structural-2026.09-r02.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "dataset_references": {
                    "prepared_gallery_version": "structural-2026.03-r01"
                }
            }
        ),
        encoding="utf-8",
    )
    image = (
        root
        / "data/prepared_gallery_references"
        / "structural-2026.03-r01/images/clean/case.png"
    )
    image.parent.mkdir(parents=True)
    image.write_bytes(b"reference")
    manifest = image.parents[2] / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "label", "split", "payload_hash", "case_id"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "path": image.relative_to(root).as_posix(),
                "label": "clean",
                "split": "train",
                "payload_hash": "a" * 64,
                "case_id": "clean-case",
            }
        )
    monkeypatch.setattr(structural_recipes, "ROOT", root)
    monkeypatch.setattr(structural_recipes, "VERSION", "structural-2026.09-r02")
    monkeypatch.setattr(structural_recipes, "IS_V3", True)

    rows = structural_recipes._prepared_gallery_reference_rows()

    assert len(rows) == 1
    assert rows[0]["source"] == "qrguard_prepared_gallery_reference"


def test_acquisition_quality_loader_is_opt_in_and_train_only(
    tmp_path: Path, monkeypatch
):
    config = tmp_path / "ml_training/configs/structural-2026.09-r04.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "dataset_references": {
                    "acquisition_quality_development_version": "2026-09-r02"
                }
            }
        ),
        encoding="utf-8",
    )
    image = tmp_path / "data/acquisition_quality_development/acquisition_quality_release_r02/crop.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"clean-hard-negative")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    manifest = image.parent / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path",
                "label",
                "split",
                "development_only",
                "deployment_holdout_eligible",
                "crop_sha256",
            ],
        )
        writer.writeheader()
        for _ in range(90):
            writer.writerow(
                {
                    "path": image.relative_to(tmp_path).as_posix(),
                    "label": "clean",
                    "split": "train",
                    "development_only": True,
                    "deployment_holdout_eligible": False,
                    "crop_sha256": digest,
                }
            )
    (image.parent / "audit.json").write_text(
        json.dumps(
            {
                "admitted_clean_frames": 90,
                "source_archive_sha256": (
                    "02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4"
                ),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(structural_recipes, "ROOT", tmp_path)
    monkeypatch.setattr(structural_recipes, "VERSION", "structural-2026.09-r04")

    rows = structural_recipes._acquisition_quality_development_rows()

    assert len(rows) == 90
    assert {row["label"] for row in rows} == {"clean"}
    assert {row["split"] for row in rows} == {"train"}


def test_candidate_manifest_contract_rejects_missing_rows(tmp_path: Path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("path,label\na.png,clean\n", encoding="utf-8")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="rows 1 != locked 2"):
        _validate_candidate_manifest_contract(
            manifest,
            {"candidate_manifest": {"rows": 2, "sha256": digest}},
        )


def test_candidate_manifest_contract_accepts_exact_identity(tmp_path: Path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("path,label\na.png,clean\n", encoding="utf-8")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()

    _validate_candidate_manifest_contract(
        manifest,
        {"candidate_manifest": {"rows": 1, "sha256": digest}},
    )


def test_adversarial_manifest_order_is_independent_of_cache_generation_order():
    fresh_order = [
        {"group_id": "group-2", "attack_recipe": "fgsm", "path": "2.png"},
        {"group_id": "group-1", "attack_recipe": "pgd20", "path": "1.png"},
    ]
    cached_order = list(reversed(fresh_order))

    expected = structural_recipes._canonical_adversarial_rows(fresh_order)

    assert structural_recipes._canonical_adversarial_rows(cached_order) == expected
    assert [row["group_id"] for row in expected] == ["group-1", "group-2"]


def test_sampler_allocates_mass_by_domain_not_sparse_source():
    rows = []
    for class_id, label in enumerate(("clean", "adversarial", "tampered")):
        sources = (
            ["qrguard_runtime_v3_camera"] * 2
            + ["qrguard_coverage_2026_09_camera"] * 2
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
        camera = class_mask & pd.Series(sources).isin(
            ["qrguard_runtime_v3_camera", "qrguard_coverage_2026_09_camera"]
        ).to_numpy()
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


def test_source_family_sampler_keeps_procedural_classes_equally_represented():
    rows = []
    sources_by_label = {
        "clean": (
            ["procedural_qrguard"] * 10
            + ["QR-DN1.0"] * 40
            + ["qr_codes_in_surfaces"] * 3
            + ["qrguard_runtime_v3_camera"] * 2
            + ["qrguard_physical_attack_2026_09_camera"] * 2
            + ["qrguard_prepared_gallery_reference"] * 2
        ),
        "adversarial": (
            ["procedural_qrguard"] * 10
            + ["qrguard_runtime_v3_camera"] * 2
            + ["qrguard_physical_attack_2026_09_camera"] * 2
            + ["qrguard_prepared_gallery_reference"] * 2
        ),
        "tampered": (
            ["procedural_qrguard"] * 10
            + ["qrguard_runtime_v3_camera"] * 4
            + ["qrguard_prepared_gallery_reference"] * 2
        ),
    }
    for class_id, label in enumerate(("clean", "adversarial", "tampered")):
        rows.extend(
            {"class_id": class_id, "label": label, "source": source}
            for source in sources_by_label[label]
        )
    frame = pd.DataFrame(rows)
    policy = {
        "source_family_draw_fractions": {
            "clean": {
                "procedural": 0.40,
                "camera": 0.35,
                "gallery": 0.20,
                "public_clean": 0.05,
            },
            "adversarial": {
                "procedural": 0.40,
                "camera": 0.35,
                "gallery": 0.25,
            },
            "tampered": {
                "procedural": 0.40,
                "camera": 0.35,
                "gallery": 0.25,
            },
        }
    }

    weights = _sampling_weights(frame, policy)

    assert weights.sum() == pytest.approx(1.0)
    for class_id in (0, 1, 2):
        class_mask = frame.class_id.to_numpy() == class_id
        procedural = class_mask & (
            frame.source.to_numpy() == "procedural_qrguard"
        )
        assert weights[class_mask].sum() == pytest.approx(1 / 3)
        assert weights[procedural].sum() == pytest.approx((1 / 3) * 0.40)
    physical_camera = frame.source.to_numpy() == (
        "qrguard_physical_attack_2026_09_camera"
    )
    assert weights[physical_camera].sum() > 0


def test_source_family_sampler_can_prioritize_hard_negatives_within_camera():
    rows = []
    for class_id, label in enumerate(("clean", "adversarial", "tampered")):
        rows.extend(
            {
                "class_id": class_id,
                "label": label,
                "source": source,
            }
            for source in (
                "procedural_qrguard",
                "qrguard_runtime_v3_camera",
                "qrguard_acquisition_quality_2026_09_camera",
                "qrguard_prepared_gallery_reference",
            )
        )
    frame = pd.DataFrame(rows)
    policy = {
        "source_family_draw_fractions": {
            label: {"procedural": 0.4, "camera": 0.4, "gallery": 0.2}
            for label in ("clean", "adversarial", "tampered")
        },
        "source_multipliers": {
            "qrguard_acquisition_quality_2026_09_camera": 3.0
        },
    }

    weights = _sampling_weights(frame, policy)
    sources = frame.source.to_numpy()
    for class_id in (0, 1, 2):
        class_mask = frame.class_id.to_numpy() == class_id
        hard_negative = class_mask & (
            sources == "qrguard_acquisition_quality_2026_09_camera"
        )
        runtime = class_mask & (sources == "qrguard_runtime_v3_camera")
        camera = hard_negative | runtime
        assert weights[camera].sum() == pytest.approx((1 / 3) * 0.4)
        assert weights[hard_negative].sum() == pytest.approx(
            3 * weights[runtime].sum()
        )


def test_weighted_temperature_rejects_invalid_sample_weights():
    logits = pd.DataFrame([[2.0, 0.0, -1.0], [0.0, 2.0, -1.0]]).to_numpy()
    labels = pd.Series([0, 1]).to_numpy()

    with pytest.raises(ValueError, match="must match labels"):
        _fit_temperature(logits, labels, pd.Series([1.0]).to_numpy())
    with pytest.raises(ValueError, match="must be positive"):
        _fit_temperature(logits, labels, pd.Series([1.0, 0.0]).to_numpy())


def test_weighted_temperature_returns_a_positive_finite_value():
    logits = pd.DataFrame(
        [[3.0, 0.0, -1.0], [0.0, 3.0, -1.0], [2.0, 0.5, -1.0]]
    ).to_numpy()
    labels = pd.Series([0, 1, 1]).to_numpy()
    weights = pd.Series([0.2, 0.2, 0.6]).to_numpy()

    temperature = _fit_temperature(logits, labels, weights)

    assert np.isfinite(temperature)
    assert temperature > 0


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


def test_checkpoint_selection_includes_m5_coverage_camera_rows():
    frame = pd.DataFrame(
        [
            {
                "class_id": class_id,
                "source": "qrguard_coverage_2026_09_camera",
                "group_id": f"coverage-{class_id}",
            }
            for class_id in (0, 1, 2)
        ]
    )
    probabilities = pd.DataFrame(
        [[0.9, 0.05, 0.05], [0.05, 0.9, 0.05], [0.05, 0.05, 0.9]]
    ).to_numpy()

    metrics = _deployment_validation_metrics(frame, probabilities)

    assert metrics["rows"] == 3
    assert metrics["macro_f1"] == 1.0
    assert metrics["paired_groups"] == 0


def test_checkpoint_selection_uses_image_source_for_new_camera_evidence():
    frame = pd.DataFrame(
        [
            {
                "class_id": 0,
                "source": "qrguard_acquisition_quality_2026_09_camera",
                "image_source": "camera",
                "group_id": "clean-1",
            },
            {
                "class_id": 0,
                "source": "qrguard_acquisition_quality_2026_09_camera",
                "image_source": "camera",
                "group_id": "clean-2",
            },
            {
                "class_id": 1,
                "source": "qrguard_acquisition_quality_2026_09_camera",
                "image_source": "camera",
                "group_id": "attack",
            },
        ]
    )
    probabilities = np.array(
        [[0.9, 0.05, 0.05], [0.1, 0.85, 0.05], [0.05, 0.9, 0.05]]
    )

    metrics = _deployment_validation_metrics(frame, probabilities)

    assert metrics["rows"] == 3
    assert metrics["camera_clean_false_positive_rate"] == 0.5
