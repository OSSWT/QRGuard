# QRGuard supporting research evidence

This folder contains compact evidence that is unique to diagnosis, physical
capture studies or report traceability. Canonical model performance, notebooks,
datasets and runtime artifacts are not duplicated here.

## Retained evidence

- `structural/performance/r07-corrective/` — controlled attack-calibration
  survival and replay results for the active r07 controlled release.
- `structural/performance/live-camera-repeatability-*/` — evidence supporting
  temporal consensus and image-quality policy.
- `structural/performance/screen-camera-robustness-*/` — the diagnostic chain
  that exposed SEM-11, exposure, module-scale and topology failures.
- `decision/performance/` — bounded candidate-stack camera-policy comparisons.
- `semantic/dataset_documentation/` and `semantic/references/` — compact
  source, cleaning and citation records.

## Canonical sources

- Model performance: `ml_training/*/performance/`
- Generated notebooks: `ml_training/*/notebooks/`
- Datasets: `ml_training/datasets/` and `data/`
- Runtime models: `training/artifacts/`
- Deployment state: `ml_training/deployment/model_registry.json`

Research evidence does not select a runtime model or trigger deployment. The
active versions and formal limitations are recorded in
`ml_training/CURRENT_CHECKPOINT.md`.
