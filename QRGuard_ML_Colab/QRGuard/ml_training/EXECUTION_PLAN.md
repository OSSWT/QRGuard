# ML retraining execution plan

Status on 2026-08-21: baseline audit, public-data acquisition, Structural v1/v2
experiments, Semantic v2 promotion, Decision v2 promotion, backend/Flutter tests,
and emulator smoke checks are complete. The only incomplete deployment evidence is
the labelled exact QRGuard app-camera collection required by the Structural gate.

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
