# Generated QR code datasets

This folder records QR images created by QRGuard rather than downloaded from an
external dataset. The actual image trees remain Git-ignored; their paths,
counts, roles, source manifests and deterministic tree hashes are recorded in
`registry.json`.

The registry records the active generated sets:

- QR references created for the exact-app Gallery/Camera capture campaign;
- train/validation Gallery references with locked-test references excluded;
- the post-training QR scan-card demo pack;
- active backend/Flutter regression fixtures; and
- active manual Gallery scanning QA cards.

Regenerable legacy image caches are deliberately excluded from this registry
and from the repository. Current training inputs are catalogued separately in
[`../DATASET_CATALOG.md`](../DATASET_CATALOG.md).

Regenerate the inventory from the repository root:

```powershell
.venv\Scripts\python.exe scripts\inventory_generated_qr_codes.py
```

`qr_codes_demo/` is intentionally separate. Its cases are generated after the
production model lock and are always `demo_only`; they must never be added to a
training or threshold-calibration split.
