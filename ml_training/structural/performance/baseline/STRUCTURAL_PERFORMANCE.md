# Structural Training baseline performance

Status: **REJECTED as a replacement baseline**. The currently installed model is
retained only for rollback and comparison.

| Metric | Value |
|---|---:|
| Test accuracy | 0.8604 |
| Macro F1 | 0.8607 |
| Camera-simulated accuracy | 0.8041 |
| Camera-simulated clean false-positive rate | 0.1908 |
| Adversarial recall | 0.7547 |
| Tampered recall | 0.9653 |
| Calibrated ECE | 0.0295 |
| FP32 latency median / P95 | 15.5 / 23.3 ms |

Gate failures:

- camera clean FPR 0.1908 > 0.0500
- adversarial recall 0.7547 < 0.8000
