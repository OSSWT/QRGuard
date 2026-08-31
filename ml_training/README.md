# QRGuard ML Training

This is the canonical, report-facing machine-learning workspace. The project has
two trained branches only:

1. **Structural Training** analyses the QR image and predicts `clean`,
   `adversarial`, or `tampered`.
2. **Semantic Training** analyses the decoded URL/payload and estimates semantic
   risk.

The **Risk Decision Layer** combines both branches with deterministic security
rules. It is a calibrated decision component, not a third ML branch.

Legacy names such as `Method 1`, `RUN 4`, and `RUN 6` are retained only in
historical files and compatibility imports. New reports, artifacts, and commands
use `structural` and `semantic` consistently.

## Directory contract

```text
ml_training/
  configs/              immutable JSON configuration per experiment
  datasets/             raw/processed data locations and manifest contract
  references/           citations, licences, provenance, dataset registry
  structural/           image-model code, notebooks and performance outputs
  semantic/             URL/payload-model code, notebooks and performance outputs
  decision_layer/       branch fusion, threshold calibration and cell gates
  datasets/             Structural/Semantic data contracts, shared references,
                        generated QR provenance and QR_Codes_Demo
  deployment/           candidate/approved model registry and promotion checks
  scripts/              shared dataset, environment and reporting utilities
```

Raw datasets, processed images, checkpoints, and exported models are intentionally
ignored by Git. Their identity is preserved through source URLs, versions,
licences, manifests, counts, and SHA-256 hashes.

## Promotion policy

A run is not deployable because aggregate accuracy is high. It must pass its
branch-specific acceptance gates, export parity checks, and the end-to-end
Gallery/Live-camera matrix. Failed candidates remain in history; an accepted
promotion preserves the previous deployed set as rollback evidence.

The canonical execution order is documented in [EXECUTION_PLAN.md](EXECUTION_PLAN.md).
The final run folders, report tables, figures, citations, deployment artifacts, and
remaining evidence boundary are indexed in [RESULTS_INDEX.md](RESULTS_INDEX.md).
The exact RGB preprocessing and coloured-QR coverage are documented in
[COLOR_PIPELINE.md](COLOR_PIPELINE.md).

The complete Drive/Colab hand-off is generated with
`python scripts/build_colab_bundle.py`. It creates the ignored
`dist/QRGuard_ML_Colab/` and `dist/QRGuard_ML_Colab.zip`; generated copies are no
longer tracked beside their canonical sources. The package contains Structural
training plus frozen Semantic and Decision report notebooks, performance validation,
dataset provenance and reference results.
