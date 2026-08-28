# QRGuard Google Play listing

## App identity

- App name: QRGuard
- Application ID: `com.osswt.qrguard`
- Category: Tools
- Default language: English (United States)
- Contact email: `szeshou03@gmail.com`

## Short description

Scan QR codes and assess link, payload, and image-manipulation risk.

## Full description

QRGuard helps you inspect a QR code before acting on it. It combines visual QR
integrity analysis with URL and payload checks, then presents a calibrated Safe,
Warning, or Blocked result with understandable reasons.

Use the live camera or select an image from your gallery. QRGuard can identify
suspicious destination patterns, risky payload types, and signs that the QR image
may have been altered. DuitNow, Wi-Fi, URL, and plain-text payloads are handled
according to their own safety rules.

QRGuard is a research-based safety aid. Its result is not a guarantee that a QR
code, website, payment request, or network is safe. Always verify recipients,
amounts, domains, and sensitive requests before continuing.

Privacy is built in: scan history stores a payload hash and non-identifying result
summary on the device, not the raw QR image or complete scanned URL.

## Internal testing release notes

Initial QRGuard 1.0 internal release:

- Live-camera and gallery QR scanning
- Structural image-integrity analysis
- Semantic URL and payload analysis
- Calibrated Safe, Warning, and Blocked decisions
- Privacy-preserving local history
- Optional user-initiated deep analysis when configured

This release is restricted to internal testing while exact app-camera acceptance
data is collected for the Structural deployment gate.
