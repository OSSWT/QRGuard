# Attendance QR policy

## 8014 candidate — physical acceptance pending

The 8013 physical-phone follow-up exposed two failures: 61-module crops reported
3.8 pixels/module, and logo-sensitive CNN results became Blocked whenever the
strict grid check abstained. The 8013 image replays below were not physical
camera acceptance and did not establish live-camera reliability.

The 8014 candidate separates positive image/payload mismatch from inconclusive
grid, format, colour and decoding checks. Inconclusive attendance design checks
now abstain to Rescan with no effective structural score; raw CNN scores/classes
are retained. Exact Safe checks remain strict pending actual camera evidence.
An adversarial aggregate prediction still retains its existing risk treatment.

Camera acquisition requests 1920x1080 (the actual device stream may differ).
For attendance byte payloads the client estimates minimum crop size from QR H
capacity; the 134-byte example requires 397 pixels including the quiet zone.
The scanner uses the shortest detected edge and frame-size ceiling, and the
cropper enforces the same estimate. Larger issuer-selected versions may still
need a backend Rescan. This estimate never creates detail by upsampling.

Each checked frame reports its failure reason, crop dimensions, measured module
scale and outer-grid mismatch count where available. Details and private local
capture metadata retain these checks. The UI says Rescan needed for inconclusive
image evidence and no longer labels attendance hand-off as a URL override.

USB validation uses a separate `com.osswt.qrguard.capture` debug build; production
8013 remains unchanged until acceptance:

```powershell
cd app
flutter build apk --debug --no-pub --dart-define=QRGUARD_BACKEND_URL=http://127.0.0.1:8014
cd ..
.\scripts\dev\Start-AttendanceCameraCheck.ps1
```

Connect and authorize one USB-debugging phone. The helper installs without
clearing app data, forwards port 8014, and runs the candidate backend locally.
If a previous Capture installation has a saved backend URL, select
`http://127.0.0.1:8014` in its backend settings. QR crops saved to the ignored
`.tmp/attendance-camera-8014` directory can reveal the attendance token by
decoding; keep them private and do not commit them. Stop the server after testing.

Acceptance requires reproducing the user's normal camera scans, examining the
exact failed frames, validating any further sampling changes against attacks,
and repeating normal scans across distance and angle before a production release.

Candidate verification: 492 backend tests passed (3 conditional skips), 110
Flutter tests passed, Flutter analysis reported no issues, and the added capture
metadata passed the API regression. Original-photo Gallery replay remains Safe/1.
The USB candidate was built and its package/version inspected:
`com.osswt.qrguard.capture`, version code 8014. APK SHA-256:
`d3bc93faa75666134ae328f312838c8a72b18482b41df7897d1606f8893e5564`.
No phone was connected and physical-camera acceptance has not been completed.

## 8013 deployed baseline and historical verification

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

## Production release and cleanup

Render serves deployment commit
`a34a0436a3385bbdaa6fc19fbf02479ea2033813`. Both services report live, the web
version endpoint reports build 8013, and the hosted APK hash matches the signed
local artifact. Replaying the original photo against the deployed API returns
Safe / 1 for Gallery and the three-frame Camera simulation.
The post-deployment 42-case regression completed at 2026-09-07 10:26:51 UTC:
42/42 intended Gallery outcomes, 42/42 intended Camera-simulation outcomes,
and 84/84 HTTP 200 responses. Dataset baseline files were not rewritten.

The source workspace retains code, tests and this policy record. The deployable
web bundle and signed APK live under the existing deployment worktree. Four
temporary test directories, the duplicate staging bundle and seven obsolete
debug APKs were removed, reclaiming 774,791,792 bytes. These generated outputs
can be rebuilt; datasets, trained models and research evidence were retained.
