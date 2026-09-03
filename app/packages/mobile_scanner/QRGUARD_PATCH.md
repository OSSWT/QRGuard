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
