import hashlib
import json
import zipfile
from pathlib import Path

from scripts.build_structural_attack_calibration_colab import (
    NOTEBOOK_NAME,
    SOURCE_FILES,
    build,
    notebook,
)


def test_calibration_notebook_has_gpu_generation_and_non_mutation_contracts() -> None:
    document = notebook()
    source = "\n".join(
        "".join(cell["source"])
        for cell in document["cells"]
        if cell["cell_type"] == "code"
    )

    assert "torch.cuda.is_available()" in source
    assert "screen_camera_robust_v2_function" in source
    assert "screen_camera_robust_v2_alternate" in source
    assert "model_training_performed': False" in source
    assert "candidate_scoring_performed': False" in source
    assert "production_mutation_performed': False" in source
    assert "QRGuard_Attack_Calibration_Output" in source


def test_calibration_colab_bundle_is_deterministic_and_complete(tmp_path: Path) -> None:
    output = tmp_path / "QRGuard_Attack_Calibration_Colab"
    archive = tmp_path / "QRGuard_Attack_Calibration_Colab.zip"

    first = build(output, archive)
    first_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    second = build(output, archive)
    second_hash = hashlib.sha256(archive.read_bytes()).hexdigest()

    assert first_hash == second_hash == first["archive_sha256"]
    assert second["archive_sha256"] == first["archive_sha256"]
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        prefix = "QRGuard_Attack_Calibration_Colab/"
        assert prefix + NOTEBOOK_NAME in names
        assert prefix + "README.md" in names
        for relative in SOURCE_FILES:
            assert prefix + "QRGuard/" + relative in names
        document = json.loads(package.read(prefix + NOTEBOOK_NAME))
        assert document["nbformat"] == 4
