# Existing measured Structural and Semantic performance

These are the checked-in `2026.02` reference results, not invented notebook
output. Run the two Colab notebooks to reproduce fresh artifacts in your own
Google Drive.

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

Semantic `semantic-2026.02` passed its recorded gates. Structural
`structural-2026.02` passed its research gates but is **candidate only**, because
the recorded exact QRGuard app-camera audit has zero labelled sessions. The
Colab pipeline keeps that limitation explicit and cannot approve deployment
until the real-camera sample/session gates and class-specific performance gates
pass.
