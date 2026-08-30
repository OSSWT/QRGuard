# QRGuard ML — Start Here

This is the single entry point for current ML work.

## Current state

- Structural `structural-2026.03-r01` is in the local production artifact path
  and serves Gallery and Live Camera through one source-neutral model.
- Semantic `semantic-2026.02` remains frozen.
- Decision `decision-2026.03-r05` is in the local production Fusion path.
- The 120-row production-path evaluator, real Uvicorn HTTP smoke, backend suite,
  Flutter suite and Render static-package smoke passed.
- GitHub push and external Render deployment remain pending.

Read these files in order:

1. [`ml_training/CURRENT_CHECKPOINT.md`](ml_training/CURRENT_CHECKPOINT.md) —
   current hashes, measurements and remaining external deployment steps.
2. [`ml_training/LATEST.md`](ml_training/LATEST.md) — production and rollback sets.
3. [`ml_training/deployment/promotion/structural-2026.03-r01__decision-2026.03-r05/README.md`](ml_training/deployment/promotion/structural-2026.03-r01__decision-2026.03-r05/README.md)
   — post-promotion evidence.
4. [`ml_training/structural/STRUCTURAL_V3_REAL_100X3_RESULTS_2026-08-31.md`](ml_training/structural/STRUCTURAL_V3_REAL_100X3_RESULTS_2026-08-31.md)
   — accepted Structural results.
5. [`ml_training/decision_layer/DECISION_V3_LOCAL_RESULTS_2026-08-30.md`](ml_training/decision_layer/DECISION_V3_LOCAL_RESULTS_2026-08-30.md)
   — Decision results and limitations.
6. [`ml_training/CLEANUP_REVIEW_2026-08-30.md`](ml_training/CLEANUP_REVIEW_2026-08-30.md)
   — canonical, rollback, historical and generated folders.

## Safety rule

RUN5, Structural 2026.02 and Decision 2026.02 remain the rollback set. Do not
declare external deployment complete until Render builds the promoted commit and
remote health/scan smoke passes.
