# Structural Training performance

Architecture: ImageNet-pretrained ResNet-18, 3-class fine-tuning
Synthetic grouped test identities: 180
QR-DN external clean identities: 25

| Metric | Result |
|---|---:|
| Synthetic grouped accuracy | 0.8907 |
| Synthetic grouped macro-F1 | 0.8892 |
| Adversarial recall | 0.9611 |
| Tampered recall | 0.9222 |
| QR-DN clean false-positive rate | 0.0000 |
| QR-DN median `p_structural` | 0.0035 |
| ECE | 0.0126 |
| ONNX P95 latency | 44.63 ms |

Status: **CANDIDATE ONLY**

Deployment gate failures:

- exact app-crop gate: clean: 0 sessions; require 100
- exact app-crop gate: clean test: 0 sessions; require 20
- exact app-crop gate: adversarial: 0 sessions; require 100
- exact app-crop gate: adversarial test: 0 sessions; require 20
- exact app-crop gate: tampered: 0 sessions; require 100
- exact app-crop gate: tampered test: 0 sessions; require 20
