from __future__ import annotations

from scripts.build_colab_bundle import (
    decision_frozen_notebook,
    semantic_frozen_notebook,
    semantic_notebook,
    structural_v3_notebook,
)


def _code(notebook: dict) -> str:
    return "\n".join(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )


def test_structural_v3_notebook_cells_compile_and_expose_all_modes() -> None:
    notebook = structural_v3_notebook()
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"cell-{index}", "exec")

    source = _code(notebook)
    for mode in ("fresh", "resume", "evaluate_only", "report_only"):
        assert mode in source
    assert "structural-r07-corrective-v1" in source
    assert "DATASET_VERSION = 'structural-r07-corrective-v1'" in source
    assert "physical_attack_development_sha256" in source
    assert "coverage_development_sha256" in source
    assert "prepared_gallery_reference_sha256" in source
    assert "acquisition_quality_development_sha256" in source
    assert "consumed_blind_clean_development_sha256" in source
    assert "consumed_blind_verified_attack_development_sha256" in source
    assert "Phase 3 started" in source
    assert "raw_sentinels" in source
    assert "processed-{DATASET_VERSION}.zip" in source
    assert "BASE_CACHE_DRIVE" in source
    assert "restoring verified r07 base image cache" in source
    assert "scripts.build_structural_r07_corrective_cache" in source
    assert "prepared_archive_sha256" in source
    assert "Phase 3 complete: rows=" in source
    assert "shutil.copytree(cached_processed, PROCESSED_ROOT" not in source
    assert source.index("raw_ready =") < source.index("if not public_manifests_ready:")
    assert "--checkpoint-dir" in source
    assert "QRGUARD_STRUCTURAL_VERSION" in source
    assert "QRGUARD_STRUCTURAL_DATASET_VERSION" in source


def test_semantic_notebook_is_frozen_report_only() -> None:
    source = _code(semantic_frozen_notebook())

    assert "semantic-2026.02" in source
    assert "ml_training.semantic.src.train_local" not in source


def test_semantic_training_notebook_compiles_and_is_candidate_only() -> None:
    notebook = semantic_notebook()
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"cell-{index}", "exec")

    source = _code(notebook)
    assert "ml_training.semantic.src.prepare_colab_data" in source
    assert "ml_training.semantic.src.train_local" in source
    assert "semantic-colab-candidate-v1" in source
    assert "QRGUARD_SEMANTIC_VERSION" in source
    assert "PERFORMANCE_VALIDATION.json" in source
    assert "No runtime model, GitHub branch, or deployment was changed." in source
    assert "--promote" not in source


def test_decision_notebook_is_frozen_report_only() -> None:
    notebook = decision_frozen_notebook()
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"cell-{index}", "exec")

    source = _code(notebook)
    assert "decision-2026.03-r05" in source
    assert "gates_passed" in source
    assert "promotion_requested" in source
    assert "train_fusion" not in source
    assert "--promote" not in source
