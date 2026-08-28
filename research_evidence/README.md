# QRGuard Structural and Semantic ML evidence bundle

This folder is the human-readable entry point for QRGuard's two machine-learning
branches. It was organised on 2026-08-26 without changing the canonical training,
runtime, model, or deployment paths.

## Layout

```text
research_evidence/
  structural/
    notebooks/            Google Colab notebook snapshot
    dataset_documentation/ Dataset catalogue and reproducibility manifests
    references/           Source links and Structural research references
    performance/          Report-ready metrics and figures
  semantic/
    notebooks/            Google Colab notebook snapshot
    dataset_documentation/ Dataset catalogue and reproducibility manifests
    references/           Source links and local articles/journals
    performance/          Report-ready metrics and figures
```

## Important path rule

This is an evidence and navigation bundle, not a second training workspace.
Large datasets are deliberately **not duplicated** here. Training continues to use:

- `ml_training/datasets/structural/`
- `ml_training/datasets/semantic/`
- `data/runtime_captures/`

Models and deployment continue to use:

- `training/artifacts/`
- `ml_training/deployment/model_registry.json`
- `backend/fusion/fusion_weights.json`

The copied notebooks and performance files are traceable snapshots. Their
canonical sources remain under `QRGuard_ML_Colab/` and `ml_training/`.

## Scope

- **Structural** predicts `clean`, `adversarial`, or `tampered` from a QR image.
- **Semantic** predicts URL/payload risk from the decoded content.
- The **Risk Decision Layer / Fusion** combines branch evidence and rules. It is
  not a third dataset or third ML training branch.

## Deployment safety

Creating this folder does not trigger a deployment. `render.yaml` keeps automatic
deployment disabled, and `.dockerignore` excludes this evidence bundle from the
backend container. No runtime dataset, trained model, secret, database, or deployed
service data was moved.
