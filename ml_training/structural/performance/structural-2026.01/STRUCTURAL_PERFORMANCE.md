# Structural Training performance

Architecture: ImageNet-pretrained ResNet-18, 3-class fine-tuning
Synthetic grouped test identities: 180
QR-DN external clean identities: 25

| Metric | Result |
|---|---:|
| Synthetic grouped accuracy | 0.7148 |
| Synthetic grouped macro-F1 | 0.7072 |
| Adversarial recall | 0.8611 |
| Tampered recall | 0.8611 |
| QR-DN clean false-positive rate | 0.0000 |
| QR-DN median `p_structural` | 0.0396 |
| ECE | 0.0884 |
| ONNX P95 latency | 45.13 ms |

Status: **CANDIDATE ONLY**

Deployment gate failures:

- synthetic grouped macro-F1 0.7072 < 0.8500
- tampered recall 0.8611 < 0.9000
- synthetic test ECE 0.0884 > 0.0500
- exact app-crop gate: clean: 0 sessions; require 100
- exact app-crop gate: clean test: 0 sessions; require 20
- exact app-crop gate: adversarial: 0 sessions; require 100
- exact app-crop gate: adversarial test: 0 sessions; require 20
- exact app-crop gate: tampered: 0 sessions; require 100
- exact app-crop gate: tampered test: 0 sessions; require 20
