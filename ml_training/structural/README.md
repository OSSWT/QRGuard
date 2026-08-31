# Structural Training

Structural Training consumes the QR image crop and predicts `clean`,
`adversarial`, or `tampered`. Image quality such as blur, glare, perspective, or
camera noise is a capture condition, not an attack label.

The canonical Colab entry point is
`notebooks/structural_training_v3.ipynb`. Older notebook generations are archived
outside the public repository.

The tensor contract is RGB (not CMYK/Lab), 224×224 and ImageNet-normalised; see
`../COLOR_PIPELINE.md`. Audited exact QRGuard app crops in
`data/runtime_captures/manifest.csv` are automatically added to grouped
train/validation splits. Their test sessions stay isolated as
`runtime_holdout_test` and control deployment approval.

Required performance artifacts for every completed run:

- `metrics.json` and `metrics.csv`
- `dataset_composition.csv`
- `training_curves.png`
- `confusion_matrix.png`
- `roc_pr_curves.png`
- `calibration_curve.png`
- `per_source_results.csv`
- `per_device_results.csv`
- `gallery_camera_consistency.csv`
- `misclassified_samples.csv`
- `STRUCTURAL_PERFORMANCE.md`

No deployable export may be created when the real-camera session gate is not
satisfied. External camera datasets improve coverage but do not replace exact
QRGuard runtime crops.
