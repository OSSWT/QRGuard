# Attendance QR policy — 1.2.0+8013

Normal hi-hive attendance QRs can return Safe after their decoded content and
image pass a deterministic structural design check. Matching `Q01:*:` alone
does not grant Safe. The previous unconditional Warning/26 override is removed.

## Evidence and scope

The user-supplied UTAR sample decoded as an attendance token with a 61-module
grid (version 11), high error correction and mask 7. The deployed r07 CNN scored
its rectified crop as tampered (raw structural score 0.9994465). Re-encoding the
payload showed zero differing modules outside the central logo region.

The `attendance_grid_v1` check requires:

- A complete, untruncated attendance envelope and an independently decoded image
  containing exactly the same payload.
- Usable image quality and at least five observed pixels per QR module.
- Both format strings agreeing exactly on error correction and mask.
- Exact module agreement outside the central 30% of the symbol side, rounded
  outwards to module boundaries. Any module disagreement outside rejects Safe.
- For a logo allowance, high error correction, a coloured central graphic and
  no substantial colour overlay outside the central region.
- Every selected camera image passing. Existing insufficient-quality/frame and
  uncertain-model abstentions remain in effect. An adversarial aggregate class
  never receives this allowance. A tampered class requires a central logo in
  every checked image; an unexplained tampered prediction is not cleared.

The effective structural signal is zero after this deterministic check; it is
not a new CNN probability. `p_structural_raw` and `structural_raw_type` retain the
original model evidence. `structural_method` records which check cleared the
image, and the app and privacy-safe history display this distinction.

An unsupported encoding, failed decode, mismatched payload, unclear image or
unverified design does not pass this check. Confirmed manipulation can remain
Blocked; an otherwise Safe result without the required attendance evidence is
raised to Warning. Non-attendance QR policies are unchanged.

## Limits

This check recognizes an allowed central graphic; it does not authenticate the
UTAR logo, issuer, token signature, expiry, class or attendance submission.
hi-hive must validate the original token in its official app. It cannot detect
all pixel-level attacks that leave module values unchanged. Conservative
matching can still request another scan under difficult camera conditions.

No model was retrained or formally promoted. The CNN, Semantic and Fusion
artifacts remain unchanged. The submitted photo/token stays outside Git and is
not added to training data or the independent research holdout.

## Verification

- Backend: 489 passed, 3 conditional skips; Flutter: 105 passed; analyzer clean.
- Web and signed Android builds completed for `1.2.0+8013`.
- APK: 73,462,225 bytes, SHA-256
  `df0810d0d9be018b41f15ce02e2c2be9856772bcd6441df24dd16e0961c62ce9`.
- Package `com.osswt.qrguard`, version code 8013, existing signing certificate
  `ce47b65dab21523731dfd76a414068ad95dcce3e1ee02a54e80b04552191c1ec`.

`backend/tests/test_attendance_grid.py` covers synthetic independent attendance
identities, masks, rotation, brightness, perspective, peripheral module changes,
colour overlays, oversized logos, mismatched content, missing/small images,
mixed camera payloads, adversarial evidence and actual multipart API requests.
Flutter tests check Safe text, method disclosure, original CNN evidence and
privacy-safe history reconstruction.

The original user photo returns HTTP 200, Safe, risk 1 through Gallery and
three distinct brightness-varied Camera simulation frames using the production
unified-model configuration. This is image replay, not a physical phone camera
test. No phone was connected during verification.
