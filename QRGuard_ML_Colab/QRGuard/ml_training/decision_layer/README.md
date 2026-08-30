# Risk Decision Layer

This layer combines Structural and Semantic probabilities with deterministic
payload rules and branch-availability indicators. It owns Safe/Warning/Blocked
thresholds and partial-analysis behaviour. It is not described as a third ML
analysis branch in the report.

Promotion requires aggregate security gates, all payload/image cell gates, and
the fixed UTAR/Open-Wi-Fi/branch-unavailable regressions.

## Structural v3 recalibration

`decision-2026.03-r05` passed its aggregate and all 36 cell gates against the
accepted `structural-2026.03-r01` fingerprint. The 120-row full candidate stack
also passed its exact-app Camera/Gallery gate. Semantic remains frozen at
`semantic-2026.02`. Structural r01 and Decision r05 have now replaced the local
runtime files and passed post-copy smoke tests; GitHub/Render deployment remains
pending.

Run the candidate without changing the app's current weights:

```powershell
python scripts/train_fusion.py --structural-artifacts ml_training/structural/runs/structural-2026.03-r01/artifacts --decision-version decision-2026.03-r05
```

The normal command writes only a versioned candidate and performance bundle.
Runtime `backend/fusion/fusion_weights.json` changes only when a later reviewed
command includes `--promote` and every decision-layer gate passes.
