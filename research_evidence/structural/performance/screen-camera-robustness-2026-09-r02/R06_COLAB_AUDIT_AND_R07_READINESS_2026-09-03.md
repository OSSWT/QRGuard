# Structural r06 Colab audit and r07 readiness

Date: 2026-09-03 (Asia/Kuala_Lumpur)

## Candidate identity and execution

- Version: `structural-2026.09-r06`
- Run ID: `r06-topology-generalisation-v1`
- Bundle SHA-256: `29148f4374192715203baeade98228c95400266a72997e657968d2cf45881a35`
- Best checkpoint SHA-256: `95a499bb8e5bf4f95cb9ad311266faffd65d2b25bacefe822fcf5799686f5781`
- Last checkpoint SHA-256: `aaa00cba8aa5a1434d509ddc897c32c91a3ee058a7e6b7ca662a4390624adbd5`
- FP32 ONNX SHA-256: `7cb75a2af193b395d03e195c197c53f4433c9f64df1581837ee45601f866a5e2`
- Metrics SHA-256: `23ba0bd028394fa994b104ee703c79c6619fefc6874f7680194d163101638536`
- Locked config SHA-256: `79b9046021591a2cece22294334a2390d22bef5649ad13086eb96019a9817b05`
- Locked manifest: 14,150 rows / 1,821 groups; SHA-256 `c553efd57c707d1f60457ade0ffa2d2675e225727b95d8cea17820ed56a96d16`

Training resumed safely after epoch 2 and completed epoch 6. Epoch 5 was selected
with score `0.5620368`. The checkpoint-resume failure seen during execution was
an infrastructure compatibility issue: loading the checkpoint directly onto
CUDA also moved CPU generator states to CUDA. The permanent bundle now loads
portable checkpoint state on CPU and normalises all Torch/CUDA/sampler RNG
states to CPU `uint8` before restoration. The corrected resume/package test set
passed (`5` focused tests and `16` package/regression tests).

The final process returned code 2 only after writing and validating a complete
candidate report. No production artifact was replaced or deployed.

## r06 measured result

- Grouped synthetic accuracy: `0.931481`
- Grouped synthetic macro-F1: `0.931723`
- Synthetic clean recall: `0.894444` (`161/180`)
- Synthetic adversarial recall: `0.966667` (`174/180`)
- Synthetic tampered recall: `0.933333` (`168/180`)
- QR-DN clean FPR: `0/2250`
- Exact-app Camera holdout: clean FPR `0.0`, adversarial recall `1.0`, tampered recall `1.0`
- Exact-app Gallery holdout: clean FPR `0.0`, adversarial recall `1.0`, tampered recall `1.0`
- Gallery/Camera verdict agreement: `0.983333`
- Exposure-sweep verdict agreement: `1.0`
- Clean exposure probability-span P95: `0.026529`
- Synthetic test ECE: `0.022349`
- ONNX P95 latency: `50.95 ms`

The synthetic clean gate missed `0.90` by one additional correct clean sample.
Of the 19 clean errors, 18 were predicted adversarial and one was predicted
tampered. Several errors were close to the decision boundary, but the tail also
contains confident clean-to-adversarial errors, so threshold-only adjustment is
not an adequate fix.

## r05 to r06 comparison

| Metric | r05 | r06 | Direction |
|---|---:|---:|---|
| Synthetic clean recall | 0.738889 | 0.894444 | improved |
| Synthetic macro-F1 | 0.885905 | 0.931723 | improved |
| Topology clean FPR | 0.017578 | 0.000000 | passed |
| Topology probability-span P95 | 0.520148 | 0.338984 | improved, still failed |
| Exact-app Camera clean FPR | 0.000000 | 0.000000 | retained |
| Exposure verdict agreement | 1.000000 | 1.000000 | retained |
| Clean exposure span P95 | 0.011454 | 0.026529 | slightly higher, still passed |

r06 materially corrected r05's ordinary-clean regression and removed all
threshold-crossing errors in the 1,024-row synthetic topology validation set.
It did not make probabilities invariant enough for deployment.

## Topology diagnosis

Across 1,024 clean counterfactual rows / 64 independent payload groups, every
Version (3, 5, 7, 10, 12, 14, 16, 20), every mask (0-7), and both normal and
screen-moire conditions had zero clean false positives. However:

- full-family structural-probability span P95: `0.338984` (gate maximum `0.15`)
- within-condition mask span P95: `0.311971`
- same-mask condition span P95: `0.036295`
- maximum group span: `0.460243` (`synthetic_topology:v07-q-5`)

The remaining synthetic instability is dominated by legal mask/layout changes,
not normal-versus-moire condition changes.

The controlled synthetic quality audit also found high clean FPR on the small
screen-moire/compression (`4/14`) and normal (`11/39`) slices. In contrast, all
94 exact-app runtime holdout rows, including the exact-app moire slice, were
classified correctly. This discrepancy is evidence of source/domain dependence
and must not be averaged away.

## Consumed physical replay

The already-opened M8 archive was evaluated strictly as `development_replay`.
It has no remaining blind or promotion value.

Compared with r05:

| Metric | r05 | r06 |
|---|---:|---:|
| Correct sessions | 0.729167 | 0.708333 |
| Clean false-Blocked rate | 0.062500 (`1/16`) | 0.125000 (`2/16`) |
| Adversarial false-Safe rate | 0.281250 | 0.281250 |
| Rescan rate | 0.062500 | 0.062500 |
| Clean layout probability span | 0.927447 | 0.982719 |

All four non-Safe clean sessions are Version 12, 65-module, 132-byte long
payloads. Masks 1 and 2 were falsely Blocked; masks 4 and 0 produced rescan
outcomes (the mask-0 session also failed module-scale quality). r06 therefore
passes generated V12 rows but does not generalise to the corresponding real
screen-camera domain. Tampered recall remained `16/16`. Only two adversarial
attacks in this archive were independently verified to survive physical
capture, so it remains statistically insufficient for the physical-attack
recall gate.

## Decision and r07 constraints

r06 is rejected and unpromoted. Research gates failed because synthetic clean
recall was `0.894444 < 0.90` and topology probability-span P95 was
`0.338984 > 0.15`. A new fresh blind campaign must not be generated yet.

The next iteration must not merely add more digital masks. r07 should:

1. treat the consumed Version-12/65-module/long-payload screen captures as
   development hard negatives, with group-aware separation from all future
   blind identities;
2. add paired real/simulated screen-camera clean consistency across high module
   counts, masks and controlled module scale, without changing clean labels into
   malicious labels;
3. make checkpoint selection Pareto-constrained by procedural-clean FPR and
   topology span instead of allowing a small selection-score gain to trade away
   clean stability;
4. retain the exact-app Camera, Gallery, exposure, tampered, adversarial,
   SEM-05 and SEM-11 gates unchanged;
5. pass all development gates before generating a newly randomised,
   candidate-frozen blind capture pack.

Evidence output:
`R06_CONSUMED_BLIND_DEVELOPMENT_REPLAY/`. This replay never deploys or mutates
production artifacts.
