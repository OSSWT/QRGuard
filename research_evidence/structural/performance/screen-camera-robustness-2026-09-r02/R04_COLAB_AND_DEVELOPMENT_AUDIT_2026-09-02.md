# Structural r04 Colab and development audit

Date: 2026-09-02 (Asia/Kuala_Lumpur)

## Candidate identity

- Version: `structural-2026.09-r04`
- Run ID: `colab-r04-hard-negative-v1`
- Colab result ZIP SHA-256: `711f08269ac23590086c6dbe84b664216c5baec7223f51440b4932e83259627c`
- Best checkpoint SHA-256: `9496b466d6f1642e397dd5fcda26f2aec6347ba7183b9a48e2ebb411bc575fe1`
- FP32 ONNX SHA-256: `240079d09f6c0ed35163d0e32edd735ee8e2315db8ca9e0e98d771d0da59b8f5`
- Locked config SHA-256: `199e319026cf4f7c7e0d6401c9720747a1e1ce80cbf36315db089182e1441c75`
- Locked manifest SHA-256: `85afbdc2b1d28a275eb86486c4c9e61fcde8401fcf65d890b2813689d0078644`

## Colab result

Training completed normally for six epochs; epoch 3 was selected with score `0.9369803`.

- Grouped synthetic test macro-F1: `0.955811`
- Synthetic adversarial recall: `0.972222`
- Synthetic tampered recall: `0.927778`
- QR-DN clean false-positive rate: `0.0`
- Exact-app runtime holdout: clean FPR `0.0625`, adversarial recall `1.0`, tampered recall `1.0`
- Exported authoritative test (120 sessions): clean FPR `0.05`, adversarial recall `0.975`, tampered recall `1.0`
- Exported camera-only test (60 sessions): clean FPR `0.10`, adversarial recall `0.95`, tampered recall `1.0`
- Exported gallery-only test (60 sessions): all class recalls `1.0`, clean FPR `0.0`
- Paired gallery/camera agreement: `0.95`
- All 361 authoritative sessions: clean FPR `0.0413`; camera clean FPR `0.05`, adversarial recall `0.97`, tampered recall `1.0`
- Exposure agreement: `0.989362`; clean exposure span P95: `0.077353`
- Expected calibration error: `0.034495`

The two camera clean test errors had structural probabilities `0.5812` and `0.6248`. Both are below the production camera policy floor `0.70`, so a live-camera decision is converted to rescan unless the three-frame consensus clears the floor. This prevents those borderline predictions from becoming hard blocks, but it does not satisfy the stricter model deployment gate.

The third camera test error was an overexposed adversarial sample predicted clean at structural probability `0.0243`.

## Retired acquisition replay

The acquisition archive used to create the r04 hard negatives was replayed only as a training-fit diagnostic. It produced `0/90` structural clean false positives and `30/30` structural attack detections. SEM-11 produced `0/15` frame errors and `0/3` session errors. SEM-05 produced no structural branch errors among payload-matched frames.

These results confirm that r04 learned the exposure and module-scale cases it was given. They are not independent evidence because those six QR identities and 90 clean frames were part of training.

## Consumed blind archive replay

The earlier blind archive had already influenced r01 and is no longer blind. It was therefore evaluated with evidence role `development_replay`, which permanently makes it ineligible for promotion evidence.

- Clean low-density V1-V3: `5/5` correct
- Clean medium-density V4-V6: `5/5` correct
- Clean high-density V7+: `3/6` false blocks and `1/6` rescan
- Tampered: `16/16` correct
- Adversarial: only `2/16` physical attacks survived capture, so attack evidence is insufficient
- Clean layout probability span: `0.9909`, a severe invariance failure

All three clean false blocks were previously unseen Version 12, 65x65-module, 132-byte payload symbols using mask patterns 4, 1, and 2. Their structural probabilities were `0.8488`, `0.9922`, and `0.8827`. Other Version 12 masks were correct or rescan, showing that the failure is not explained by exposure alone; it is a version/payload/mask-topology confound.

The frozen r04 ONNX was also evaluated before retraining on the new, independent-payload topology validation matrix. Across 512 clean counterfactual rows and 32 logical payload groups, its clean FPR was `0.064453` and its within-group structural-probability span P95 was `0.799788`. Version-specific FPR was V3 `0.1875`, V5 `0.125`, V7 `0.125`, V10 `0.078125`, and zero on the generated V12+ rows. Mask 4 had the worst FPR at `0.109375`, followed by mask 7 at `0.09375`. This result confirms a broader legal-topology/screen-texture shortcut even though the generated V12 cases are easier than the real consumed replay.

## Decision

`r04` is rejected and remains unpromoted. Research gates passed, but the exact app-camera clean FPR exceeded the locked `0.05` deployment limit, a fresh blind holdout was absent, and the non-promoting development replay exposed high-density mask sensitivity.

The next candidate must add grouped counterfactual clean coverage across QR versions, payload lengths, and all eight mask patterns while retaining SEM-05/SEM-11, exposure, physical-tamper, and adversarial gates. A fresh blind pack must not be captured until the new candidate first passes development evidence.
