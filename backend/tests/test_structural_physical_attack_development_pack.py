from collections import Counter

import cv2
import numpy as np

from scripts.build_structural_coverage_development_pack import _pristine_qr
from scripts.build_structural_physical_attack_development_pack import (
    base_specs,
    case_specs,
)


def test_physical_attack_pack_has_paired_profiles_and_version_diversity() -> None:
    bases = base_specs()
    cases = case_specs()

    assert len(bases) == 16
    assert len(cases) == 48
    assert {base.qr_version for base in bases} == {
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        12,
        14,
    }
    assert Counter(base.mask_pattern for base in bases) == {
        mask: 2 for mask in range(8)
    }
    for base in bases:
        selected = [case for case in cases if case.base.base_id == base.base_id]
        assert Counter(case.label for case in selected) == {
            "clean": 1,
            "adversarial": 2,
        }
        assert {
            case.attack_profile for case in selected if case.label == "adversarial"
        } == {
            "screen_robust_function",
            "screen_robust_alternate",
        }


def test_every_physical_attack_base_fits_fixed_version_and_decodes() -> None:
    detector = cv2.QRCodeDetector()

    for base in base_specs():
        image, _ = _pristine_qr(base)
        decoded, _, _ = detector.detectAndDecode(
            cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        )

        assert decoded == base.payload
        assert len(base.payload.encode("utf-8")) > 0
