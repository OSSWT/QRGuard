# Latest ML versions

Last updated: 2026-08-31.

## Repository production set

| Component | Version | Status |
|---|---|---|
| Structural | **`structural-2026.03-r01`** | Deployed; one artifact for Gallery and Camera |
| Semantic | `semantic-2026.02` | Frozen accepted model |
| Decision | **`decision-2026.03-r05`** | Deployed; Safe < 26, Blocked >= 76 |
| Full stack | r01 + r05 | Local and remote production smoke passed |

GitHub `main` contains commit `e942bbf`; Render API and Web are live from deploy
commit `6f17d664e0d1f3f4e30d643c3592dceacabd32fa`.

The fresh Structural run recorded 0.9111 grouped-test accuracy, 0.9095 macro-F1,
0.0000 QR-DN clean false-positive rate and 0.0278 ECE. On the locked exact-app
holdout, Camera clean false-block was 0.0000, adversarial Blocked recall 0.9500,
tampered Blocked recall 1.0000 and paired final verdict agreement 0.9833.

Decision r05 recorded 0.9820 ROC-AUC, 0.9912 Blocked precision, 0.0194 Safe-tier
false-negative rate and 0.9759 policy acceptance on the fixed 540-row holdout.

## Rollback set

- Gallery Structural RUN5.
- Camera `structural-2026.02`.
- Decision `decision-2026.02`.
- Frozen Semantic remains `semantic-2026.02` in both sets.

## Milestones

1. 361-session audit and zero-leakage manifest. **Completed.**
2. Structural r01 real-data training and gates. **Completed.**
3. Decision r05 calibration and all 36 cell gates. **Completed.**
4. Full candidate and production-path stack gates. **Completed.**
5. Local artifact promotion and production package smoke. **Completed.**
6. GitHub push, Render build and remote smoke. **Completed.**

See `CURRENT_CHECKPOINT.md` for exact hashes and verification evidence.
