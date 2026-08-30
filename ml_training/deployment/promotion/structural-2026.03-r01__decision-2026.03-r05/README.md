# r01 + r05 production promotion evidence

Status: **local promotion, Render deployment and remote smoke tests passed**.

The active runtime files now contain Structural r01 and Decision r05. The full
120-row locked evaluator was rerun from those production paths and passed with
the same hashes and metrics as the candidate evaluation.

Evidence in this directory:

- `candidate_stack_metrics.json` — full production-path locked evaluation.
- `candidate_stack_predictions.csv` — local per-row audit output; ignored by Git.
- `PRODUCTION_SMOKE.json` — local and remote Uvicorn/Render HTTP, Web and APK smoke.

Docker was not installed on this workstation, so the pre-push container check was
limited to the Dockerfile contract and production-path Uvicorn test. Render then
built the actual Docker image from deploy commit `6f17d664e0d1f3f4e30d643c3592dceacabd32fa`;
the API and static site became live and passed remote health/scan/APK verification.
