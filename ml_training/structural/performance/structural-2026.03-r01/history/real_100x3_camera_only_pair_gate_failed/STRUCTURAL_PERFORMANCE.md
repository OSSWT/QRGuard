# Structural Training performance

Architecture: ImageNet-pretrained ResNet-18, 3-class fine-tuning
Synthetic grouped test identities: 180
QR-DN external clean identities: 25

| Metric | Result |
|---|---:|
| Synthetic grouped accuracy | 0.9167 |
| Synthetic grouped macro-F1 | 0.9154 |
| Adversarial recall | 1.0000 |
| Tampered recall | 0.9556 |
| QR-DN clean false-positive rate | 0.0000 |
| QR-DN median `p_structural` | 0.0024 |
| Controlled nuisance conditions evaluated | 10 |
| Worst controlled clean FPR | 0.5455 (glare) |
| Exact app-camera test frames | 47 |
| Exact app-camera clean FPR | 0.0 |
| Exact app-camera adversarial recall | 0.9333333333333333 |
| Exact app-camera tampered recall | 1.0 |
| Exact app-gallery clean FPR | 0.0 |
| Exported source-neutral camera clean FPR | 0.0 |
| Exported quality abstention rate | 0.0 |
| Paired Gallery/Camera verdict agreement | 0.8166666666666667 |
| ECE | 0.0300 |
| ONNX P95 latency | 50.42 ms |

Status: **CANDIDATE ONLY**

Deployment gate failures:

- paired Gallery/Camera verdict agreement 0.8166666666666667; require min 0.95
