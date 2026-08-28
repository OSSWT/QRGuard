# Semantic Training

Semantic Training consumes decoded URL/payload text. It does not consume camera
pixels. URL rows are grouped by registrable domain to prevent train/test leakage.

The source-labelled inspection catalog is generated at
`ml_training/datasets/semantic/processed/semantic-2026.02/by_source/` by
`src/build_source_catalog.py`. Folder names identify provenance directly:
`PHIUSIIL_UCI`, `MALICIOUS_URLS_KAGGLE`, `TRANCO_BENIGN`, and the two
`QRGuard_DERIVED_*` behavioural probe groups. Use
`source_catalog_manifest.csv` for the official URL, role, row count, and file
hash. These files are inspection exports; training still uses the canonical
split parquet files.

Required performance artifacts for every completed run:

- `metrics.json` and `metrics.csv`
- `dataset_composition.csv`
- `training_curves.png`
- `confusion_matrix.png`
- `roc_pr_curves.png`
- `calibration_curve.png`
- `threshold_analysis.csv`
- `per_source_results.csv`
- `hard_benign_results.csv`
- `behavioural_acceptance.csv`
- `SEMANTIC_PERFORMANCE.md`

Wi-Fi security and analysis availability are policy signals. They must not be
misrepresented as URL-model predictions.

For a fresh Colab workspace,
`src/prepare_colab_data.py` acquires/standardises PhiUSIIL, Malicious URLs and a
dated Tranco list, records hashes/provenance and creates the independent
registrable-domain holdout expected by `src/train_local.py`.
