# M5 Structural coverage development pack

Status: ready for physical development capture; model retraining has not started.

This pack addresses the coverage hole exposed by SEM-11. The previous exact-app
holdout was almost entirely Version 8 and contained no mask 0 examples. The new
development set crosses 16 pristine QR identities with clean, adversarial and
tampered variants, producing 48 cases and 240 physical frames after capture.

## Locked coverage

- 16 cases per class: clean, adversarial and tampered.
- Five Version 3, five Version 5 and six Version 10 identities per class.
- Masks 0-7 occur exactly twice in every class.
- Payload lengths are 24, 40 and 112 UTF-8 bytes, covering the short, medium and
  long audit bins while respecting each fixed Version-H capacity.
- Twelve parent identities are assigned to train and four to validation. All
  three label variants of a parent stay in the same split.
- The pack is development-only and cannot be reused as the M8 blind holdout.

## Attack integrity

All 16 adversarial references preserve the exact QR payload and flip the locked
victim model in at least 3/6 EOT views. Fifteen use projected EOT-FGSM; the one
locally insensitive Version 3 identity uses projected iterative EOT-PGD under
the same epsilon ceiling. Fourteen attacks use epsilon 8/255, one uses 12/255
and one uses 24/255. QR function-safe or module-interior projections are recorded
per case in `MANIFEST.json`.

## Artifact verification

- Development ZIP: SHA-256
  `b86463c15926b0409e7d4542fa2d419e5a76a74bf077569c951bb320f0785335`.
- Diagnostic APK: SHA-256
  `dc13ee5275cdfc1151272633d4358ce79a6d29d5309a474183343003a0db06fe`.
- All 116 ZIP entries match the 116 generated disk files byte for byte.
- All manifest reference/card hashes pass and the app plan equals the pack plan.
- The APK embeds that exact plan and verifies under Android APK Signature Scheme
  v2 with the Android debug signer.

No production model, threshold or APK was promoted by this milestone.
