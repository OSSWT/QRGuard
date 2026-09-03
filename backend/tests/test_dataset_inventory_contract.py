"""Static contract for the published dataset audit and presentation boundary."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "ml_training/datasets"


def _inventory() -> dict:
    return json.loads((DATASETS / "DATASET_INVENTORY.json").read_text(encoding="utf-8"))


def test_dataset_inventory_records_every_active_branch_and_archive():
    inventory = _inventory()
    summary = inventory["summary"]

    assert inventory["schema_version"] == 1
    assert summary == {
        "dataset_records": 21,
        "required_records": 20,
        "required_present": 20,
        "required_verified": 20,
        "all_required_verified": True,
        "optional_records": 1,
        "optional_verified": 1,
        "private_archive_records": 5,
        "private_archives_verified": 5,
    }

    rows = {row["dataset_id"]: row for row in inventory["datasets"]}
    for dataset_id in (
        "qrdn_v2_archive",
        "qrguard_runtime_captures_v3",
        "semantic_phiusiil_standardised",
        "semantic_malicious_urls_standardised",
        "semantic_tranco_top150k_snapshot",
        "semantic_train",
        "semantic_validation",
        "semantic_test",
        "qrguard_mix_v2",
    ):
        assert rows[dataset_id]["verified"] is True

    for row in rows.values():
        assert row["source_url"]
        assert row["licence"]
        assert row["github_policy"]


def test_known_provenance_gap_is_disclosed_instead_of_guessed():
    inventory = _inventory()
    limitations = " ".join(inventory["known_provenance_limitations"])
    tranco = next(
        row
        for row in inventory["datasets"]
        if row["dataset_id"] == "semantic_tranco_top150k_snapshot"
    )

    assert "permanent ID" in limitations
    assert "not recorded" in limitations
    assert "permanent Tranco list ID was not recorded" in tranco["note"]


def test_presentation_pack_is_post_training_and_covers_every_demo_type():
    demo = DATASETS / "qr_codes_demo"
    manifest = json.loads((demo / "MANIFEST.json").read_text(encoding="utf-8"))
    quick = (demo / "QUICK_DEMO_ORDER.csv").read_text(encoding="utf-8")

    assert manifest["pack_id"] == "qrguard-presentation-demo-r07"
    assert manifest["case_count"] == 42
    assert manifest["independent_performance_claim"] is False
    assert all(case["demo_role"] == "demo_only" for case in manifest["cases"])
    assert {case["structural_ground_truth"] for case in manifest["cases"] if case["category"] == "structural"} == {
        "clean",
        "adversarial",
        "tampered",
    }
    for number in range(1, 13):
        assert f"SEM-{number:02d}-" in quick

    assert (demo / "PRESENTATION_DEMO.html").is_file()
    assert (demo / "PRESENTATION_GUIDE.md").is_file()
    assert (DATASETS / "DATASET_CATALOG.md").is_file()


def test_generated_qr_registry_contains_only_active_or_evidence_sets():
    registry = json.loads(
        (DATASETS / "generated_qr_codes/registry.json").read_text(encoding="utf-8")
    )
    rows = {row["dataset_id"]: row for row in registry["datasets"]}

    assert set(rows) == {
        "structural-v3-real-2026.03-r01-capture-references",
        "structural-2026.03-r01-prepared-gallery-references",
        "qrguard-presentation-demo-r07",
        "qrguard-api-regression-fixtures",
        "qrguard-gallery-test-cards",
    }
    assert not any(
        "legacy_not_current" in row["exposure_states"] for row in rows.values()
    )
