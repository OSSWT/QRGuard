# Structural v3 real 100x3 results — 2026-08-31

Version: **`structural-2026.03-r01` — latest candidate**
Status: **gates passed; deployed and remote-smoke verified**

## What changed

The model was retrained after the audited exact-app capture campaign. Training
uses one source-neutral ResNet-18 artifact for Gallery and Live Camera, with
measured-pixel quality handling. Prepared Gallery references were added only to
train/validation; the 60 Camera/Gallery pairs remained locked for final testing.

The earlier pre-real and camera-only failed runs remain under history folders as
negative evidence. They are not the active candidate.

## Dataset and split contract

- 300 accepted Camera sessions: 100 clean, 100 adversarial, 100 tampered.
- 60 locked test sessions per source: 20 per class.
- 60 locked paired Gallery/Camera groups.
- 361 total authoritative sessions and zero group leakage.
- Training manifest: 11,130 rows; SHA-256
  `e4aad0f2e378b9e35565493e297fd0a0ea862dff710ce5f78528008a64a79d45`.

## Model-only and export results

| Metric | Result |
|---|---:|
| Synthetic grouped accuracy | 0.9111 |
| Synthetic grouped macro-F1 | 0.9095 |
| Synthetic adversarial recall | 0.9889 |
| Synthetic tampered recall | 0.9500 |
| QR-DN external clean false-positive rate | 0.0000 |
| Binary expected calibration error | 0.0278 |
| ONNX/PyTorch maximum probability difference | 0.00000289 |
| ONNX P95 local CPU latency | 44.09 ms |

## Locked exact-app deployment holdout

| Source | Clean FPR | Adversarial recall | Tampered recall |
|---|---:|---:|---:|
| Camera | 0.0000 | 0.9500 | 1.0000 |
| Gallery | 0.0000 | 1.0000 | 1.0000 |

The exported source-neutral model produced identical class/verdict outcomes for
59 of 60 paired groups (0.9833), exceeding the 0.95 gate. The remaining Camera
adversarial miss is retained in the prediction evidence.

## Artifact identity

- ONNX bytes: 44,702,737.
- ONNX SHA-256:
  `3529df95acaba3f5fe29f7369670de5c0c8c06d60f90e8a2e1959584967c5ad4`.
- Temperature: 0.4637561909457002.
- Performance bundle:
  `ml_training/structural/performance/structural-2026.03-r01/`.

The artifact was subsequently copied into the local production path and passed
the same 120-row evaluator plus real HTTP smoke. GitHub/Render deployment is a
separate remaining step.
