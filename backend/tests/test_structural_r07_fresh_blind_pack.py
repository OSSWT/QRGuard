"""Contracts for the candidate-bound r07 fresh blind pack."""

from collections import Counter

import cv2
import numpy as np

from scripts.build_structural_blind_holdout_pack import blind_base_specs
from scripts.build_structural_coverage_development_pack import (
    _capture_order_rows,
    _capture_plan,
    _pristine_qr,
)
from scripts.build_structural_r07_fresh_blind_pack import (
    PACK_ID,
    fresh_base_specs,
    fresh_case_specs,
)


def test_r07_fresh_blind_identities_are_new_balanced_and_opaque() -> None:
    candidate_sha256 = "a" * 64
    bases = fresh_base_specs(candidate_sha256)
    cases = fresh_case_specs(candidate_sha256)

    assert PACK_ID == "structural-r07-fresh-blind-v1"
    assert len(bases) == 16
    assert len(cases) == 48
    assert len({case.case_id for case in cases}) == 48
    assert all(case.label not in case.case_id.lower() for case in cases)
    assert all(case.attack_profile == "screen_robust_alternate" for case in cases)
    assert {base.payload for base in bases}.isdisjoint(
        {base.payload for base in blind_base_specs()}
    )

    for label in ("clean", "adversarial", "tampered"):
        selected = [case for case in cases if case.label == label]
        assert Counter(case.base.version_band for case in selected) == {
            "low_v1_v3": 5,
            "medium_v4_v6": 5,
            "high_v7_plus": 6,
        }
        assert Counter(case.base.mask_pattern for case in selected) == {
            mask: 2 for mask in range(8)
        }


def test_r07_fresh_blind_payloads_change_with_candidate_binding() -> None:
    first = fresh_base_specs("a" * 64)
    second = fresh_base_specs("b" * 64)

    assert {base.payload for base in first}.isdisjoint(
        {base.payload for base in second}
    )


def test_r07_fresh_blind_plan_uses_blinded_operator_language() -> None:
    rows = [
        {
            "order": 1,
            "case_id": "R7B-01-ABCDEF",
            "label": "clean",
            "qr_version": 3,
            "mask_pattern": 0,
            "card_path": "cards/R7B-01-ABCDEF.png",
            "payload_sha256": "a" * 64,
            "base_id": "base",
            "development_split": "blind_holdout",
            "module_count": 29,
            "version_band": "low_v1_v3",
            "payload_length_bin": "short_1_32",
            "payload_utf8_bytes": 24,
            "qr_matrix_sha256": "b" * 64,
            "card_sha256": "c" * 64,
            "attack_method": "none",
            "attack_reference_sha256": "",
            "manipulation_method": "none",
        }
    ]

    plan = _capture_plan(
        rows,
        pack_id=PACK_ID,
        evidence_role="blind_holdout",
    )

    instruction = plan["distances"][0]["instruction"]
    assert "blinded pass" in instruction
    assert "development" not in instruction
    assert _capture_order_rows(rows, is_blind=True) == [
        {
            "order": rows[0]["order"],
            "case_id": "R7B-01-ABCDEF",
            "card_path": "cards/R7B-01-ABCDEF.png",
        }
    ]
    assert "label" not in _capture_order_rows(rows, is_blind=True)[0]


def test_r07_fresh_blind_pristine_bases_decode() -> None:
    detector = cv2.QRCodeDetector()

    candidate_hashes = (
        "a" * 64,
        "71a86dec83c5c63dd3ac4b83705f403c183c9efe8822a424e072a7b95c555033",
    )
    for candidate_sha256 in candidate_hashes:
        for base in fresh_base_specs(candidate_sha256):
            image, _ = _pristine_qr(base)
            payload, _, _ = detector.detectAndDecode(
                cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
            )

            assert payload == base.payload
