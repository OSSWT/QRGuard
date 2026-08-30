# r01 + r05 production promotion evidence

Status: **local production promotion and smoke tests passed; external deployment
pending**.

The active runtime files now contain Structural r01 and Decision r05. The full
120-row locked evaluator was rerun from those production paths and passed with
the same hashes and metrics as the candidate evaluation.

Evidence in this directory:

- `candidate_stack_metrics.json` — full production-path locked evaluation.
- `candidate_stack_predictions.csv` — local per-row audit output; ignored by Git.
- `PRODUCTION_SMOKE.json` — actual Uvicorn HTTP and Render static-package smoke.

Docker was not installed on this workstation. The Dockerfile packaging contract
passed and the actual Docker build must be verified by Render after GitHub push.
This limitation does not replace the successful production-path Uvicorn test.
