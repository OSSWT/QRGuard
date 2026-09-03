# Structural r05 training readiness

Date: 2026-09-02 (Asia/Kuala_Lumpur)

## Locked candidate

- Version: `structural-2026.09-r05`
- Run ID: `r05-topology-counterfactual-v1`
- Initial r04 checkpoint SHA-256: `9496b466d6f1642e397dd5fcda26f2aec6347ba7183b9a48e2ebb411bc575fe1`
- Config SHA-256: `1ff38596f2b528871b9b84c34701355df802e2228dba0ec2ddf5ea72d2608cab`
- Manifest rows: `12,614`
- Manifest SHA-256: `d079321d615db5d3faa3d95a643ed8348fed52647d13406cc3a55b81b67d61c6`
- Colab ZIP bytes: `156,526,784`
- Colab ZIP SHA-256: `fa411a1fd3c36bf8d84b49a29d209a287be203f035f2e306b89e82b474fcc087`

The manifest contract was rebuilt twice from the frozen r04 image cache and passed the exact row/hash check. QR matrix generation is pinned to `qrcode 8.2` so a later package update cannot silently change mask matrices.

## New topology coverage

The candidate adds 1,024 clean development rows in 64 logical payload groups:

- QR Versions 3, 5, 7, 10, 12, 14, 16, and 20;
- payload lengths 24, 40, 64, 112, 132, 180, 220, and 300 UTF-8 bytes;
- error correction L, M, Q, and H;
- every standards-valid mask pattern 0-7;
- normal and moderate screen-moire/compression conditions;
- one payload per Version/error-correction for train and a different payload for validation.

All mask and condition variants of one payload share the same group and consistency partner. No payload crosses train/validation. These rows are development-only and cannot be presented as a fresh blind holdout.

## Training and gates

r05 starts from the rejected r04 checkpoint, skips head-only retraining, and fine-tunes all layers for five epochs at `3e-5`. The acquisition hard-negative multiplier is reduced from 4x to 2x, while topology rows receive 2x priority inside the clean procedural family. This keeps the learned exposure recovery without letting the six acquisition identities dominate training.

Checkpoint selection now applies explicit penalties for topology clean FPR above `0.01` and probability-span P95 above `0.15`. The same limits are research gates in the final report. Existing synthetic attack recall, tamper recall, QR-DN clean FPR, exposure invariance, calibration, exact-app camera, pairing, SEM-05 regression, and fresh-blind requirements remain in force.

The runtime model and deployment registry are unchanged. r05 cannot be promoted by the notebook; after training it must first pass development replay and then a newly generated physical blind holdout using unseen payload/device/display/session combinations.

## Verification completed

- r05 manifest row/hash contract: passed.
- Related topology, sampling, exposure, blind-audit, notebook, and complete
  package regression suite: 39 passed.
- Ruff fatal/import checks: passed.
- Temporary browser, download, screenshot, and pytest files: removed.
