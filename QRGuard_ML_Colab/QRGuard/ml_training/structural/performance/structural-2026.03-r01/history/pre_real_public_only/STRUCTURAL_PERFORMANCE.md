# Structural Training performance

Architecture: ImageNet-pretrained ResNet-18, 3-class fine-tuning
Synthetic grouped test identities: 180
QR-DN external clean identities: 25

| Metric | Result |
|---|---:|
| Synthetic grouped accuracy | 0.9426 |
| Synthetic grouped macro-F1 | 0.9435 |
| Adversarial recall | 0.9111 |
| Tampered recall | 0.9278 |
| QR-DN clean false-positive rate | 0.0000 |
| QR-DN median `p_structural` | 0.0022 |
| Controlled nuisance conditions evaluated | 10 |
| Worst controlled clean FPR | 0.0526 (perspective) |
| Exact app-camera test frames | 0 |
| Exact app-camera clean FPR | not evaluated |
| Exact app-camera adversarial recall | not evaluated |
| Exact app-camera tampered recall | not evaluated |
| Exact app-gallery clean FPR | not evaluated |
| Exported source-neutral camera clean FPR | not evaluated |
| Exported quality abstention rate | None |
| Paired Gallery/Camera verdict agreement | not evaluated |
| ECE | 0.0194 |
| ONNX P95 latency | 39.88 ms |

Status: **CANDIDATE ONLY**

Deployment gate failures:

- exact app-crop gate: clean: 0 camera sessions; require 100
- exact app-crop gate: clean: 0 camera test groups; require 20
- exact app-crop gate: clean: 0 paired test groups; require 20
- exact app-crop gate: clean/defocus_blur: 0 camera sessions; require 5
- exact app-crop gate: clean/far_distance: 0 camera sessions; require 5
- exact app-crop gate: clean/glare: 0 camera sessions; require 5
- exact app-crop gate: clean/motion_blur: 0 camera sessions; require 5
- exact app-crop gate: clean/normal: 0 camera sessions; require 5
- exact app-crop gate: clean/overexposure: 0 camera sessions; require 5
- exact app-crop gate: clean/perspective: 0 camera sessions; require 5
- exact app-crop gate: clean/screen_moire_or_compression: 0 camera sessions; require 5
- exact app-crop gate: clean/shadow: 0 camera sessions; require 5
- exact app-crop gate: clean/underexposure: 0 camera sessions; require 5
- exact app-crop gate: adversarial: 0 camera sessions; require 100
- exact app-crop gate: adversarial: 0 camera test groups; require 20
- exact app-crop gate: adversarial: 0 paired test groups; require 20
- exact app-crop gate: adversarial/defocus_blur: 0 camera sessions; require 5
- exact app-crop gate: adversarial/far_distance: 0 camera sessions; require 5
- exact app-crop gate: adversarial/glare: 0 camera sessions; require 5
- exact app-crop gate: adversarial/motion_blur: 0 camera sessions; require 5
- exact app-crop gate: adversarial/normal: 0 camera sessions; require 5
- exact app-crop gate: adversarial/overexposure: 0 camera sessions; require 5
- exact app-crop gate: adversarial/perspective: 0 camera sessions; require 5
- exact app-crop gate: adversarial/screen_moire_or_compression: 0 camera sessions; require 5
- exact app-crop gate: adversarial/shadow: 0 camera sessions; require 5
- exact app-crop gate: adversarial/underexposure: 0 camera sessions; require 5
- exact app-crop gate: tampered: 0 camera sessions; require 100
- exact app-crop gate: tampered: 0 camera test groups; require 20
- exact app-crop gate: tampered: 0 paired test groups; require 20
- exact app-crop gate: tampered/defocus_blur: 0 camera sessions; require 5
- exact app-crop gate: tampered/far_distance: 0 camera sessions; require 5
- exact app-crop gate: tampered/glare: 0 camera sessions; require 5
- exact app-crop gate: tampered/motion_blur: 0 camera sessions; require 5
- exact app-crop gate: tampered/normal: 0 camera sessions; require 5
- exact app-crop gate: tampered/overexposure: 0 camera sessions; require 5
- exact app-crop gate: tampered/perspective: 0 camera sessions; require 5
- exact app-crop gate: tampered/screen_moire_or_compression: 0 camera sessions; require 5
- exact app-crop gate: tampered/shadow: 0 camera sessions; require 5
- exact app-crop gate: tampered/underexposure: 0 camera sessions; require 5
