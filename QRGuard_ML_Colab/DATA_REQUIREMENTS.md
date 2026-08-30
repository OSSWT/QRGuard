# Data requirements and Drive layout

```text
MyDrive/
  QRGuard_ML_Colab.zip
  QRGuard_ML_Data/
    structural/
      QR-DN1.0.zip
      qr_codes_in_surfaces.zip
      runtime_captures/          # paired Gallery/Camera exact app crops
  QRGuard_ML/
    cache/                       # reusable prepared Structural data
    runs/                        # checkpoints, artifacts and performance
```

Structural archive hashes are verified against
`QRGuard/ml_training/datasets/download_verification.json`. Runtime capture
folders must follow `CAPTURE_GUIDE_V3.md`: 1–5 distinct exact PNG crops, one
authoritative frame, Gallery/Camera pair metadata, measured quality condition,
and anonymised identifiers. Raw QR payloads are never required or stored.
