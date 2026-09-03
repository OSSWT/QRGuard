# Structural Training performance

Architecture: ImageNet-pretrained ResNet-18, 3-class fine-tuning
Synthetic grouped test identities: 180
QR-DN external clean identities: 25

| Metric | Result |
|---|---:|
| Synthetic grouped accuracy | 0.9333 |
| Synthetic grouped macro-F1 | 0.9339 |
| Adversarial recall | 0.9389 |
| Tampered recall | 0.9278 |
| QR-DN clean false-positive rate | 0.0000 |
| QR-DN median `p_structural` | 0.0013 |
| Controlled nuisance conditions evaluated | 10 |
| Worst controlled clean FPR | 0.1538 (normal) |
| Exact app-camera test frames | 47 |
| Exact app-camera clean FPR | 0.0 |
| Exact app-camera adversarial recall | 1.0 |
| Exact app-camera tampered recall | 1.0 |
| Exact app-gallery clean FPR | 0.0 |
| Exported source-neutral camera clean FPR | 0.0 |
| Exported quality abstention rate | 0.0 |
| Paired Gallery/Camera verdict agreement | 0.9666666666666667 |
| Exposure-sweep verdict agreement | 1.0 |
| Clean exposure probability span P95 | 0.007192257791757584 |
| Consumed M8 clean development FPR | 0.0 |
| Consumed M8 clean session FPR | 0.0 |
| Consumed M8 temporal probability span P95 | 0.036787560582160934 |
| Consumed verified-attack non-clean train-fit recall | 1.0 |
| Consumed verified-attack session train-fit recall | 1.0 |
| ECE | 0.0347 |
| ONNX P95 latency | 50.57 ms |

Status: **CANDIDATE ONLY**

Deployment gate failures:

- fresh blinded Structural coverage holdout is missing or does not match this candidate model
