from __future__ import annotations

from scripts.build_colab_bundle import (
    decision_frozen_notebook,
    semantic_frozen_notebook,
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
    assert "structural-2026.03-r01" in source
    assert "--checkpoint-dir" in source
    assert "QRGUARD_STRUCTURAL_VERSION" in source


def test_semantic_notebook_is_frozen_report_only() -> None:
    source = _code(semantic_frozen_notebook())

    assert "semantic-2026.02" in source
    assert "ml_training.semantic.src.train_local" not in source


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
