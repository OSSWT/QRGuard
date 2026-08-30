# QRGuard Capture APK — Wi-Fi installation

This debug build is only for the controlled Structural v3 capture campaign. It
installs beside the signed production app as **QRGuard Capture** with application
ID `com.osswt.qrguard.capture`. It does not replace or erase the production app,
history or settings.

If the current network is not the trusted Xiaomi hotspot/private LAN, do not
start the HTTP backend. Build the network-free variant with
`--dart-define=QRGUARD_OFFLINE_CAPTURE=true` and follow
`../../OFFLINE_CAPTURE_AND_IMPORT.md` instead.

## Download from the phone

Open Google Drive and browse to:

```text
My Drive/QRGuard_APK/structural-v3-real-2026.03-r01/
```

Install `QRGuard-Capture-arm64-v8a-1.1.2.apk` first. It is the recommended
90.7 MB build for modern Android phones. If Android reports an ABI/package parse
error, use the 170.8 MB `QRGuard-Capture-universal-1.1.2.apk` fallback.

Android may ask you to allow “Install unknown apps” for Google Drive or the file
manager. Grant it only for this installation and disable it again afterwards.
The exact SHA-256 values are recorded in `APK_MANIFEST.json`.

## Start the local capture backend

From the repository root on the computer:

```powershell
$env:QRGUARD_DUMP_SCANS = Join-Path $PWD "data\runtime_captures"
$env:QRGUARD_CAPTURE_CASE_FILE = "_active_case.json"
$env:QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS = Join-Path $PWD `
  "ml_training\structural\runs\structural-2026.03-r01\artifacts"

& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app `
  --app-dir backend `
  --host 0.0.0.0 `
  --port 8001
```

The phone and computer must use the same trusted private Wi-Fi or phone hotspot.
Allow Python/backend access only on Windows **Private networks**. Do not use this
debug HTTP capture mode on an open/public network.

## Configure the phone

At package creation time the computer Wi-Fi address was:

```text
http://10.1.87.26:8001
```

This address can change. Run `ipconfig` and use the current Wi-Fi IPv4 address.
In QRGuard Capture, open Settings → Backend Connection, enter the address and
tap the connection test.

The current `10.1.87.x` network may use client isolation. If the phone cannot
reach the backend, use a trusted home router or phone hotspot and update the IP.

## First pilot only

Do not begin all 450 cases immediately. First activate `cln-normal-01`, perform
one Gallery scan and one Camera scan of the same QR, then audit the two saved
sessions. Scale the campaign only after metadata, crop and pair validation pass.

This APK is debuggable and permits private-LAN cleartext HTTP. It must never be
uploaded to a production app store or reported as a release build.
