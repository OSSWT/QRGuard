# Structural Training — QR-DN external clean holdout

Artifact: `structural_fp32.onnx`
Images: 2,250 across 25 identity-disjoint test QR codes
Real acquisition type: screen/camera capture followed by watermark extraction

| Metric | Result |
|---|---:|
| Clean false-positive rate (`p_structural >= 0.5`) | 0.8084 |
| Non-clean predicted-class rate | 0.7409 |
| Median `p_structural` | 0.7529 |
| P95 `p_structural` | 0.9803 |
| Maximum `p_structural` | 0.9995 |
| Inference P95 | 40.29 ms |

External clean gate: **FAILED**

This is genuine camera-derived evidence, but it is not an exact QRGuard app crop and
does not replace the strict live-app deployment gate.
