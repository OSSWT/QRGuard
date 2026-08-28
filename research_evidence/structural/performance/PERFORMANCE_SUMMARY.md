# Structural performance summary

## Replacement candidate: `structural-2026.02`

| Metric | Result |
|---|---:|
| Grouped synthetic accuracy | 0.8907 |
| Grouped synthetic macro-F1 | 0.8892 |
| Clean precision / recall / F1 | 0.8765 / 0.7889 / 0.8304 |
| Adversarial precision / recall / F1 | 0.8872 / 0.9611 / 0.9227 |
| Tampered precision / recall / F1 | 0.9071 / 0.9222 / 0.9146 |
| Expected calibration error | 0.0126 |
| QR-DN external clean false-positive rate | 0.0000 |
| ONNX median / P95 latency | 42.18 ms / 44.63 ms |

Research gates passed, but this model remains **candidate only**. The exact
QRGuard app-crop gate has zero collected sessions for clean, adversarial, and
tampered classes. Each class requires at least 100 sessions, including at least 20
independent test groups, before final camera deployment approval.

## Current deployed routing context

- Gallery rollback model: `structural-run5` at
  `training/artifacts/structural/structural_fp32.onnx`.
- Live-camera provisional candidate: `structural-2026.02`, as recorded in
  `ml_training/deployment/model_registry.json`.
- The older gallery model produced QR-DN external clean FPR `0.8084`; this is why
  gallery and live-camera routing are explicitly separated.

Machine-readable metrics, figures, training history, and dataset composition are
stored in the adjacent `structural-2026.02/` snapshot. Canonical performance
evidence remains under `ml_training/structural/performance/`.
