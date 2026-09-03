import numpy as np
import pytest
import qrcode
from qrcode.constants import ERROR_CORRECT_H

from scripts.audit_structural_qr_coverage import (
    coverage_failures,
    mask_from_straight_qr,
    summarize_runtime,
    version_from_module_count,
)


@pytest.mark.parametrize("version,modules", [(1, 21), (3, 29), (4, 33), (8, 49)])
def test_version_is_derived_from_module_count(version: int, modules: int) -> None:
    assert version_from_module_count(modules) == version


@pytest.mark.parametrize("mask", range(8))
def test_mask_reader_recovers_all_legal_masks(mask: int) -> None:
    qr = qrcode.QRCode(
        version=3,
        error_correction=ERROR_CORRECT_H,
        border=0,
        mask_pattern=mask,
    )
    qr.add_data("QRGuard demo order 4471")
    qr.make(fit=False)
    straight = np.asarray(qr.modules, dtype=np.uint8)
    straight = np.where(straight, 0, 255).astype(np.uint8)

    assert mask_from_straight_qr(straight) == mask


def test_coverage_gate_exposes_missing_low_versions_and_masks() -> None:
    config = {
        "required_classes": ["clean"],
        "version_bands": [
            {"id": "low", "minimum_version": 1, "maximum_version": 3},
            {"id": "high", "minimum_version": 7, "maximum_version": 40},
        ],
        "payload_length_bins": [
            {"id": "short", "minimum_utf8_bytes": 1, "maximum_utf8_bytes": 32}
        ],
        "minimum_independent_test_groups_per_class_version_band": 1,
        "minimum_independent_test_groups_per_class_mask": 1,
        "minimum_independent_test_groups_per_class_payload_length_bin": 1,
    }
    records = [
        {
            "label": "clean",
            "qr_version": 8,
            "module_count": 49,
            "version_band": "high",
            "mask_pattern": 4,
            "payload_length_bin": "short",
            "payload_utf8_bytes": 20,
        }
    ]

    failures = coverage_failures(summarize_runtime(records), config)

    assert "clean: version band low has 0, requires 1" in failures
    assert "clean: mask 0 has 0, requires 1" in failures
    assert not any("payload bin short" in failure for failure in failures)
