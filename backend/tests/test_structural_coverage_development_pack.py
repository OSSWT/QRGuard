from collections import Counter

import cv2
import numpy as np

from scripts.build_structural_coverage_development_pack import (
    _pristine_qr,
    base_specs,
    case_specs,
)


def test_development_pack_is_balanced_by_class_band_mask_and_parent() -> None:
    bases = base_specs()
    cases = case_specs()

    assert len(bases) == 16
    assert len(cases) == 48
    assert len({base.payload for base in bases}) == 16
    assert all(len(base.payload.encode("utf-8")) in {24, 40, 112} for base in bases)

    for label in ("clean", "adversarial", "tampered"):
        selected = [case for case in cases if case.label == label]
        assert len(selected) == 16
        assert Counter(case.base.version_band for case in selected) == {
            "low_v1_v3": 5,
            "medium_v4_v6": 5,
            "high_v7_plus": 6,
        }
        assert Counter(case.base.mask_pattern for case in selected) == {
            mask: 2 for mask in range(8)
        }

    for base in bases:
        variants = [case for case in cases if case.base.base_id == base.base_id]
        assert {case.label for case in variants} == {
            "clean",
            "adversarial",
            "tampered",
        }
        assert {case.base.development_split for case in variants} == {
            base.development_split
        }


def test_every_base_spec_fits_its_fixed_version_and_decodes() -> None:
    detector = cv2.QRCodeDetector()

    for base in base_specs():
        image, _ = _pristine_qr(base)
        bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        decoded, _, _ = detector.detectAndDecode(bgr)

        assert decoded == base.payload
        assert len(base.payload.encode("utf-8")) in {24, 40, 112}
