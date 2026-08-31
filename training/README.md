# Production runtime artifacts

This directory contains only artifacts consumed by the application or retained
for an explicit compatibility boundary. Training recipes, notebooks, runs and
performance evidence live under `ml_training/`.

## Active

| Path | Purpose |
|---|---|
| `artifacts/structural/` | Promoted `structural-2026.03-r01` ONNX runtime artifact |
| `artifacts/semantic/` | Promoted frozen `semantic-2026.02` runtime artifact |
| `backend/fusion/fusion_weights.json` | Promoted `decision-2026.03-r05` decision artifact |

Production selects the unified Structural artifact through
`QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS=training/artifacts/structural`. The
versioned source run, metrics and promotion evidence remain under
`ml_training/structural/` and `ml_training/deployment/`.

## Compatibility-only local artifact

`artifacts/method1/` is an ignored legacy DomURLs_BERT rollback used by optional
compatibility tests. It is not the automatic Semantic branch and is not published
as a current model.

Historical Structural RUN1–RUN5 directories and the old top-level artifact ZIP
were moved to the local history area:

`05_ML_Training_History_and_Colab/Legacy_Runtime_Artifacts/`

They are not required by the current production stack. Canonical rollback records
remain versioned under `ml_training/deployment/rollback/`.
