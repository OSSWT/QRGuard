# QRGuard mobile_scanner patch

This directory vendors the runtime portion of `mobile_scanner` 7.4.0 under its
BSD-3-Clause license. The upstream source and version remain recorded in
`pubspec.yaml` and `LICENSE`.

QRGuard changes are intentionally narrow:

- detected-QR focus points meter AF, AE and AWB together on Android;
- CameraX exposure-compensation capability, range and current index are exposed;
- a supported exposure-compensation index can be applied through the controller.

The API reports unsupported capability on non-Android platforms. QRGuard keeps
the upstream fallback behaviour there.

Preview-only Web capture patch (`QRGUARD_DIAGNOSTIC_PREVIEW=true`):

- Browser BarcodeDetector reads an immutable canvas, not the live video input.
- BarcodeDetector and ZXing-WASM return PNG bytes from their exact decoded canvas
  with matching dimensions. No second video snapshot is taken after decoding.
- Stale decode completions after stop/restart are dropped; image mirroring and
  barcode coordinates stay paired.
- A conservative native-pixel directional-detail gate rejects severe attendance
  motion streaks before emitting evidence. It is acquisition screening, not a
  safety verdict. Unsupported legacy ZXing-JS must not use a late snapshot as a
  fallback in the preview; supported auto readers are native and WASM.
- Non-preview builds retain upstream Web behavior; Android patches are unchanged.
