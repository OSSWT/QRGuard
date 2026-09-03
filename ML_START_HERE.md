# QRGuard ML — Start Here

This is the single entry point for current ML work.

## Active stack

- Structural `structural-r07-corrective-v1` serves Gallery and Live Camera from
  one source-neutral artifact. It is an authorized controlled release; a fresh
  candidate-bound blind acceptance is still required for formal promotion.
- Semantic `semantic-2026.02` is the frozen accepted URL/payload model.
- Decision `decision-2026.03-r05` is the accepted Fusion policy.
- The production API, Web application and signed Android package passed the
  recorded remote smoke matrix.

## Read in this order

1. [`ml_training/CURRENT_CHECKPOINT.md`](ml_training/CURRENT_CHECKPOINT.md) —
   current runtime identity, limitations and verification.
2. [`ml_training/LATEST.md`](ml_training/LATEST.md) — active and rollback sets.
3. [`ml_training/RESULTS_INDEX.md`](ml_training/RESULTS_INDEX.md) — canonical
   performance and evidence paths.
4. [`ml_training/DATASET_RETENTION.json`](ml_training/DATASET_RETENTION.json) —
   dataset roles and regeneration boundaries.
5. [`ml_training/deployment/model_registry.json`](ml_training/deployment/model_registry.json)
   — machine-readable deployment state.

## Colab hand-off

Run `python scripts/build_colab_bundle.py` to create the ignored
`dist/QRGuard_ML_Colab/` directory and ZIP. The bundle is generated from current
source and evidence; generated copies are not retained in Git.

## Safety boundary

Keep `structural-2026.03-r01` as the immediate Structural rollback. Do not call
r07 a formal promotion until a new independent blind acceptance satisfies the
locked product policy. Inconclusive camera evidence must remain Rescan and can
never be converted to Safe.
