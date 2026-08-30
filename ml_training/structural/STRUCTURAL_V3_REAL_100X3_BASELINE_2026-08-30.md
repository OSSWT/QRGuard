# Structural v3 pre-real candidate on the audited 100x3 holdout

Version evaluated: **`structural-2026.03-r01` pre-real baseline**
Dataset: **361 accepted exact-app sessions; locked deployment split only for gates**
Status: **failed real-camera deployment gates; retraining required**

The historical r01 candidate passed its public/procedural research gates before
any exact-app training rows existed. It was evaluated unchanged on the newly
audited real dataset to measure the domain gap before retraining.

## Locked deployment holdout

The gate calculation uses only `split=test`: 60 Camera rows and their 60 paired
Gallery rows. Train and validation rows remain available for diagnostics but do
not contribute to the deployment result.

| Metric | Baseline | Required |
|---|---:|---:|
| Camera clean false-positive rate | 0.0000 | at most 0.05 |
| Camera adversarial recall | 0.0000 | at least 0.80 |
| Camera tampered recall | 0.0000 | at least 0.85 |
| Paired Gallery/Camera verdict agreement | 0.7333 | at least 0.95 |

The model classified the real Camera attack samples as clean. This confirms the
original deployment block and provides a measured before-training baseline; it
must not be promoted even though its clean false-positive rate is low.

Canonical output:

```text
ml_training/structural/performance/structural-2026.03-r01/
  real_100x3_baseline_before_retraining/
```

The evaluator also records all 361 authoritative rows for error analysis, but
only the locked test split is used for deployment gates.
