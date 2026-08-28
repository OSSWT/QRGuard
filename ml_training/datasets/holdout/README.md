# Independent and licence-quarantined holdouts

This folder is deliberately outside both training branches. Data here may be used
only for the purpose recorded in its manifest and preparation audit.

## Dynamsoft acquisition set

- Source files acquired: 73 (90,378,510 bytes), with Git blob hashes verified.
- Prepared annotated challenging-image QR crops: 232.
- Prepared video QR crops: 1.
- Training use: prohibited because the acquired repository has no repository-wide
  licence and no QRGuard clean/adversarial/tampered ground truth.
- Class performance metrics: prohibited for the same reason.
- Permitted result: acquisition/cropping robustness inspection only.

The very low automatic video-crop yield is itself useful evidence: the current
single-frame OpenCV rectifier is not robust to the damaged and reflective videos.
It must not be presented as a Structural classifier failure because most frames did
not reach the classifier. See `processed/dynamsoft_qr/preparation_audit.json` and
`processed/dynamsoft_qr/manifest.csv` for the exact record.
