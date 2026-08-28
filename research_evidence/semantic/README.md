# Semantic Analysis Evidence

The Semantic branch analyses the decoded URL/payload. Its deployed URL model is a
calibrated hashed character 3–5 gram linear classifier.

## Current experiment

- Experiment: `semantic-2026.02`
- Labels: `0=benign`, `1=dangerous`
- Split control: registered-domain-disjoint train/validation/test groups
- Runtime contract: URL canonicalisation shared by training and serving
- Deployment status: all configured Semantic gates passed

## Contents

- `notebooks/02_Semantic_Training_Colab.ipynb` — Colab training snapshot
- `dataset_documentation/DATASET_CATALOG.md` — dataset and cleaning summary
- `dataset_documentation/manifests/` — source catalogue and audit snapshots
- `references/REFERENCES.md` — official dataset and research links
- `references/REFERENCES.md` — citations and verified source links
- `performance/semantic-2026.02/` — metrics, tables, and figures
- `performance/PERFORMANCE_SUMMARY.md` — interpretation and deployment status

Canonical data stays at `ml_training/datasets/semantic/`; the deployed model stays
at `training/artifacts/semantic/semantic_model.joblib`.
