# Generated QR code datasets

This folder records QR images created by QRGuard rather than downloaded from an
external dataset. The actual image trees remain Git-ignored; their paths,
counts, roles, source manifests and deterministic tree hashes are recorded in
`registry.json`.

The registry separates:

- legacy benign/malicious QR images that are not part of the current run;
- procedural Structural images governed by the current run manifest;
- QR references created for the exact-app Gallery/Camera capture campaign;
- train/validation Gallery references with locked-test references excluded;
- superseded manual API/Gallery demonstration cards.

Regenerate the inventory from the repository root:

```powershell
.venv\Scripts\python.exe scripts\inventory_generated_qr_codes.py
```

`qr_codes_demo/` is intentionally separate. Its cases are generated after the
production model lock and are always `demo_only`; they must never be added to a
training or threshold-calibration split.
