# QRGuard r02 Colab audit — 2026-09-02

## Decision

The locked 11,500-row `structural-2026.09-r02` candidate completed all Colab
phases and all seven training epochs. The run is reproducible and all expected
checkpoint, artifact, and performance files were recovered from Drive.

The candidate is **not approved for deployment**. Production
`structural-2026.03-r01` was not replaced. The completed candidate fails the
synthetic macro-F1 and calibration gates, has no candidate-matched blind
holdout, and also fails the independent development-camera replay gate.

## Phase 3 incident and correction

The initial complete-data preparation produced the expected 11,500 rows but
failed its manifest SHA-256 contract. The dataset content was unchanged; the
manifest byte order differed between a fresh build and a cache-hit build:

- a fresh build appended all FGSM rows and then all PGD-20 rows;
- a cache-hit build appended adversarial rows in base-group order.

Adversarial rows are now canonicalized by `(group_id, attack_recipe, path)`
before the manifest is written. A regression test covers fresh/cache ordering.
The corrected locked manifest is:

- rows: `11,500`;
- SHA-256: `d4aab55564f269a07094a47f6d51c036c39beb4f72e4220490b53615aac54ebb`.

The corrected deterministic Colab bundle is 131,682,070 bytes with SHA-256
`aad08e41d7fd0376246ca3fc02a781639ea7b7ccb77384d6d296917ba976676e`.

## Completed full run integrity

- Run ID: `r02-full-11500-v2`.
- Mode/status: `fresh` / `evaluated`.
- Epochs completed: 7/7.
- Best checkpoint: epoch 6; selection score `0.9647904315666437`.
- Config SHA-256:
  `9b28e46453147984cc4b46ae0a5c9fe754d6f31d10d6df708fb685be8b312376`.
- Manifest SHA-256:
  `d4aab55564f269a07094a47f6d51c036c39beb4f72e4220490b53615aac54ebb`.
- Best checkpoint SHA-256:
  `48f63fa981b5d7645bca25c352e47d90a2b01aabbb61025acfc929c2b3fd870e`.
- Exported ONNX SHA-256:
  `0f24cc8aaa7a36e3157d0b5ff6eb2d38c673316c779c04b22954f591e4ef2a03`.
- Drive/local result verification: 31/31 files matched by SHA-256;
  202,213,805 total bytes.

## Colab evaluation

| Metric | Result | Gate |
|---|---:|---|
| Synthetic grouped macro-F1 | 0.8213 | fail, require >= 0.8500 |
| Synthetic grouped accuracy | 0.8296 | evidence |
| Synthetic ECE | 0.0781 | fail, require <= 0.0500 |
| Adversarial recall | 1.0000 | pass |
| Tampered recall | 0.9444 | pass |
| QR-DN clean FPR | 0.0000 | pass |
| Exact app-camera clean FPR | 0.0000 | pass |
| Exact app-camera adversarial recall | 1.0000 | pass |
| Exact app-camera tampered recall | 1.0000 | pass |
| Paired Gallery/Camera verdict agreement | 0.9667 | pass, require >= 0.9500 |
| Exposure-sweep verdict agreement | 0.9894 | pass, require >= 0.9500 |
| Clean exposure probability-span P95 | 0.0649 | pass, require <= 0.1500 |

The controlled synthetic clean slices still show a serious domain weakness:
the worst clean FPR is 0.8462 on the `normal` slice, with additional high FPRs
for glare, screen moire/compression, and overexposure. This is consistent with
the sub-threshold synthetic macro-F1 and must not be hidden by the stronger
exact-app held-out slice.

Colab correctly produced `DEPLOYMENT_REJECTED.json` with three reasons:

1. synthetic grouped macro-F1 below the locked threshold;
2. synthetic ECE above the locked threshold;
3. missing candidate-matched fresh blinded Structural coverage holdout.

## Independent replay on the returned 120-frame development capture

The exported ONNX was replayed against the same fixed 24-session capture used
to compare r01 and the earlier 11,261-row attempt. This is development evidence,
not an independent promotion holdout.

- Structural clean FPR: 10/90 (11.1%); fail, require <= 5%.
- Attack detection: 30/30 (100%); pass.
- Exposure verdict agreement: 5/8 (62.5%); fail, require 8/8 for this matrix.
- Clean exposure probability-span P95: 0.6549; fail, require <= 0.15.
- SEM-11 false Blocked: 0/15 frames and 0/3 sessions; pass.
- SEM-05 intended Blocked: 2/3 sessions.
- SEM-05 payload-matched Semantic misses: 0.
- SEM-05 masked Structural branch errors: 1; fail.

The full model therefore preserves the SEM-11 correction and attack recall,
but the internal exposure improvement did not generalize to the older real
development matrix. The hidden SEM-05 branch check also prevented a false
claim of success based only on the final Blocked verdict.

Reports are preserved in:

- `ml_training/structural/runs/structural-2026.09-r02/colab-r02-full-11500-v2`;
- `MODEL_REPLAY_R02_FULL_11500_V2/ANALYSIS.json`;
- `MODEL_REPLAY_R02_FULL_11500_V2/VALIDATION_GATE.json`.

## Promotion boundary

The next candidate iteration must improve grouped clean/tampered separation and
calibration, then pass this development replay. Only after that succeeds should
a new device/display/session blind holdout be collected. The returned capture
used here must never be reused as the final promotion holdout.
