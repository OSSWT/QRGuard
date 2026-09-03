# Structural supporting evidence

The Structural branch classifies a QR image as `clean`, `adversarial` or
`tampered`. Its active controlled release is
`structural-r07-corrective-v1`, shared by Gallery and Live Camera.

This folder retains only diagnostic and physical-channel evidence that is not
duplicated by the canonical performance bundle:

- `performance/r07-corrective/` — final controlled calibration replay.
- `performance/live-camera-repeatability-*/` — temporal acquisition evidence.
- `performance/screen-camera-robustness-*/` — root-cause and corrective
  development evidence.
- `dataset_documentation/manifests/` — the public QR-DN and QR-Surfaces
  per-sample provenance that cannot be recovered from a clean Git checkout.
- `references/` — research references.

Canonical metrics are under
`ml_training/structural/performance/structural-r07-corrective-v1/`. Canonical
datasets remain under `ml_training/datasets/structural/` and `data/`.

The retained diagnostic chain may explain and reproduce design decisions, but
consumed development captures cannot be reused as fresh blind promotion evidence.
