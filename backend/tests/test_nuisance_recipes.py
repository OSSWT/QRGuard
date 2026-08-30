import numpy as np
import pytest
from PIL import Image
from structural.image_quality import assess_image_quality

from ml_training.structural.src.nuisance_recipes import CONDITIONS, apply_nuisance


def _checkerboard() -> Image.Image:
    values = np.indices((224, 224)).sum(axis=0) // 14 % 2 * 255
    rgb = np.repeat(values[:, :, None].astype(np.uint8), 3, axis=2)
    return Image.fromarray(rgb, mode="RGB")


@pytest.mark.parametrize("condition", CONDITIONS)
def test_every_recipe_is_deterministic_and_preserves_dimensions(condition):
    source = _checkerboard()
    first = apply_nuisance(source, condition, "moderate", seed="same-parent")
    second = apply_nuisance(source, condition, "moderate", seed="same-parent")

    assert first.size == source.size
    assert np.array_equal(np.asarray(first), np.asarray(second))


def test_blur_recipes_reduce_measured_focus():
    source = _checkerboard()
    original = assess_image_quality(source)
    blurred = assess_image_quality(
        apply_nuisance(source, "defocus_blur", "severe", seed=1)
    )

    assert blurred.laplacian_variance < original.laplacian_variance


def test_invalid_recipe_is_rejected():
    with pytest.raises(ValueError, match="unknown quality condition"):
        apply_nuisance(_checkerboard(), "malicious_blur")
