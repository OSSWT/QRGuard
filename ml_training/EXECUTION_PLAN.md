# ML retraining execution plan

Status on 2026-08-31: the audited 100x3 exact-app collection, Structural v3 real
training, Semantic frozen-report validation, Decision r05 recalibration, full
candidate-stack evaluation, backend regression and Flutter checks are complete.
The candidate set passed its automated gates, was copied into the local runtime
paths, and passed packaged post-copy smoke tests. Remaining work is the reviewed
GitHub push, Render build and remote health/scan verification.

## 1. Freeze and measure the baseline

- Record the installed Structural and Semantic model hashes, calibration values,
  model sizes, and existing fixed-test results.
- Preserve current artifacts as rollback candidates.
- Do not tune against the final independent holdout.

## 2. Acquire and audit data

- Download publicly accessible datasets only from the registered official source.
- Record licence, version, retrieval date, archive hash, and extraction status.
- Quarantine sources with unclear provenance or incompatible labels.
- Treat all frames from one video/burst and all derivatives of one physical QR as
  a single group.
- Keep QRGuard exact runtime crops distinct from external camera imagery.

## 3. Structural Training

- Prepare grouped `train`, `validation`, `test`, and independent `holdout` splits.
- Train the three-class image model with real camera clean images and separately
  labelled physical/synthetic manipulations.
- Calibrate on validation only.
- Produce the complete performance bundle under `structural/performance/`.
- Export only when real-camera gates pass.

## 4. Semantic Training

- Canonicalise URLs and remove label conflicts.
- Split by registrable domain, not by row.
- Keep behavioural hard-benign and unseen-domain cases outside ordinary training.
- Calibrate on validation only.
- Produce the complete performance bundle under `semantic/performance/`.
- Export only when behavioural and per-source gates pass.

Structural and Semantic may train independently once their own data contracts are
satisfied. Their outputs are not promoted independently into the application.

## 5. Risk Decision Layer

- Recompute branch signals using the accepted candidate models.
- Train/calibrate Safe, Warning, and Blocked behaviour over the full payload/image
  matrix.
- Require every per-cell gate as well as aggregate security metrics.

## 6. Deployment

- Verify native framework versus ONNX/TFLite parity.
- Run backend, Flutter, emulator, Gallery, and Live-camera regression suites.
- Promote artifacts atomically and update `deployment/model_registry.json`.
- Preserve the previous approved set for rollback.

Current state: parity, backend, Flutter, locked Gallery/Camera evaluation, local
artifact promotion and packaged runtime smoke passed. GitHub/Render deployment
and remote verification remain pending.
