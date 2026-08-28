# Snapshot provenance

Snapshot date: 2026-08-26

| Bundle content | Canonical source | Handling |
|---|---|---|
| Structural Colab notebook | `QRGuard_ML_Colab/01_Structural_Training_Colab.ipynb` | copied snapshot; canonical file preserved |
| Semantic Colab notebook | `QRGuard_ML_Colab/02_Semantic_Training_Colab.ipynb` | copied snapshot; canonical file preserved |
| Colab requirements/results | `QRGuard_ML_Colab/DATA_REQUIREMENTS.md` and `REFERENCE_RESULTS.md` | copied snapshot |
| Structural manifests/audits | `ml_training/datasets/structural/processed/` and `ml_training/datasets/download_verification.json` | copied lightweight evidence; no image/archive duplication |
| Semantic manifests/audits | `ml_training/datasets/semantic/processed/semantic-2026.02/` | copied lightweight evidence; no parquet duplication |
| Structural candidate performance | `QRGuard_ML_Colab/reference_performance/structural-2026.02/` | copied report snapshot |
| Structural deployed baseline evaluation | `ml_training/structural/performance/deployed_baseline/` | copied report snapshot |
| Semantic performance | `QRGuard_ML_Colab/reference_performance/semantic-2026.02/` | copied report snapshot |
| Local article copies | Local research archive | retained locally and excluded from the public repository; citations and source links remain available |

Intentional notebook/performance copies are small, labelled snapshots for report
navigation. They are not competing training sources. `SNAPSHOT_MANIFEST.sha256`
records the exact content of every publicly included bundled file.
