# QRGuard r02 acquisition/replay checkpoint — 2026-09-02

## Outcome

The returned 24-session, 120-frame screen-camera archive passed the acquisition
gate. It did not pass the locked `structural-2026.03-r01` model replay gate.
Production artifacts were not changed or promoted.

Source archive SHA-256:
`02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4`.

## Acquisition layer

- Complete unique matrix: 24/24 sessions and 120/120 frames.
- Structural quality: 112 usable and 8 marginal; 0 unusable crops saved.
- Exposure capability recorded in all 24 sessions; 3 sessions adjusted exposure.
- Minimum observed scale: 6.945 pixels/module; 0 frames below the 5 px/module gate.
- Acquisition gate: **passed**.

This proves the new quality, exposure, temporal collection, and module-scale
instrumentation produced admissible evidence. It does not prove model accuracy.

## Locked r01 replay

- Clean Structural false positives: 19/90 (21.1%); deployment target ≤5%.
- Clean false positives still above the 0.70 camera floor: 16/90 (17.8%).
- Attack Structural recall: 30/30 (100%).
- Attack frames ending Safe: 0/30.
- Exposure verdict agreement: 6/8 cases (75%); target ≥95%.
- Clean median Structural probability-span P95: 0.769; target ≤0.15.
- Intended final-verdict accuracy: 98/120 frames and 19/24 session majorities.

SEM-11 remained a model failure: 14/15 frames and all 3/3 session majorities
were falsely Blocked. A separate clean V8 case also flipped to Blocked under the
B30 condition.

SEM-05 remained separated from Structural correctness. Among the 9/15 crops the
backend could re-decode and match to the on-device payload hash, Semantic had 0
misses. However, only 2/3 session majorities stayed Blocked, and one payload-
matched frame had a masked Structural branch error. Therefore the hidden-branch
gate also failed; final verdict alone is not accepted as evidence.

Reports:

- `ACQUISITION_VALIDATION/ACQUISITION_AUDIT.json`
- `MODEL_REPLAY_R01/ANALYSIS.json`
- `MODEL_REPLAY_R01/VALIDATION_GATE.json`
- `MODEL_REPLAY_R01/VALIDATION_GATE.md`

## Verification and next boundary

- Backend full suite: **420 passed, 1 skipped, 0 failed**.
- Final Colab/replay targeted suite: **11 passed**.
- Ruff: passed.
- `git diff --check`: passed, with line-ending notices only.
- Deterministic Colab bundle rebuilt twice with the same SHA-256:
  `f620c5b2fc60a18d136d5921d0a6a89559728770f695a87288953b8f35109050`.

The next executable milestone is GPU training of `structural-2026.09-r02` from
the locked Colab bundle. This computer has a GTX 1650 4 GB, but the installed
driver exposes CUDA 11.6 while the project environment contains CPU-only
PyTorch. The prepared Colab GPU route is therefore the efficient path.

## Google Drive staging

The mounted Google Drive was inspected and staged without deleting prior work:

- The existing official `QR-DN1.0.zip` (1,025,545,184 bytes) and
  `qr_codes_in_surfaces.zip` (384,232,282 bytes) were already present.
- The old 1,327,087-byte Colab ZIP was renamed to
  `QRGuard_ML_Colab_legacy_2026-08-30_1327087bytes.zip`.
- The deterministic r02 bundle was copied to
  `My Drive/QRGuard_ML_Colab.zip`; its Drive/local SHA-256 values match.
- `data/runtime_captures` was copied to
  `My Drive/QRGuard_ML_Data/structural/runtime_captures`: 744/744 files and
  59,541,236/59,541,236 bytes, with a matching `manifest_v3.csv` hash.
- A directly openable notebook was copied to
  `My Drive/QRGuard_ML_Notebooks/01_Structural_Training_Colab_r02.ipynb`;
  SHA-256:
  `feabc18c964731818099eb3d67e1a8d3066ab8a3e94dc726f313601266e01a4f`.

Colab was opened. The remaining account-bound interaction is to open that
notebook, select a T4 GPU runtime, leave `RUN_MODE = 'fresh'` and
`RUN_ID = 'r02'`, then choose **Run all**. Checkpoints and outputs will persist
under `My Drive/QRGuard_ML/runs/structural-2026.09-r02/r02/`.

After candidate training, a new capture pack must be generated and collected on
a fresh device/display/session split. This returned development archive must not
be reused as the promotion holdout.
