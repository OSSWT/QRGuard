# Structural v3 Colab run guide

Notebook: **`01_Structural_Training_Colab.ipynb`**
Version: **`structural-2026.09-r07` - REAL DENSE-SCREEN CLEAN RECOVERY CANDIDATE**

## One-time Google Drive setup

Upload these exact paths:

```text
MyDrive/QRGuard_ML_Colab.zip
MyDrive/QRGuard_ML_Data/structural/QR-DN1.0.zip
MyDrive/QRGuard_ML_Data/structural/qr_codes_in_surfaces.zip
MyDrive/QRGuard_ML_Data/structural/runtime_captures/   # when collected
```

Open the Structural notebook from the ZIP/package, choose a T4 GPU for
`fresh`, `resume`, or `evaluate_only`, then edit only the first code cell:

```python
RUN_MODE = "fresh"
RUN_ID = "r07-dense-screen-clean-recovery-v1"
```

Keep `RUN_ID` unchanged when resuming or evaluating the same experiment.

## Which mode to use

| Situation | Mode | What happens |
|---|---|---|
| First training attempt for a new run ID | `fresh` | Starts at epoch 1; refuses to overwrite an existing checkpoint |
| Colab disconnected after at least one epoch | `resume` | Restores model, optimizer, completed epoch, sampler and RNG state |
| Training is finished; recompute fixed metrics/export | `evaluate_only` | Loads the saved best model; performs no training |
| Show saved results to a supervisor | `report_only` | Loads the saved performance bundle; no GPU, dataset preparation or training |

The package includes the rejected r06 checkpoint as initialization plus the
locked r01 coverage, r02 physical-development crops, and 90 clean acquisition-
quality hard negatives. It also includes 80 clean exact-app crops from the now
consumed M8 replay as development-only evidence. The replay's 160 attack crops
are excluded because physical attack survival was underpowered. It does not
contain an r07 result: `report_only` becomes available only after an r07 Drive run has produced and
saved a complete performance folder.

Every completed epoch writes `last_checkpoint.pt`; the best validation model is
`best_model.pt`. Config and manifest SHA-256 values are checked before resume or
evaluation, so changed data cannot silently reuse an incompatible checkpoint.

## Drive outputs

```text
MyDrive/QRGuard_ML/runs/structural-2026.09-r07/<RUN_ID>/
  checkpoints/
    best_model.pt
    last_checkpoint.pt
    run_state.json
  outputs/
    artifacts/
    performance/
```

Keep the complete `outputs/performance/` folder. For the FYP explanation, show:

- `STRUCTURAL_PERFORMANCE.md` and `metrics.csv`;
- `confusion_matrix.png`, `roc_pr_curves.png`, and `calibration_curve.png`;
- `per_quality_condition_results.csv` and `quality_abstention_results.csv`;
- `exported_gallery_camera_consistency.csv` and exported runtime predictions;
- `run_state.json` to prove the exact version/config/manifest identity.

Report row counts and independent group/session counts separately. r07 locks a
14,230-row manifest. It retains 2,560 generated clean counterfactual rows:
Versions 3, 5, 7, 10, 12, 14, 16 and 20; L/M/Q/H correction; all mask patterns
0-7; and normal/screen-moire conditions. Every Version/correction pair has three
independent training payloads and two independent validation payloads. Ordinary
procedural clean QR and topology rows have separate sampling quotas, and a
synthetic-clean recall gate prevents regressions from being hidden by the larger
topology validation slice. The consumed M8 clean identities use a fixed,
group-disjoint 12-train/4-validation split covering V3, V6 and V12. Their five
temporal frames form consistency partners. Feasibility-first checkpoint
selection requires zero M8 clean development false positives while preserving
Camera, topology and ordinary procedural clean limits. All of this remains
development evidence and cannot replace a newly generated physical blind
holdout. The 90 acquisition-quality clean frames remain training only.

## Important interpretation

- Exposure, blur, distance, perspective, glare, shadow, and screen artefacts are
  quality conditions, not malicious classes.
- Exposure/layout consistency is trained across paired exposure views and legal
  mask counterfactuals. Topology rows pair masks four positions apart under the
  opposite normal/screen condition. Exposure is gated again at -0.67, 0, and
  +0.67 EV; topology gets separate clean-FPR and probability-span gates.
- An unusable input must abstain and ask for a rescan.
- Gallery and Camera consistency is measured with the **same exported model** on
  paired cases; it does not mean probabilities must be numerically identical.
- A deployment-gate failure still produces useful FYP evidence, but the output
  remains `CANDIDATE ONLY`.
- The notebook never replaces runtime models, pushes GitHub, or deploys.
- `02_Semantic_Frozen_Report_Colab.ipynb` displays `semantic-2026.02`; it does
  not retrain Semantic.
