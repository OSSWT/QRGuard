"""Contract tests for the complete Google Colab ML hand-off."""

from __future__ import annotations

import ast
import hashlib
import json
import zipfile
from pathlib import Path

from ml_training.scripts.validate_performance_bundle import REQUIRED

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "QRGuard_ML_Colab"


def _source(notebook: dict) -> str:
    return "".join("".join(cell.get("source", [])) for cell in notebook["cells"])


def test_colab_code_cells_are_valid_python():
    for notebook_name in (
        "01_Structural_Training_Colab.ipynb",
        "02_Semantic_Training_Colab.ipynb",
    ):
        notebook = json.loads((PACKAGE / notebook_name).read_text(encoding="utf-8"))
        for index, cell in enumerate(notebook["cells"]):
            if cell.get("cell_type") == "code":
                ast.parse("".join(cell.get("source", [])), filename=f"{notebook_name}:{index}")


def test_colab_notebooks_have_complete_phases_and_performance_outputs():
    structural = json.loads(
        (PACKAGE / "01_Structural_Training_Colab.ipynb").read_text(encoding="utf-8")
    )
    semantic = json.loads(
        (PACKAGE / "02_Semantic_Training_Colab.ipynb").read_text(encoding="utf-8")
    )
    structural_source = _source(structural)
    semantic_source = _source(semantic)

    for phase in range(9):
        assert f"Phase {phase}" in structural_source
    for phase in range(8):
        assert f"Phase {phase}" in semantic_source
    for artifact in REQUIRED["structural"]:
        assert artifact in structural_source or artifact in {
            "metrics.json",
            "STRUCTURAL_PERFORMANCE.md",
        }
    for artifact in REQUIRED["semantic"]:
        assert artifact in semantic_source or artifact in {
            "metrics.json",
            "SEMANTIC_PERFORMANCE.md",
        }
    combined = structural_source + semantic_source
    assert "C:\\Users\\" not in combined
    assert "MyDrive/QRGuard_ML_Results" in combined
    assert "protected = {'torch', 'torchvision'}" in combined
    assert "stderr=subprocess.STDOUT" in combined
    assert "PYTHONUNBUFFERED" in combined
    assert "Bundle SHA-256:" in combined
    assert "Stale QRGuard_ML_Colab.zip detected" in structural_source
    assert "Core performance metrics" in structural_source
    assert "Gate status" in structural_source
    assert "Performance charts" in structural_source


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
        assert declared[relative]["sha256"] == hashlib.sha256(
            path.read_bytes()
        ).hexdigest()


def test_colab_zip_is_readable_and_contains_the_manifest():
    archive_path = ROOT / "QRGuard_ML_Colab.zip"
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert not any(
            name.startswith("QRGuard_ML_Colab/QRGuard_ML_Colab/")
            for name in archive.namelist()
        )
        assert "QRGuard_ML_Colab/PACKAGE_MANIFEST.json" in archive.namelist()
        assert "QRGuard_ML_Colab/01_Structural_Training_Colab.ipynb" in archive.namelist()
        assert "QRGuard_ML_Colab/02_Semantic_Training_Colab.ipynb" in archive.namelist()


def test_structural_adversarial_wrapper_moves_buffers_to_training_device():
    source = (
        PACKAGE
        / "QRGuard/ml_training/structural/src/structural_recipes.py"
    ).read_text(encoding="utf-8")

    assert "model = Normalized(victim).to(device).eval()" in source
