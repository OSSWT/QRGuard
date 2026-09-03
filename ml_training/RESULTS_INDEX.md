# ML results and evidence index

## Structural Training

### Active controlled release

- Version: `structural-r07-corrective-v1`
- Source: `structural/src/train_local.py`
- Configuration: `configs/structural-r07-corrective-v1.json`
- Performance: `structural/performance/structural-r07-corrective-v1/`
- Runtime artifact: `../training/artifacts/structural/`
- Product acceptance policy: `structural/R07_PRODUCT_ACCEPTANCE_POLICY.md`

The development gates passed. Formal promotion remains pending a fresh,
candidate-bound independent blind acceptance. Gallery and Camera use the same
artifact; camera quality, module-scale and temporal-consensus policy may return
Rescan when evidence is insufficient.

### Immediate rollback

- Version: `structural-2026.03-r01`
- Performance: `structural/performance/structural-2026.03-r01/`
- Rollback manifest:
  `deployment/rollback/structural-before-r07-controlled-release/ROLLBACK.json`

The rollback manifest records hashes instead of storing another copy of the
44.7 MB model. The source artifact remains locally recoverable and in Git history.

### r07 training lineage

- Initialization evidence: `structural/performance/structural-2026.09-r06/`
- Base r07 evidence: `structural/performance/structural-2026.09-r07/`
- Corrective r07 evidence: `structural/performance/structural-r07-corrective-v1/`
- Controlled physical calibration: `../research_evidence/structural/performance/r07-corrective/`

## Semantic Training

- Version: `semantic-2026.02`
- Source: `semantic/src/train_local.py`
- Performance: `semantic/performance/semantic-2026.02/`
- Runtime artifact: `../training/artifacts/semantic/`
- Rollback lineage: `semantic/runs/semantic-2026.01/`

The active model uses the same canonicalization contract in training and serving.
The removed Transformer/Method-1 runtime was obsolete and is not a rollback for
the current hashed character n-gram model.

## Risk Decision Layer

- Version: `decision-2026.03-r05`
- Training/report generator: `../scripts/train_fusion.py`
- Performance: `decision_layer/performance/decision-2026.03-r05/`
- Runtime weights: `../backend/fusion/fusion_weights.json`
- Frozen input: `../data/qrguard_mix_v2/`
- Rollback: `decision_layer/runs/decision-2026.02/`

## Datasets, licences and citations

- Verified sources: `datasets/references/SOURCES.md`
- Machine-readable registry: `datasets/references/dataset_registry.csv`
- Licence decisions: `datasets/references/DATASET_LICENSES.md`
- Citations: `datasets/references/REFERENCES.bib`
- Archive hashes: `datasets/download_verification.json`
- Retention policy: `DATASET_RETENTION.json`

Public camera data does not replace exact QRGuard runtime captures. Consumed
development evidence may support training or diagnosis but cannot be reused as
fresh blind promotion evidence.

## Deployment

- Authoritative registry: `deployment/model_registry.json`
- Current checkpoint: `CURRENT_CHECKPOINT.md`
- Release summary: `LATEST.md`
- Workspace cleanup record: `CLEANUP_AUDIT.json`
