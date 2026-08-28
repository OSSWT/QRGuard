# Structural Analysis Evidence

The Structural branch analyses the QR image itself and assigns one of three
labels: `clean`, `adversarial`, or `tampered`.

## Current experiment

- Experiment: `structural-2026.02`
- Architecture: ImageNet-pretrained ResNet-18, three-class fine-tuning
- Input contract: RGB, 224 x 224, ImageNet normalisation
- Leakage control: group-disjoint split by source dataset, capture session,
  physical QR identity, and payload hash
- Candidate status: research gates passed; deployment gate remains blocked until
  exact QRGuard app-crop sessions are collected for all three classes

## Contents

- `notebooks/01_Structural_Training_Colab.ipynb` — Colab training snapshot
- `dataset_documentation/DATASET_CATALOG.md` — admitted, quarantined, and planned data
- `dataset_documentation/manifests/` — reproducibility/audit snapshots
- `references/REFERENCES.md` — official dataset and research links
- `performance/structural-2026.02/` — current candidate metrics and figures
- `performance/PERFORMANCE_SUMMARY.md` — interpretation and deployment status

Do not redirect training code into this folder. Canonical data stays at
`ml_training/datasets/structural/` and exact app captures stay at
`data/runtime_captures/`.
