"""Verify the canonical QRGuard ML datasets and write a stable inventory.

Large or redistribution-restricted datasets stay outside Git.  This audit makes
their local presence, identity, role, and recovery path reviewable without
publishing their contents.  The output deliberately contains no wall-clock
field, so an unchanged workspace produces an unchanged inventory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DATASETS = ROOT.parent / "03_Datasets"
OUTPUT = ROOT / "ml_training/datasets/DATASET_INVENTORY.json"


DATASETS: tuple[dict[str, Any], ...] = (
    {
        "dataset_id": "qrdn_v2_archive",
        "branch": "structural",
        "path": "ml_training/datasets/structural/downloads/qrdn/QR-DN1.0.zip",
        "kind": "archive",
        "role": "auxiliary clean train plus external clean holdout",
        "source_url": "https://data.mendeley.com/datasets/t2bdr663ms/2",
        "doi": "10.17632/t2bdr663ms.2",
        "licence": "CC BY 4.0",
        "expected_bytes": 1_025_545_184,
        "expected_sha256": "1f175a62239646bd7d6b179245cb0970c03b179c2baf1a5e8e59ba0b156cdf61",
        "github_policy": "metadata_only_large_archive",
        "required": True,
    },
    {
        "dataset_id": "qrdn_v2_prepared_manifest",
        "branch": "structural",
        "path": "ml_training/datasets/structural/processed/qrdn/manifest.csv",
        "kind": "manifest",
        "role": "4,500 official-train and 2,250 identity-disjoint external-test rows",
        "source_url": "https://data.mendeley.com/datasets/t2bdr663ms/2",
        "licence": "CC BY 4.0",
        "expected_rows": 6_750,
        "expected_sha256": "adfb9d563162bf00ec7af1c9ef2ac8de1859068b3e22b08a50737f7e73b01989",
        "github_policy": "generated_cache_not_published",
        "required": True,
        "note": "Image expansion is intentionally absent and is restored from the verified archive before a rebuild.",
    },
    {
        "dataset_id": "qr_surfaces_v1_archive",
        "branch": "structural",
        "path": "ml_training/datasets/structural/downloads/qr_surfaces/qr_codes_in_surfaces.zip",
        "kind": "archive",
        "role": "auxiliary clean geometry and surface robustness",
        "source_url": "https://data.mendeley.com/datasets/m6mfwc52vk/1",
        "doi": "10.17632/m6mfwc52vk.1",
        "licence": "CC BY 4.0",
        "expected_bytes": 384_232_282,
        "expected_sha256": "706352654a744217b6853c77362f4a32cc318d941b715423948ba2108aae7523",
        "github_policy": "metadata_only_large_archive",
        "required": True,
    },
    {
        "dataset_id": "qr_surfaces_v1_prepared",
        "branch": "structural",
        "path": "ml_training/datasets/structural/processed/qr_surfaces/manifest.csv",
        "kind": "manifest",
        "role": "67 accepted real-image rectified crops; train only",
        "source_url": "https://data.mendeley.com/datasets/m6mfwc52vk/1",
        "licence": "CC BY 4.0",
        "expected_rows": 67,
        "expected_sha256": "98f1a2a02fda8f310acb0ba66875c44a4bba0d5fc3cb6e164e81402f522c27a2",
        "path_column": "path",
        "hash_column": "crop_sha256",
        "github_policy": "generated_cache_not_published",
        "required": True,
    },
    {
        "dataset_id": "dynamsoft_qr_acquisition_quarantine",
        "branch": "acquisition",
        "path": "ml_training/datasets/holdout/processed/dynamsoft_qr/manifest.csv",
        "kind": "manifest",
        "role": "232 challenging-image crops plus one video crop for acquisition inspection only",
        "source_url": "https://github.com/Dynamsoft/datasets-from-dynamsoft",
        "licence": "no repository-wide dataset licence recorded for the acquired QR subsets",
        "expected_rows": 233,
        "expected_sha256": "b8f9757bef296c7f240de8c5f6d5793342da02c88bde531c946c14410bbf951d",
        "path_column": "path",
        "hash_column": "crop_sha256",
        "github_policy": "metadata_only_licence_quarantine",
        "required": False,
        "note": "Excluded from training and Structural class metrics; useful only for detector/crop robustness inspection.",
    },
    {
        "dataset_id": "qrguard_runtime_captures_v3",
        "branch": "structural",
        "path": "data/runtime_captures/manifest_v3.csv",
        "kind": "manifest",
        "role": "primary exact-app Gallery/Camera train, validation and locked runtime holdout",
        "source_url": "local://QRGuard/opt-in-app-capture",
        "licence": "project internal opt-in",
        "expected_rows": 361,
        "expected_sha256": "013e0ad7df831244a4a7518197f55cc52849ea7486f6f8b9a33f17e1e97559e0",
        "path_column": "sample_path",
        "hash_column": "sha256",
        "hash_mode": "rgb_pixels_with_dimensions",
        "reference_root": "data/runtime_captures",
        "github_policy": "metadata_only_private_captures",
        "required": True,
    },
    {
        "dataset_id": "qrguard_gallery_references_r01",
        "branch": "structural",
        "path": "data/prepared_gallery_references/structural-2026.03-r01/manifest.csv",
        "kind": "manifest",
        "role": "grouped Gallery train and validation references; locked test excluded",
        "source_url": "local://QRGuard/capture-campaign",
        "licence": "project internal",
        "expected_rows": 239,
        "expected_sha256": "f2a8cfcd921834d7efe8b309c00ecb3ddf64aae34dea8c3b32b94dd962315573",
        "path_column": "path",
        "hash_column": "sha256",
        "github_policy": "metadata_only_project_data",
        "required": True,
    },
    {
        "dataset_id": "qrguard_structural_coverage_development",
        "branch": "structural",
        "path": "data/structural_coverage_development/coverage_development_release_r01/manifest.csv",
        "kind": "manifest",
        "role": "version, mask and payload-length development coverage",
        "source_url": "local://QRGuard/diagnostic-capture",
        "licence": "project internal opt-in",
        "expected_rows": 240,
        "expected_sha256": "601d824bd5e1910fe3458f6a59018c1333ccba73c8c8b607ec5aa6bd46bd1335",
        "path_column": "path",
        "hash_column": "crop_sha256",
        "github_policy": "metadata_only_private_captures",
        "required": True,
    },
    {
        "dataset_id": "qrguard_physical_attack_development",
        "branch": "structural",
        "path": "data/structural_physical_attack_development/physical_attack_release_r02/manifest.csv",
        "kind": "manifest",
        "role": "80 clean plus 50 verified-surviving attack development frames",
        "source_url": "local://QRGuard/physical-attack-capture",
        "licence": "project internal opt-in",
        "expected_rows": 130,
        "expected_sha256": "80a88611a8e717be11602497b2c5ffb263635f7954b75945e18d34963dd9ccce",
        "path_column": "path",
        "hash_column": "crop_sha256",
        "github_policy": "metadata_only_private_captures",
        "required": True,
    },
    {
        "dataset_id": "qrguard_acquisition_quality_development",
        "branch": "structural",
        "path": "data/acquisition_quality_development/acquisition_quality_release_r02/manifest.csv",
        "kind": "manifest",
        "role": "clean exposure and module-scale train-only hard negatives",
        "source_url": "local://QRGuard/acquisition-quality-capture",
        "licence": "project internal opt-in",
        "expected_rows": 90,
        "expected_sha256": "4f6d1739b96eacf3b2b59b07a337c0b6970952584d7c5ceec81e3625ce69108e",
        "path_column": "path",
        "hash_column": "crop_sha256",
        "github_policy": "metadata_only_private_captures",
        "required": True,
    },
    {
        "dataset_id": "qrguard_consumed_blind_clean_development",
        "branch": "structural",
        "path": "data/structural_consumed_blind_development/consumed_blind_clean_release_r01/manifest.csv",
        "kind": "manifest",
        "role": "80 clean dense-screen development rows; never blind again",
        "source_url": "local://QRGuard/consumed-blind-capture",
        "licence": "project internal opt-in",
        "expected_rows": 80,
        "expected_sha256": "76358ef5201999221982ba0a701ddad985b5ac4288f874fc6f4a8429baec29cb",
        "path_column": "path",
        "hash_column": "crop_sha256",
        "github_policy": "metadata_only_private_captures",
        "required": True,
    },
    {
        "dataset_id": "qrguard_consumed_verified_attack_development",
        "branch": "structural",
        "path": "data/structural_consumed_blind_attack_development/r07-corrective-v1/manifest.csv",
        "kind": "manifest",
        "role": "10 train-only frames from two verified-surviving attacks",
        "source_url": "local://QRGuard/consumed-blind-capture",
        "licence": "project internal opt-in",
        "expected_rows": 10,
        "expected_sha256": "81ead9378a6b528b0c415a6213367af08e5cdb0860b2f260f4017d249f4368a4",
        "path_column": "path",
        "hash_column": "crop_sha256",
        "github_policy": "metadata_only_private_captures",
        "required": True,
    },
    {
        "dataset_id": "semantic_phiusiil_standardised",
        "branch": "semantic",
        "path": "data/method1/phiusiil.csv",
        "kind": "table",
        "role": "primary labelled benign/phishing URLs with QRGuard label mapping",
        "source_url": "https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset",
        "doi": "10.1016/j.cose.2023.103545",
        "licence": "CC BY 4.0",
        "expected_rows": 235_795,
        "expected_sha256": "1511c42441eb0360b46c54aae4cf07c98c6affa898a2e205ac2cb65fb13dcfbf",
        "github_policy": "metadata_only_redistributable_but_large",
        "required": True,
    },
    {
        "dataset_id": "semantic_malicious_urls_standardised",
        "branch": "semantic",
        "path": "data/method1/malicious_phish.csv",
        "kind": "table",
        "role": "benign, phishing, defacement and malware URL source",
        "source_url": "https://www.kaggle.com/datasets/sid321axn/malicious-urls-dataset",
        "licence": "CC0 Public Domain on the dataset page",
        "expected_rows": 651_191,
        "expected_sha256": "d83ce942075dd63ed4d11560cfdcd9d512caa3d680e292f22cab484e8f074d01",
        "github_policy": "metadata_only_large_source",
        "required": True,
    },
    {
        "dataset_id": "semantic_tranco_top150k_snapshot",
        "branch": "semantic",
        "path": "data/method1/tranco_top150k.csv",
        "kind": "table",
        "role": "benign registered-domain augmentation",
        "source_url": "https://tranco-list.eu/",
        "doi": "10.14722/ndss.2019.23386",
        "licence": "Tranco research list and component attribution terms",
        "expected_rows": 150_000,
        "expected_sha256": "b698a2686a0db066ccb3b0aeda2379791a2ca95466558d63a9fde9b6b2f79f26",
        "github_policy": "metadata_only_snapshot",
        "required": True,
        "note": "The original permanent Tranco list ID was not recorded; the frozen local file hash is authoritative and the missing list ID is a disclosed provenance limitation.",
    },
    {
        "dataset_id": "semantic_frozen_domain_holdout",
        "branch": "semantic",
        "path": "data/method1/heldout_test.parquet",
        "kind": "table",
        "role": "source-labelled pool used to create the balanced independent test split",
        "source_url": "local://QRGuard/derived-from-three-semantic-sources",
        "licence": "mixed; inherit source row licence",
        "expected_rows": 141_900,
        "expected_sha256": "d741916cc16cc2ca099ed737193b19ff647376f07ed1bbde3b7d2d9b743fbaad",
        "github_policy": "metadata_only_derived_data",
        "required": True,
    },
    {
        "dataset_id": "semantic_clean_pool",
        "branch": "semantic",
        "path": "ml_training/datasets/semantic/processed/semantic-2026.02/combined_clean.parquet",
        "kind": "table",
        "role": "conflict-cleaned, de-duplicated URL pool before bounded split sampling",
        "source_url": "local://QRGuard/derived-semantic-pool",
        "licence": "mixed; inherit source row licence",
        "expected_rows": 1_017_689,
        "expected_sha256": "82e578aeb770dc52a32b1b1a75af4970e0c63996f66d6f506a9f7a754820a7d7",
        "github_policy": "generated_cache_not_published",
        "required": True,
    },
    {
        "dataset_id": "semantic_train",
        "branch": "semantic",
        "path": "ml_training/datasets/semantic/processed/semantic-2026.02/train.parquet",
        "kind": "table",
        "role": "domain-grouped Semantic training split",
        "source_url": "local://QRGuard/derived-semantic-split",
        "licence": "mixed; inherit source row licence",
        "expected_rows": 240_050,
        "expected_sha256": "2f9cdb5b2825ec83428338d30be946516beed9548bc6d828797f007318da7e99",
        "github_policy": "generated_cache_not_published",
        "required": True,
    },
    {
        "dataset_id": "semantic_validation",
        "branch": "semantic",
        "path": "ml_training/datasets/semantic/processed/semantic-2026.02/validation.parquet",
        "kind": "table",
        "role": "domain-grouped Semantic validation split",
        "source_url": "local://QRGuard/derived-semantic-split",
        "licence": "mixed; inherit source row licence",
        "expected_rows": 60_000,
        "expected_sha256": "33172289c6425f4cf4b0836507d1e5da2bd8a6305c3d937a734e62a2be2e3a56",
        "github_policy": "generated_cache_not_published",
        "required": True,
    },
    {
        "dataset_id": "semantic_test",
        "branch": "semantic",
        "path": "ml_training/datasets/semantic/processed/semantic-2026.02/test.parquet",
        "kind": "table",
        "role": "balanced independent registered-domain test split",
        "source_url": "local://QRGuard/derived-semantic-split",
        "licence": "mixed; inherit source row licence",
        "expected_rows": 80_000,
        "expected_sha256": "78cf0de37916f0c66dea9c3d013094aea338fe17e5acca244536b7edb8d15e2b",
        "github_policy": "generated_cache_not_published",
        "required": True,
    },
    {
        "dataset_id": "qrguard_mix_v2",
        "branch": "decision_layer",
        "path": "data/qrguard_mix_v2/manifest.csv",
        "kind": "manifest",
        "role": "frozen 1,260-train/540-test fusion and threshold dataset",
        "source_url": "local://QRGuard/generated-mix",
        "licence": "project-generated; URL rows inherit source constraints",
        "expected_rows": 1_800,
        "expected_sha256": "6c30bba32aba6cd1b80ef21fe556db73ffc0f73ca0d19015c516dcdd6454cc16",
        "path_column": "filename",
        "reference_root": "data/qrguard_mix_v2/images",
        "github_policy": "metadata_only_generated_dataset",
        "required": True,
        "note": "Decision r05 is frozen on its recorded branch-signal fingerprint; regenerate signals before training a later decision version against another Structural artifact.",
    },
)


PRIVATE_ARCHIVES: tuple[dict[str, Any], ...] = (
    {
        "dataset_id": "qrguard_exact_app_master_archive",
        "path": "01_Structural/Real_App_Captures_100x3/00_Final_Master/QRGuard_Structural_100x3_Master_Audited_20260830.zip",
        "role": "canonical private recovery archive for exact-app captures",
        "expected_sha256": "f2c2e0c5b2fe2dfa7ecf1c2f9a6805f1dbd67147930b2f7ca17e065dd5d2606c",
    },
    {
        "dataset_id": "r07_consumed_blind_source_capture",
        "path": "01_Structural/R07_Fresh_Blind_Holdout/SOURCE_CAPTURE.zip",
        "role": "consumed diagnosis evidence; never fresh blind evidence again",
        "expected_sha256": "718b83f7032ca4e67d494105ed91bea5a14be1aa709c02cea046669a55958c08",
    },
    {
        "dataset_id": "r07_consumed_blind_reference_pack",
        "path": "01_Structural/R07_Fresh_Blind_Holdout/REFERENCE_PACK.zip",
        "role": "locked references for the consumed diagnosis evidence",
        "expected_sha256": "44d3fa833d64a6df05cca1a8670b2ab0586e930fcb28dbb2418c7b5531cb3aff",
    },
    {
        "dataset_id": "r07_attack_calibration_source_capture",
        "path": "01_Structural/Attack_Calibration_v1/SOURCE_CAPTURE.zip",
        "role": "development-only physical attack calibration capture",
        "expected_sha256": "c0a7ff155d7bcfc34cdcb84913b22cea569a6f7ace19efe48587a82cfa88cd67",
    },
    {
        "dataset_id": "r07_attack_calibration_reference_pack",
        "path": "01_Structural/Attack_Calibration_v1/REFERENCE_PACK.zip",
        "role": "locked physical attack calibration references",
        "expected_sha256": "9778b5d3c3afa0243f4561302d72e9805eab1c5020cabaacd1d698850d8a2183",
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rgb_pixel_sha256(path: Path) -> str:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        digest = hashlib.sha256()
        digest.update(width.to_bytes(4, "big"))
        digest.update(height.to_bytes(4, "big"))
        digest.update(rgb.tobytes())
        return digest.hexdigest()


def _table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _verify_references(spec: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    path_column = spec.get("path_column")
    if not path_column:
        return {}
    base = ROOT / spec.get("reference_root", "")
    missing = 0
    hash_mismatches = 0
    hash_column = spec.get("hash_column")
    for row in frame.to_dict("records"):
        candidate = base / str(row[path_column])
        if not candidate.is_file():
            missing += 1
            continue
        if hash_column and str(row.get(hash_column, "")):
            actual_hash = (
                _rgb_pixel_sha256(candidate)
                if spec.get("hash_mode") == "rgb_pixels_with_dimensions"
                else _sha256(candidate)
            )
            if actual_hash != str(row[hash_column]).lower():
                hash_mismatches += 1
    return {
        "referenced_files": len(frame),
        "referenced_files_present": len(frame) - missing,
        "missing_references": missing,
        "reference_hash_mismatches": hash_mismatches,
    }


def _inspect(spec: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / spec["path"]
    result = dict(spec)
    result["exists"] = path.is_file()
    failures: list[str] = []
    if not path.is_file():
        failures.append("missing")
        result["verified"] = False
        result["failures"] = failures
        return result

    result["actual_bytes"] = path.stat().st_size
    result["actual_sha256"] = _sha256(path)
    if "expected_bytes" in spec and result["actual_bytes"] != spec["expected_bytes"]:
        failures.append("byte_size_mismatch")
    if "expected_sha256" in spec and result["actual_sha256"] != spec["expected_sha256"]:
        failures.append("sha256_mismatch")
    if spec["kind"] in {"manifest", "table"}:
        frame = _table(path)
        result["actual_rows"] = len(frame)
        result["columns"] = list(frame.columns)
        if "expected_rows" in spec and len(frame) != spec["expected_rows"]:
            failures.append("row_count_mismatch")
        reference = _verify_references(spec, frame)
        result.update(reference)
        if reference.get("missing_references"):
            failures.append("missing_referenced_files")
        if reference.get("reference_hash_mismatches"):
            failures.append("referenced_file_hash_mismatch")
    result["verified"] = not failures
    result["failures"] = failures
    return result


def _inspect_private(spec: dict[str, Any]) -> dict[str, Any]:
    path = WORKSPACE_DATASETS / spec["path"]
    result = {**spec, "workspace_root": "03_Datasets", "exists": path.is_file()}
    if path.is_file():
        result["actual_bytes"] = path.stat().st_size
        result["actual_sha256"] = _sha256(path)
        result["verified"] = result["actual_sha256"] == spec["expected_sha256"]
    else:
        result["verified"] = False
    return result


def build_inventory() -> dict[str, Any]:
    datasets = [_inspect(spec) for spec in DATASETS]
    private = [_inspect_private(spec) for spec in PRIVATE_ARCHIVES]
    required = [row for row in datasets if row.get("required")]
    return {
        "schema_version": 1,
        "inventory_kind": "reproducible local presence and identity snapshot",
        "active_models": {
            "structural": "structural-r07-corrective-v1",
            "semantic": "semantic-2026.02",
            "decision_layer": "decision-2026.03-r05",
        },
        "summary": {
            "dataset_records": len(datasets),
            "required_records": len(required),
            "required_present": sum(row["exists"] for row in required),
            "required_verified": sum(row["verified"] for row in required),
            "all_required_verified": all(row["verified"] for row in required),
            "optional_records": len(datasets) - len(required),
            "optional_verified": sum(
                row["verified"] for row in datasets if not row.get("required")
            ),
            "private_archive_records": len(private),
            "private_archives_verified": sum(row["verified"] for row in private),
        },
        "rebuild_state": {
            "structural_source_complete": all(
                row["verified"] for row in required if row["branch"] == "structural"
            ),
            "structural_combined_cache": "intentionally absent; deterministic rebuild from retained sources or locked Drive cache",
            "semantic_source_and_splits_complete": all(
                row["verified"] for row in required if row["branch"] == "semantic"
            ),
            "decision_dataset_complete": all(
                row["verified"]
                for row in required
                if row["branch"] == "decision_layer"
            ),
            "formal_r07_promotion": "fresh candidate-bound independent blind acceptance remains pending",
        },
        "datasets": datasets,
        "private_workspace_archives": private,
        "known_provenance_limitations": [
            "The permanent ID of the retained Tranco snapshot was not recorded at acquisition; its exact file SHA-256 is locked.",
            "Large/private data are intentionally not in GitHub; GitHub contains acquisition recipes, contracts, hashes, citations and this audit.",
            "Development and consumed-blind captures cannot be represented as fresh independent promotion evidence.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    inventory = build_inventory()
    rendered = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("dataset inventory is stale; run without --check")
    else:
        OUTPUT.write_text(rendered, encoding="utf-8")
        print(f"wrote {OUTPUT.relative_to(ROOT)}")
    print(json.dumps(inventory["summary"], indent=2))
    if not inventory["summary"]["all_required_verified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
