# Existing measured Structural, Semantic and Decision performance

The first table is the measured 2026-08-31 local CPU v3 real-data candidate run.
It is checked-in reproduction evidence, not invented notebook output and not an
automatic production promotion. The second table contains the existing
`2026.02` rollback baseline and frozen Semantic evidence.

| Structural v3 local candidate metric | Measured result |
|---|---:|
| Grouped test accuracy | 0.9111 |
| Grouped macro-F1 | 0.9095 |
| Adversarial recall | 0.9889 |
| Tampered recall | 0.9500 |
| QR-DN clean false-positive rate | 0.0000 |
| Exact-app Camera clean FPR | 0.0000 |
| Exact-app Camera adversarial recall | 0.9500 |
| Exact-app Camera tampered recall | 1.0000 |
| Paired Camera/Gallery verdict agreement | 0.9833 |
| ECE | 0.0278 |
| Controlled nuisance conditions | 10 |
| ONNX P95 latency (local reference machine) | 44.09 ms |
| Research gates | PASS |
| Deployment gates | PASS — deployed and remote-smoke verified |

## Existing 2026.02 baseline and frozen Semantic reference

| Branch / metric | Existing measured result |
|---|---:|
| Structural grouped test accuracy | 0.8907 |
| Structural grouped macro-F1 | 0.8892 |
| Structural adversarial recall | 0.9611 |
| Structural tampered recall | 0.9222 |
| Structural ECE | 0.0126 |
| Structural QR-DN clean false-positive rate | 0.0000 |
| Structural ONNX P95 latency (reference machine) | 44.63 ms |
| Semantic test accuracy | 0.8983 |
| Semantic precision | 0.9089 |
| Semantic recall | 0.8853 |
| Semantic F1 | 0.8969 |
| Semantic ROC-AUC | 0.9566 |
| Semantic PR-AUC | 0.9617 |
| Semantic ECE | 0.0202 |
| Semantic behavioural benign FPR | 0.0400 |
| Semantic behavioural phishing recall | 1.0000 |

## Decision v3 local candidate

| Decision metric | Measured result |
|---|---:|
| Version | decision-2026.03-r05 |
| ROC-AUC | 0.9820 |
| Blocked-tier precision | 0.9912 |
| Safe-tier false-negative rate | 0.0194 |
| Exact three-tier accuracy | 0.8667 |
| Security-impact policy acceptance | 0.9759 |
| Internal Decision gates | PASS — all 36 cells; deployed |

Semantic `semantic-2026.02` passed its recorded gates. Structural
`structural-2026.03-r01` and Decision `decision-2026.03-r05` passed their
recorded local and integration gates and were later promoted into the local
runtime. The Colab package itself never copies runtime files, pushes GitHub, or
deploys services.
