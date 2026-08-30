# Structural v3 offline Android capture and desktop import

Use this path when the capture phone and workstation cannot safely share a
trusted private network. It preserves the same exact QR crop produced by
QRGuard's Android camera/gallery pipeline, but postpones model analysis until
the ZIP reaches the workstation.

The production app is unchanged. Offline mode exists only when the side-by-side
debug APK is built with `QRGUARD_OFFLINE_CAPTURE=true`.

## Evidence contract

- The Android app decodes exactly one QR and runs the existing `qr_cropper`.
- It stores the crop, case fields and SHA-256 of the decoded payload.
- It never stores the raw payload or opens the decoded destination.
- Gallery and Live Camera for one case must have the same payload hash.
- The scoped APK pre-fills provenance from the verified adversarial and
  documented tampered reference; missing or invalid provenance remains blocked.
- At most 40 unexported sessions or 96 MB of crop data can queue at once,
  whichever limit is reached first. This can be 20 complete pairs or a
  camera-first batch of up to 40 Camera sessions.
- Export writes a ZIP to `Downloads/QRGuard`; rows remain in the app after export.
- The workstation treats the ZIP as untrusted, validates all paths/fields/hashes,
  forces the canonical `structural-2026.03-r01` candidate, and only then writes
  canonical runtime-capture sessions.

An ordinary Xiaomi Camera photograph imported through Gallery is still Gallery
evidence. Only a crop produced by the QRGuard Live Camera flow is labelled
`camera`.

## Refresh the bundled campaign plan

Run this whenever canonical capture progress or the desired first case changes:

```powershell
& ".\.venv\Scripts\python.exe" scripts\build_offline_capture_plan.py `
  --selection ml_training\structural\campaigns\structural-v3-real-2026.03-r01\scope_50x3_selection.json `
  --initial-case cln-overexp-02
```

The generated Flutter asset contains the locked 150-case scope, including the
two already completed pairs, group hashes, prepared provenance, and capture
instructions. It contains no QR payloads and no raw pair/physical tokens.

## Build the side-by-side offline capture APK

```powershell
Set-Location app
& "C:\src\flutter\bin\flutter.bat" build apk --debug --split-per-abi `
  --dart-define=QRGUARD_OFFLINE_CAPTURE=true
```

Install the arm64 APK from
`build\app\outputs\flutter-apk\app-arm64-v8a-debug.apk`. Debug builds use
application ID `com.osswt.qrguard.capture` and label `QRGuard Capture`, so they
do not replace the signed production app.

## Capture a small batch

1. Open `QRGuard Capture`; confirm the displayed campaign and case ID.
2. Use the exact numbered reference assigned to that case.
3. Apply the scheduled physical acquisition condition only to Live Camera.
4. Tap **Capture Camera**, scan the reference, review, then save it.
5. For a locked test case, add the unchanged numbered PNG through Gallery.
6. The app advances to the next Camera case after a Camera save.
7. Export before the queue reaches 40 sessions.

For the single-phone camera-first workflow, Camera evidence may be collected
and exported before Gallery. After a Camera save the app advances to the next
case missing Camera evidence. Add the unchanged numbered Gallery reference only
for the locked test cases first; the desktop importer accepts camera-only ZIPs,
while the strict paired-test gate still requires the selected Gallery partners.

The preview can be discarded before saving. A stored local source can also be
discarded explicitly; an already exported ZIP is not deleted by that action.

## Validate on the workstation

Copy the ZIP from the phone to a local path. Validation is read-only and is the
default:

```powershell
& ".\.venv\Scripts\python.exe" -m `
  ml_training.structural.src.import_offline_capture `
  "C:\path\to\QRGuard_Offline_structural-v3-real-2026.03-r01_....zip"
```

The importer rejects path traversal, extra files, duplicate case/source rows,
oversized data, changed crop/metadata hashes, raw payload fields, campaign or
group mismatches, invalid provenance and conflicts with existing canonical
sessions.

## Commit the validated batch

Only after the validation summary is correct:

```powershell
& ".\.venv\Scripts\python.exe" -m `
  ml_training.structural.src.import_offline_capture `
  "C:\path\to\QRGuard_Offline_structural-v3-real-2026.03-r01_....zip" `
  --commit
```

`--commit` runs local analysis with the exact v3 candidate, writes one canonical
`crop_00.png` and `metadata.json` per session, writes an import receipt, then
runs the campaign audit. It refuses an environment variable that points to a
different Structural artifact. It never deletes the input ZIP.

OpenCV independently verifies the payload hash whenever the exported crop is
decodable. A deliberately degraded crop can be valid Structural evidence even
when the desktop decoder abstains; in that case metadata records
`desktop_payload_decode_verified: false` and retains only the on-device ML Kit
payload hash.

## After every batch

Review `data/runtime_captures/campaign_progress.json` and
`data/runtime_captures/audit_v3.json` before collecting more. Do not promote a
model, count duplicate views as independent cases, or delete the ZIP until the
canonical audit is accepted.
