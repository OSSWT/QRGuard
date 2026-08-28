# Semantic Training baseline performance

Status: **REJECTED as a replacement baseline**. Aggregate corpus performance is
high, but the behavioural benign gate fails.

| Metric | Value |
|---|---:|
| Test accuracy | 0.9776 |
| Test F1 | 0.9625 |
| Test ROC-AUC | 0.9944 |
| Behavioural accuracy | 0.6500 |
| Behavioural benign FPR | 0.7000 |
| Behavioural phishing recall | 1.0000 |
| Maximum benign p_url | 0.9896 |
| Calibrated ECE | 0.0052 |
| INT8 latency median / P95 | 32.2 / 45.4 ms |

Gate failures:

- behavioural benign FPR 0.7000 > 0.0500
- official benign max p_url 0.9896 > 0.3500
