# Structural Training performance

Architecture: ImageNet-pretrained ResNet-18, 3-class fine-tuning
Synthetic grouped test identities: 180
QR-DN external clean identities: 25

| Metric | Result |
|---|---:|
| Synthetic grouped accuracy | 0.9111 |
| Synthetic grouped macro-F1 | 0.9095 |
| Adversarial recall | 0.9889 |
| Tampered recall | 0.9500 |
| QR-DN clean false-positive rate | 0.0000 |
| QR-DN median `p_structural` | 0.0001 |
| Controlled nuisance conditions evaluated | 10 |
| Worst controlled clean FPR | 0.5385 (normal) |
| Exact app-camera test frames | 47 |
| Exact app-camera clean FPR | 0.0 |
| Exact app-camera adversarial recall | 0.9333333333333333 |
| Exact app-camera tampered recall | 1.0 |
| Exact app-gallery clean FPR | 0.0 |
| Exported source-neutral camera clean FPR | 0.0 |
| Exported quality abstention rate | 0.0 |
| Paired Gallery/Camera verdict agreement | 0.9833333333333333 |
| ECE | 0.0278 |
| ONNX P95 latency | 44.09 ms |

Status: **DEPLOYMENT APPROVED**
