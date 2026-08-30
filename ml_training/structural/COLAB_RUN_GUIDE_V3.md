# Structural v3 Colab run guide

Notebook: **`01_Structural_Training_Colab.ipynb`**
Version: **`structural-2026.03-r01` — LATEST CANDIDATE**

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
RUN_ID = "r01"
```

Keep `RUN_ID` unchanged when resuming or evaluating the same experiment.

## Which mode to use

| Situation | Mode | What happens |
|---|---|---|
| First training attempt for a new run ID | `fresh` | Starts at epoch 1; refuses to overwrite an existing checkpoint |
| Colab disconnected after at least one epoch | `resume` | Restores model, optimizer, completed epoch, sampler and RNG state |
| Training is finished; recompute fixed metrics/export | `evaluate_only` | Loads the saved best model; performs no training |
| Show saved results to a supervisor | `report_only` | Loads the saved performance bundle; no GPU, dataset preparation or training |

The package also contains the measured 2026-08-30 local CPU reference. If
`RUN_MODE="report_only"` is used before that `RUN_ID` has a Drive performance
folder, the notebook displays this bundled reference and labels it as a local,
non-Colab result. After a Colab run exists, `report_only` always restores that
run's saved Drive output instead.

Every completed epoch writes `last_checkpoint.pt`; the best validation model is
`best_model.pt`. Config and manifest SHA-256 values are checked before resume or
evaluation, so changed data cannot silently reuse an incompatible checkpoint.

## Drive outputs

```text
MyDrive/QRGuard_ML/runs/structural-2026.03-r01/<RUN_ID>/
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

Report row counts and independent group/session counts separately. The scoped
Camera-row budget is 6,457 train, 1,470 validation, and 2,820 holdout rows. The
30 paired Gallery test views add rows, but do not increase the 150 independent
exact-app cases.

## Important interpretation

- Exposure, blur, distance, perspective, glare, shadow, and screen artefacts are
  quality conditions, not malicious classes.
- An unusable input must abstain and ask for a rescan.
- Gallery and Camera consistency is measured with the **same exported model** on
  paired cases; it does not mean probabilities must be numerically identical.
- A deployment-gate failure still produces useful FYP evidence, but the output
  remains `CANDIDATE ONLY`.
- The notebook never replaces runtime models, pushes GitHub, or deploys.
- `02_Semantic_Frozen_Report_Colab.ipynb` displays `semantic-2026.02`; it does
  not retrain Semantic.
