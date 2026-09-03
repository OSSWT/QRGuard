"""Contracts for the post-freeze M8 blinded Structural acceptance pack."""

from collections import Counter

import cv2
import numpy as np

from scripts.build_structural_blind_holdout_pack import (
    PACK_ID,
    blind_base_specs,
    blind_case_specs,
)
from scripts.build_structural_coverage_development_pack import (
    _pristine_qr,
    base_specs,
)


def test_blind_holdout_has_new_opaque_balanced_identities() -> None:
    bases = blind_base_specs()
    cases = blind_case_specs()

    assert PACK_ID == "structural-coverage-blind-holdout-2026-09-r01"
    assert len(bases) == 16
    assert len(cases) == 48
    assert len({case.case_id for case in cases}) == 48
    assert all(case.label not in case.case_id.lower() for case in cases)
    assert all(base.development_split == "blind_holdout" for base in bases)
    assert {base.payload for base in bases}.isdisjoint(
        {base.payload for base in base_specs()}
    )

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


def test_blind_base_payloads_fit_fixed_versions_and_decode() -> None:
    detector = cv2.QRCodeDetector()

    for base in blind_base_specs():
        image, _ = _pristine_qr(base)
        payload, _, _ = detector.detectAndDecode(
            cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        )

        assert payload == base.payload
        assert len(base.payload.encode("utf-8")) in {24, 48, 132}
