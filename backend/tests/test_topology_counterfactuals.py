from collections import Counter

import numpy as np
import pandas as pd

from ml_training.structural.src import structural_recipes
from ml_training.structural.src.train_local import (
    TOPOLOGY_COUNTERFACTUAL_SOURCE,
    _paired_partner_indices,
    _sampling_weights,
    _source_family,
    _topology_counterfactual_metrics,
    _verified_attack_fit_metrics,
)


def test_topology_counterfactuals_balance_masks_and_hold_out_payloads(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(structural_recipes, "ROOT", tmp_path)
    monkeypatch.setattr(structural_recipes, "IMAGES", tmp_path / "images")
    rows = structural_recipes.generate_topology_counterfactual_clean_rows(
        {
            "enabled": True,
            "versions": [{"version": 12, "payload_utf8_bytes": 132}],
            "mask_patterns": list(range(8)),
            "error_corrections": ["L", "M", "Q", "H"],
            "identities_per_error_correction": 2,
            "conditions": ["normal"],
        }
    )

    assert len(rows) == 64
    assert Counter(row["split"] for row in rows) == {
        "train": 32,
        "validation": 32,
    }
    assert {row["label"] for row in rows} == {"clean"}
    assert {row["qr_version"] for row in rows} == {12}
    assert {row["module_count"] for row in rows} == {65}
    assert {row["payload_utf8_bytes"] for row in rows} == {132}
    assert {row["mask_pattern"] for row in rows} == set(range(8))
    assert len({row["group_id"] for row in rows}) == 8
    assert not (
        {row["group_id"] for row in rows if row["split"] == "train"}
        & {row["group_id"] for row in rows if row["split"] == "validation"}
    )
    for group_id in {row["group_id"] for row in rows}:
        group = [row for row in rows if row["group_id"] == group_id]
        assert {row["mask_pattern"] for row in group} == set(range(8))
        assert len({row["payload_hash"] for row in group}) == 1
        assert len({row["qr_matrix_sha256"] for row in group}) == 8
        assert all((tmp_path / row["path"]).is_file() for row in group)


def test_topology_recipe_is_opt_in() -> None:
    assert structural_recipes.generate_topology_counterfactual_clean_rows({}) == []
    assert (
        structural_recipes.generate_topology_counterfactual_clean_rows(
            {"enabled": False}
        )
        == []
    )


def test_topology_counterfactuals_support_more_independent_payloads(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(structural_recipes, "ROOT", tmp_path)
    monkeypatch.setattr(structural_recipes, "IMAGES", tmp_path / "images")
    rows = structural_recipes.generate_topology_counterfactual_clean_rows(
        {
            "enabled": True,
            "versions": [{"version": 12, "payload_utf8_bytes": 132}],
            "mask_patterns": list(range(8)),
            "error_corrections": ["L", "M", "Q", "H"],
            "train_identities_per_error_correction": 2,
            "validation_identities_per_error_correction": 2,
            "conditions": ["normal"],
        }
    )

    assert len(rows) == 128
    assert Counter(row["split"] for row in rows) == {
        "train": 64,
        "validation": 64,
    }
    assert len({row["group_id"] for row in rows if row["split"] == "train"}) == 8
    assert (
        len({row["group_id"] for row in rows if row["split"] == "validation"})
        == 8
    )
    assert not (
        {row["payload_hash"] for row in rows if row["split"] == "train"}
        & {row["payload_hash"] for row in rows if row["split"] == "validation"}
    )


def test_topology_partners_connect_every_mask_and_condition() -> None:
    frame = pd.DataFrame(
        [
            {
                "source": TOPOLOGY_COUNTERFACTUAL_SOURCE,
                "paired_group": "payload-a",
                "group_id": "payload-a",
                "class_id": 0,
                "mask_pattern": mask,
                "quality_condition": condition,
            }
            for mask in range(8)
            for condition in ("normal", "screen_moire_or_compression")
        ]
    )

    partners = _paired_partner_indices(frame)

    visited = {0}
    current = 0
    for _ in range(len(frame) - 1):
        current = partners[current]
        assert current not in visited
        visited.add(current)
    assert partners[current] == 0
    assert visited == set(range(len(frame)))
    assert {int(frame.iloc[index].mask_pattern) for index in visited} == set(range(8))
    assert {
        str(frame.iloc[index].quality_condition) for index in visited
    } == {"normal", "screen_moire_or_compression"}


def test_topology_sampling_can_reserve_a_separate_family_quota() -> None:
    frame = pd.DataFrame(
        [
            {"source": "procedural_qrguard", "class_id": 0, "label": "clean"},
            {
                "source": TOPOLOGY_COUNTERFACTUAL_SOURCE,
                "class_id": 0,
                "label": "clean",
            },
        ]
    )
    weights = _sampling_weights(
        frame,
        {
            "source_family_draw_fractions": {
                "clean": {
                    "procedural": 0.6,
                    "topology_counterfactual": 0.4,
                }
            }
        },
    )

    assert np.isclose(weights[0] / weights[1], 1.5)
    assert _source_family(TOPOLOGY_COUNTERFACTUAL_SOURCE) == "procedural"
    assert (
        _source_family(TOPOLOGY_COUNTERFACTUAL_SOURCE, separate_topology=True)
        == "topology_counterfactual"
    )


def test_topology_metrics_expose_mask_specific_clean_failures() -> None:
    source = "procedural_qrguard_topology_counterfactual"
    frame = pd.DataFrame(
        [
            {
                "source": source,
                "group_id": "a",
                "qr_version": 12,
                "mask_pattern": 0,
            },
            {
                "source": source,
                "group_id": "a",
                "qr_version": 12,
                "mask_pattern": 1,
            },
            {
                "source": "procedural_qrguard",
                "group_id": "ignored",
                "qr_version": 3,
                "mask_pattern": 7,
            },
        ]
    )
    probabilities = np.asarray(
        [
            [0.95, 0.03, 0.02],
            [0.10, 0.80, 0.10],
            [0.00, 1.00, 0.00],
        ]
    )

    metrics = _topology_counterfactual_metrics(frame, probabilities)

    assert metrics["rows"] == 2
    assert metrics["groups"] == 1
    assert metrics["clean_false_positive_rate"] == 0.5
    assert metrics["per_mask_clean_false_positive_rate"] == {
        "0": 0.0,
        "1": 1.0,
    }
    assert metrics["clean_structural_probability_span_p95"] == 0.85
    assert metrics["mask_probability_span_p95_within_condition"] == 0.85
    assert metrics["condition_probability_span_p95_within_mask"] == 0.0
    assert _source_family(source) == "procedural"


def test_verified_attack_fit_is_explicitly_non_promoting() -> None:
    frame = pd.DataFrame(
        [
            {"paired_group": "attack-a"},
            {"paired_group": "attack-a"},
            {"paired_group": "attack-b"},
            {"paired_group": "attack-b"},
        ]
    )
    probabilities = np.asarray(
        [
            [0.1, 0.8, 0.1],
            [0.2, 0.7, 0.1],
            [0.6, 0.3, 0.1],
            [0.4, 0.5, 0.1],
        ]
    )

    metrics = _verified_attack_fit_metrics(frame, probabilities)

    assert metrics["evidence_role"] == "development_train_fit_only"
    assert metrics["promotion_eligible"] is False
    assert metrics["nonclean_recall"] == 0.75
    assert metrics["session_nonclean_recall"] == 0.5
