# Risk Decision Layer

This layer combines Structural and Semantic probabilities with deterministic
payload rules and branch-availability indicators. It owns Safe/Warning/Blocked
thresholds and partial-analysis behaviour. It is not described as a third ML
analysis branch in the report.

Promotion requires aggregate security gates, all payload/image cell gates, and
the fixed UTAR/Open-Wi-Fi/branch-unavailable regressions.

## Current deployed decision layer

`decision-2026.03-r05` passed its aggregate and all 36 cell gates when it was
trained on the frozen `QRGuard-Mix-v2` branch-signal fingerprint. Semantic stays
frozen at `semantic-2026.02`. The deployed image branch is now
`structural-r07-corrective-v1`; the controlled r07 release and Decision r05 have
passed the recorded production smoke matrix.

The 1,800-row QRGuard-Mix-v2 manifest and all referenced local images remain
available. The manifest SHA-256 is
`6c30bba32aba6cd1b80ef21fe556db73ffc0f73ca0d19015c516dcdd6454cc16`.
See `../datasets/DATASET_CATALOG.md` for provenance and split details.

Run the candidate without changing the app's current weights:

```powershell
python scripts/train_fusion.py --structural-artifacts training/artifacts/structural --decision-version <new-version>
```

Do not overwrite the frozen r05 evidence. A later Decision version must first
regenerate `data/qrguard_mix_v2/branch_signals.csv` against the intended
Structural/Semantic artifacts and record the new fingerprint. The normal command
writes only a versioned candidate and performance bundle. Runtime
`backend/fusion/fusion_weights.json` changes only when a reviewed command includes
`--promote` and every decision-layer gate passes.
