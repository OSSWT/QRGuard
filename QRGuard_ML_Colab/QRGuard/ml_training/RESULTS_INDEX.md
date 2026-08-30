# ML results and report-material index

This page is the entry point for the final report. New work is classified by the
two report phases, followed by the Risk Decision Layer and deployment evidence.

## Structural Training

### Current local production replacement

- Run: `structural-2026.03-r01`
- Training source: `structural/src/train_local.py`
- Run artifacts: `structural/runs/structural-2026.03-r01/artifacts/`
- Full report: `structural/performance/structural-2026.03-r01/STRUCTURAL_PERFORMANCE.md`
- Machine-readable metrics: `structural/performance/structural-2026.03-r01/metrics.json`
- Exact-app summary: `structural/STRUCTURAL_V3_REAL_100X3_RESULTS_2026-08-31.md`
- Main figures: confusion matrix, calibration curve, training curves, score
  distribution, and grouped-source results in the same performance folder.

The artifact passed research, 100x3 exact-app, paired source-neutral, export,
calibration and latency gates. It occupies the production path, passed post-copy
evaluation and is live on Render after remote smoke. Earlier failed candidates
remain negative evidence and are not active runtime choices.

### External optical evaluation

- Baseline QR-DN result:
  `structural/performance/deployed_baseline/qrdn/QRDN_EXTERNAL_CLEAN.md`
- QR-DN prepared manifest:
  `datasets/structural/processed/qrdn/manifest.csv`
- QR surfaces preparation audit:
  `datasets/structural/processed/qr_surfaces/preparation_audit.json`
- Dynamsoft acquisition-only audit:
  `datasets/holdout/processed/dynamsoft_qr/preparation_audit.json`

## Semantic Training

- Deployed run: `semantic-2026.02`
- Training source: `semantic/src/train_local.py`
- Runtime feature contract: `../backend/semantic/semantic_features.py`
- Run artifacts: `semantic/runs/semantic-2026.02/artifacts/`
- Full report: `semantic/performance/semantic-2026.02/SEMANTIC_PERFORMANCE.md`
- Machine-readable metrics: `semantic/performance/semantic-2026.02/metrics.json`
- Report tables: dataset composition, per-source results, hard-benign results,
  and behavioural acceptance CSV files in the same performance folder.
- Figures: training, confusion, ROC/PR, and calibration plots.

`semantic-2026.01` is retained to show the train–serve skew found after Fusion:
scheme-less training URLs and router-normalised `http://` URLs did not share the
same character n-grams. v2 canonicalises both paths identically.

## Risk Decision Layer

- Current local production: `decision-2026.03-r05` (`decision-2026.02` remains
  rollback)
- Training and report generator: `../scripts/train_fusion.py`
- Frozen data: `../data/qrguard_mix_v2/manifest.csv` and 1,800 named images.
- Run weights: `decision_layer/runs/decision-2026.03-r05/artifacts/fusion_weights.json`
- Full report:
  `decision_layer/performance/decision-2026.03-r05/DECISION_LAYER_PERFORMANCE.md`
- Machine-readable metrics:
  `decision_layer/performance/decision-2026.03-r05/metrics.json`
- Per-cell table:
  `decision_layer/performance/decision-2026.03-r05/per_cell_metrics.csv`
- Figures: tier confusion matrix, risk-score distribution, and branch ablation.

QRGuard-Mix-v2 crosses six payload families with six image/evidence modes. Runtime
policy is applied during evaluation, including open-Wi-Fi floors and camera
abstention, so training metrics do not omit serving behaviour.

## Datasets, licences, and citations

- Human-readable verified sources: `references/SOURCES.md`
- Machine-readable registry: `references/dataset_registry.csv`
- Licence/access decisions: `references/DATASET_LICENSES.md`
- Report-ready BibTeX: `references/REFERENCES.bib`
- Archive hashes: `datasets/download_verification.json`

Do not use or cite a quarantined dataset as training data. Dynamsoft crops are for
acquisition-robustness inspection only. Public camera data does not replace exact
QRGuard runtime crops.

## Deployment and rollback

- Authoritative registry: `deployment/model_registry.json`
- Structural RUN5 rollback: `deployment/rollback/structural-run5/`
- Deployed Semantic artifacts: `../training/artifacts/semantic/`
- Deployed Decision weights: `../backend/fusion/fusion_weights.json`

The 2026-08-21 device baseline recorded 247 backend tests, 58 Flutter tests,
Flutter analysis with no issues, release APK `1.0.0+8003`, Gallery UTAR
Safe/risk 2, and Gallery open Wi-Fi risk 45. Since 2026-08-23, `not_applicable`
branches (including the URL model for Wi-Fi/text/payment payloads) are explicitly
separate from unavailable evidence and no longer create a Partial result.
