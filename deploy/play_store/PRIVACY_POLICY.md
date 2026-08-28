# QRGuard Privacy Policy

Effective date: 24 August 2026

QRGuard is developed by OSSWT as a QR-code safety and research application.
Questions about this policy may be sent to `szeshou03@gmail.com`.

## Data processed during a scan

When you request analysis, QRGuard sends the decoded QR payload and, when image
analysis is available, a cropped QR image to the QRGuard analysis server. This data
is used only to calculate structural, semantic, and combined risk results.

The production server does not persist uploaded QR images or raw payloads by
default. Images are decoded and analysed in memory. Application logs contain
technical status, scores, verdicts, and timing information, but deliberately omit
the raw payload and destination domain.

## Data stored on the device

If scan history is enabled, QRGuard stores up to 200 result summaries locally on
the device. It stores a SHA-256 hash of the payload, the registered domain when
applicable, risk signals, verdict, score, and time. It does not store the raw QR
image, full URL, path, query string, or raw payload. Users can disable or clear
history from the application.

## Optional deep analysis

Deep analysis is initiated only when the user requests it. If the server operator
enables a third-party language-model provider, the relevant link evidence may be
sent to that provider to produce a second opinion. The initial internal deployment
keeps this provider disabled. QRGuard does not sell personal data or use scan data
for advertising.

## Permissions

QRGuard requests camera permission to scan QR codes and network access to contact
the analysis service. Gallery selection is initiated by the user through the
operating system picker.

## Retention and deletion

Server-side scan inputs are not retained under the default production
configuration. Local history remains until it exceeds 200 records, the user clears
it, or the application is removed. Infrastructure security logs are retained only
for service operation and abuse investigation under the hosting provider's log
retention configuration.

## Children

QRGuard is not directed to children and does not knowingly create profiles of
children.

## Security and limitations

Data is transmitted to the production service using HTTPS. QRGuard is a decision
support tool and cannot guarantee that a QR code or destination is safe.

## Changes

Material changes will be reflected by updating this policy and its effective date.
