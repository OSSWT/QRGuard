# Decision v3 local results — updated 2026-08-31

Latest candidate: **`decision-2026.03-r05`**
Status: **all gates passed; promoted locally; external deployment pending**

## What was calibrated

The Decision layer was recalibrated on QRGuard-Mix-v2 using:

- the accepted source-neutral `structural-2026.03-r01` artifact;
- frozen `semantic-2026.02` URL outputs;
- deterministic payload-policy flags and branch-availability indicators;
- source-neutral quality abstention for unusable image evidence;
- a serving-parity rule that a completed non-clean Structural class is confirmed
  manipulation and must be at least Blocked.

Training used 1,260 rows. Evaluation used the fixed, cell-stratified 540-row
holdout covering six payload types crossed with six image/evidence modes.

## Decision holdout results

| Metric | Result | Gate |
|---|---:|---:|
| ROC-AUC | 0.9820 | reported |
| Blocked-tier precision | 0.9912 | >= 0.95 |
| Safe-tier false-negative rate | 0.0194 | <= 0.02 |
| Exact Safe/Warning/Blocked accuracy | 0.8667 | reported |
| Security-impact policy acceptance | 0.9759 | all cell gates apply |
| Safe threshold | score below 26 | tuned on training split |
| Blocked threshold | score at least 76 | tuned on training split |

All aggregate and 36 cell gates passed. Failed r02-r04 threshold experiments are
retained as history; they are not active candidates.

## Full backend candidate-stack gate

The real backend pipeline was then evaluated with Structural r01 and Decision r05
on all 120 locked authoritative exact-app test crops.

| Metric | Camera | Gallery |
|---|---:|---:|
| Clean false-block rate | 0.0000 | 0.0000 |
| Adversarial Blocked recall | 0.9500 | 1.0000 |
| Tampered Blocked recall | 1.0000 | 1.0000 |

Final Camera/Gallery verdict agreement was 59/60 (0.9833), above the 0.95 gate.
The one disagreement is an honest Camera Structural miss and remains visible in
the prediction evidence.

## Ablation

| Evaluation | ROC-AUC | Binary accuracy |
|---|---:|---:|
| Structural only | 0.8531 | 0.8037 |
| Semantic and rules only | 0.7426 | 0.6574 |
| Fused evidence | 0.9857 | 0.9648 |

Structural detects manipulation in QR pixels. Semantic and rules inspect decoded
content. Fusion combines them while treating blur, glare, exposure and distance
as quality conditions rather than attacks.

## Limitations and promotion boundary

QRGuard-Mix-v2 has no LLM-labelled subset, so `llm_score`/`llm_invoked` weights
are untrained and must not be described as validated LLM-aware Fusion. Semantic
was not retrained. The 100x3 exact-app campaign is sufficient for the configured
deployment gate, but it is still one-device/one-operator evidence rather than a
multi-device field study.

The accepted weights and Structural artifact now occupy the local runtime paths
and passed production-path evaluation and HTTP smoke. GitHub and the external
service have not changed. See `ml_training/CURRENT_CHECKPOINT.md` for the remote
deployment sequence.
