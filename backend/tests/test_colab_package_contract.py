"""Contract tests for the complete Google Colab ML hand-off."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from ml_training.scripts.validate_performance_bundle import REQUIRED

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "dist/QRGuard_ML_Colab"


@pytest.fixture(scope="module", autouse=True)
def _build_current_colab_package():
    from scripts.build_colab_bundle import build

    build()


def _source(notebook: dict) -> str:
    return "".join("".join(cell.get("source", [])) for cell in notebook["cells"])


def test_colab_code_cells_are_valid_python():
    for notebook_name in (
        "01_Structural_Training_Colab.ipynb",
        "02_Semantic_Training_Colab.ipynb",
        "03_Semantic_Frozen_Report_Colab.ipynb",
        "04_Decision_Frozen_Report_Colab.ipynb",
    ):
        notebook = json.loads((PACKAGE / notebook_name).read_text(encoding="utf-8"))
        for index, cell in enumerate(notebook["cells"]):
            if cell.get("cell_type") == "code":
                ast.parse(
                    "".join(cell.get("source", [])), filename=f"{notebook_name}:{index}"
                )


def test_colab_notebooks_have_complete_phases_and_performance_outputs():
    structural = json.loads(
        (PACKAGE / "01_Structural_Training_Colab.ipynb").read_text(encoding="utf-8")
    )
    semantic_training = json.loads(
        (PACKAGE / "02_Semantic_Training_Colab.ipynb").read_text(encoding="utf-8")
    )
    semantic_frozen = json.loads(
        (PACKAGE / "03_Semantic_Frozen_Report_Colab.ipynb").read_text(encoding="utf-8")
    )
    decision = json.loads(
        (PACKAGE / "04_Decision_Frozen_Report_Colab.ipynb").read_text(encoding="utf-8")
    )
    structural_source = _source(structural)
    semantic_training_source = _source(semantic_training)
    semantic_frozen_source = _source(semantic_frozen)
    decision_source = _source(decision)

    for phase in range(8):
        assert f"Phase {phase}" in structural_source
        assert f"Phase {phase}" in semantic_training_source
    for artifact in REQUIRED["structural"]:
        assert artifact in structural_source or artifact in {
            "metrics.json",
            "STRUCTURAL_PERFORMANCE.md",
        }
    for artifact in REQUIRED["semantic"]:
        assert artifact in semantic_training_source or artifact in {
            "metrics.json",
            "SEMANTIC_PERFORMANCE.md",
        }
    combined = structural_source + semantic_training_source
    assert "C:\\Users\\" not in combined
    assert "MyDrive/QRGuard_ML" in combined
    assert "'runs' / VERSION" in structural_source
    assert "protected = {'torch', 'torchvision'}" in combined
    assert "stderr=subprocess.STDOUT" in combined
    assert "PYTHONUNBUFFERED" in combined
    assert "Bundle SHA-256:" in combined
    for mode in ("fresh", "resume", "evaluate_only", "report_only"):
        assert mode in structural_source
    assert "--checkpoint-dir" in structural_source
    assert "run_identity" in structural_source
    assert "structural-r07-corrective-v1" in structural_source
    assert "QRGUARD_STRUCTURAL_DATASET_VERSION" in structural_source
    assert "ml_training.semantic.src.train_local" in semantic_training_source
    assert "QRGUARD_SEMANTIC_VERSION" in semantic_training_source
    assert "semantic-colab-candidate-v1" in semantic_training_source
    assert "No runtime model, GitHub branch, or deployment was changed." in (
        semantic_training_source
    )
    assert "ml_training.semantic.src.train_local" not in semantic_frozen_source
    assert "semantic-2026.02" in semantic_frozen_source
    assert "decision-2026.03-r05" in decision_source
    assert "promotion_requested" in decision_source


def test_package_manifest_hashes_every_handoff_file():
    manifest = json.loads(
        (PACKAGE / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    declared = {row["path"]: row for row in manifest["files"]}
    actual = {
        path.relative_to(PACKAGE).as_posix(): path
        for path in PACKAGE.rglob("*")
        if path.is_file() and path.name != "PACKAGE_MANIFEST.json"
    }
    assert not any(PACKAGE.name in Path(relative).parts for relative in actual)
    assert set(declared) == set(actual)
    for relative, path in actual.items():
        assert declared[relative]["bytes"] == path.stat().st_size
        assert (
            declared[relative]["sha256"]
            == hashlib.sha256(path.read_bytes()).hexdigest()
        )


def test_package_contains_complete_dataset_catalogue_and_inventory():
    repository = PACKAGE / "QRGuard"
    catalogue = repository / "ml_training/datasets/DATASET_CATALOG.md"
    inventory_path = repository / "ml_training/datasets/DATASET_INVENTORY.json"

    assert catalogue.is_file()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assert inventory["summary"]["all_required_verified"] is True
    assert inventory["summary"]["required_verified"] == 20
    assert inventory["summary"]["optional_verified"] == 1
    assert inventory["summary"]["private_archives_verified"] == 5


def test_colab_zip_is_readable_and_contains_the_manifest():
    archive_path = ROOT / "dist/QRGuard_ML_Colab.zip"
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert {
            member.date_time for member in archive.infolist()
        } == {(1980, 1, 1, 0, 0, 0)}
        assert not any(
            name.startswith("QRGuard_ML_Colab/QRGuard_ML_Colab/")
            for name in archive.namelist()
        )
        assert "QRGuard_ML_Colab/PACKAGE_MANIFEST.json" in archive.namelist()
        assert (
            "QRGuard_ML_Colab/01_Structural_Training_Colab.ipynb" in archive.namelist()
        )
        assert (
            "QRGuard_ML_Colab/02_Semantic_Training_Colab.ipynb"
            in archive.namelist()
        )
        assert (
            "QRGuard_ML_Colab/03_Semantic_Frozen_Report_Colab.ipynb"
            in archive.namelist()
        )
        assert (
            "QRGuard_ML_Colab/04_Decision_Frozen_Report_Colab.ipynb"
            in archive.namelist()
        )


def test_structural_adversarial_wrapper_moves_buffers_to_training_device():
    source = (
        PACKAGE / "QRGuard/ml_training/structural/src/structural_recipes.py"
    ).read_text(encoding="utf-8")

    assert "model = Normalized(victim).to(device).eval()" in source


def test_r07_corrective_training_contract_is_packaged():
    repository = PACKAGE / "QRGuard"
    config = json.loads(
        (
            repository / "ml_training/configs/structural-r07-corrective-v1.json"
        ).read_text(encoding="utf-8")
    )
    source = (
        repository / "ml_training/structural/src/train_local.py"
    ).read_text(encoding="utf-8")

    assert config["training"]["head_epochs"] == 0
    assert config["training"]["finetune_learning_rate"] == 0.000005
    assert config["training"]["initial_checkpoint_sha256"] == (
        "0decc53ea5aabb97f579a13ba1bb3bb012480b96c26c4551e8593f7a297e186f"
    )
    assert config["topology_counterfactuals"]["expected_rows"] == 2560
    assert config["topology_counterfactuals"][
        "train_identities_per_error_correction"
    ] == 3
    assert config["topology_counterfactuals"][
        "validation_identities_per_error_correction"
    ] == 2
    assert config["topology_counterfactuals"]["mask_patterns"] == list(range(8))
    assert config["training"]["sampling"]["source_family_draw_fractions"][
        "clean"
    ]["topology_counterfactual"] == 0.30
    assert config["training"]["topology_consistency_multiplier"] == 2.0
    assert config["deployment_gates"]["synthetic_clean_recall_min"] == 0.90
    assert config["consumed_development_replay"]["clean_frames"] == 80
    assert config["consumed_development_replay"]["verified_attack_frames"] == 10
    assert config["training"]["checkpoint_selection_constraints"][
        "consumed_blind_clean_false_positive_rate"
    ]["maximum"] == 0.0
    assert "HEAD_LEARNING_RATE" in source
    assert "FINETUNE_LEARNING_RATE" in source


def test_package_contains_locked_real_capture_campaign():
    schedule = (
        PACKAGE / "QRGuard/ml_training/structural/campaigns/"
        "structural-v3-real-2026.03-r01/campaign.csv"
    )
    with schedule.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 450
    assert {row["label"] for row in rows} == {"clean", "adversarial", "tampered"}
    assert all(row["gallery_required"] == "True" for row in rows)
    assert all(row["camera_required"] == "True" for row in rows)


def test_package_contains_r07_initial_weights_and_development_data():
    repository = PACKAGE / "QRGuard"
    initial = (
        repository
        / "ml_training/structural/runs/structural-2026.09-r07/"
        "colab-r07-dense-screen-clean-recovery-v1/checkpoints/best_model.pt"
    )
    physical = (
        repository
        / "data/structural_physical_attack_development/physical_attack_release_r02/manifest.csv"
    )
    coverage = (
        repository
        / "data/structural_coverage_development/coverage_development_release_r01/manifest.csv"
    )
    prepared_gallery = (
        repository
        / "data/prepared_gallery_references/structural-2026.03-r01/manifest.csv"
    )
    acquisition = (
        repository
        / "data/acquisition_quality_development/acquisition_quality_release_r02/manifest.csv"
    )
    consumed = (
        repository
        / "data/structural_consumed_blind_development/consumed_blind_clean_release_r01/manifest.csv"
    )
    consumed_attacks = (
        repository
        / "data/structural_consumed_blind_attack_development/"
        "r07-corrective-v1/manifest.csv"
    )
    cache_rebase = repository / "scripts/build_structural_r07_corrective_cache.py"

    assert initial.is_file()
    assert cache_rebase.is_file()
    assert hashlib.sha256(initial.read_bytes()).hexdigest() == (
        "0decc53ea5aabb97f579a13ba1bb3bb012480b96c26c4551e8593f7a297e186f"
    )
    with physical.open(newline="", encoding="utf-8") as handle:
        physical_rows = list(csv.DictReader(handle))
    assert len(physical_rows) == 130
    assert all(
        row.get("physical_attack_survival_verified", "").lower() == "true"
        for row in physical_rows
        if row["label"] == "adversarial"
    )
    with coverage.open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 240
    with prepared_gallery.open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 239
    with acquisition.open(newline="", encoding="utf-8") as handle:
        acquisition_rows = list(csv.DictReader(handle))
    assert len(acquisition_rows) == 90
    assert {row["label"] for row in acquisition_rows} == {"clean"}
    assert {row["split"] for row in acquisition_rows} == {"train"}
    assert all(
        row["deployment_holdout_eligible"].lower() == "false"
        for row in acquisition_rows
    )
    with consumed.open(newline="", encoding="utf-8") as handle:
        consumed_rows = list(csv.DictReader(handle))
    assert len(consumed_rows) == 80
    assert {row["label"] for row in consumed_rows} == {"clean"}
    assert {row["split"] for row in consumed_rows} == {"train", "validation"}
    assert all(row["blind_holdout_consumed"].lower() == "true" for row in consumed_rows)
    assert all(row["promotion_eligible"].lower() == "false" for row in consumed_rows)
    with consumed_attacks.open(newline="", encoding="utf-8") as handle:
        consumed_attack_rows = list(csv.DictReader(handle))
    assert len(consumed_attack_rows) == 10
    assert {row["label"] for row in consumed_attack_rows} == {"adversarial"}
    assert {row["split"] for row in consumed_attack_rows} == {"train"}
    assert all(
        row["physical_attack_survival_verified"].lower() == "true"
        for row in consumed_attack_rows
    )
    assert all(
        row["promotion_eligible"].lower() == "false"
        for row in consumed_attack_rows
    )
