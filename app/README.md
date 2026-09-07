# QRGuard mobile application

This directory contains the Flutter client for QRGuard `1.2.0+8014`. The
supported release targets are Android and Web.

The normal scan flow decodes a QR on-device, rectifies the detected QR region,
and sends the payload and image evidence to the FastAPI `/scan` endpoint.
Camera scans retain a bounded pool of observations and submit three distinct,
quality-ranked crops for temporal consensus. Gallery scans submit one image.
Incomplete image evidence fails closed and asks the user to scan again.

## Development

From this directory:

```powershell
flutter pub get
flutter analyze
flutter test
flutter run
```

Android emulator development uses `http://10.0.2.2:8001` by default. Web uses
`http://127.0.0.1:8001`. A release build must receive the production HTTPS API:

```powershell
flutter build web --release --dart-define=QRGUARD_BACKEND_URL=https://qrguard-api-osswt.onrender.com
flutter build apk --release --dart-define=QRGUARD_BACKEND_URL=https://qrguard-api-osswt.onrender.com
```

Android release builds require `android/key.properties` and the corresponding
keystore. Debug builds install as `com.osswt.qrguard.capture`; the signed release
uses `com.osswt.qrguard`.

## Privacy and special modes

Normal history stores at most 200 local summaries. It retains a SHA-256 payload
hash, registered domain and analysis signals, but never the raw image, full URL
or payload.

Diagnostic and offline capture screens are compile-time research modes. They are
disabled in ordinary production builds and must not be enabled when preparing a
public release.
