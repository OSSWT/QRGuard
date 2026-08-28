# Semantic performance summary

## Deployed run: `semantic-2026.02`

| Metric | Result |
|---|---:|
| Accuracy | 0.8983 |
| Precision | 0.9089 |
| Recall | 0.8853 |
| F1 | 0.8969 |
| ROC-AUC | 0.9566 |
| PR-AUC | 0.9617 |
| Brier score | 0.0783 |
| Expected calibration error | 0.0202 |
| Behavioural benign false-positive rate | 0.0400 |
| Behavioural phishing recall | 1.0000 |
| Median / P95 inference latency | 0.81 ms / 1.03 ms |

## Per-source independent test

| Source | Rows | Accuracy | ROC-AUC |
|---|---:|---:|---:|
| Malicious URLs | 50,409 | 0.8880 | 0.9500 |
| PhiUSIIL | 20,397 | 0.9266 | 0.9813 |
| Tranco benign-only | 9,194 | 0.8921 | not applicable |

All configured Semantic research and deployment gates passed. The deployed model
is `training/artifacts/semantic/semantic_model.joblib`; its registry SHA-256 starts
with `a15a` and the recorded size is 6,060,168 bytes.

Machine-readable metrics, composition, behavioural acceptance, per-source tables,
and figures are stored in the adjacent `semantic-2026.02/` snapshot. Canonical
performance evidence remains under `ml_training/semantic/performance/`.
