# Structural Training performance

Architecture: ImageNet-pretrained ResNet-18, 3-class fine-tuning
Synthetic grouped test identities: 180
QR-DN external clean identities: 25

| Metric | Result |
|---|---:|
| Synthetic grouped accuracy | 0.9315 |
| Synthetic grouped macro-F1 | 0.9317 |
| Adversarial recall | 0.9667 |
| Tampered recall | 0.9333 |
| QR-DN clean false-positive rate | 0.0000 |
| QR-DN median `p_structural` | 0.0011 |
| Controlled nuisance conditions evaluated | 10 |
| Worst controlled clean FPR | 0.2857 (screen_moire_or_compression) |
| Exact app-camera test frames | 47 |
| Exact app-camera clean FPR | 0.0 |
| Exact app-camera adversarial recall | 1.0 |
| Exact app-camera tampered recall | 1.0 |
| Exact app-gallery clean FPR | 0.0 |
| Exported source-neutral camera clean FPR | 0.0 |
| Exported quality abstention rate | 0.0 |
| Paired Gallery/Camera verdict agreement | 0.9833333333333333 |
| Exposure-sweep verdict agreement | 1.0 |
| Clean exposure probability span P95 | 0.026528887450695038 |
| ECE | 0.0223 |
| ONNX P95 latency | 50.95 ms |

Status: **CANDIDATE ONLY**

Deployment gate failures:

- synthetic clean recall 0.8944 < 0.9000
- topology counterfactual clean probability span P95 0.33898427188396435; require max 0.1500
- fresh blinded Structural coverage holdout is missing or does not match this candidate model
