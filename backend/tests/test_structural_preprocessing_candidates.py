from PIL import Image

from scripts.evaluate_structural_preprocessing_candidates import (
    TRANSFORMS,
    apply_transform,
)


def test_every_candidate_preserves_crop_contract() -> None:
    image = Image.new("RGB", (280, 280), "white")

    for transform in TRANSFORMS.values():
        result = apply_transform(image, 29, transform)
        assert result.mode == "RGB"
        assert result.size == image.size
