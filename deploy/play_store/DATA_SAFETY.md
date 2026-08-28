# Google Play Data safety working sheet

Use this as the truthful basis for the Play Console form. Re-check every answer
against the deployed build before submission.

## Collection and sharing

- The app transmits user-provided QR payload text and cropped QR images to the
  QRGuard server to provide the scan-analysis feature.
- Data is encrypted in transit through the production HTTPS endpoint.
- Scan inputs are processed ephemerally and are not persisted by the application
  server under the production configuration.
- QRGuard does not sell data and contains no advertising or analytics SDK.
- The initial internal release does not configure the optional Gemini provider.

## Local-only data

- Privacy-preserving scan history is stored locally and can be disabled or deleted.
- The history contains a payload hash and result summary, not raw images or URLs.

## Permissions to declare

- Camera: core QR scanning functionality.
- Internet: server-side risk analysis.

## Play Console review flags

- Mark the app as a security/research decision-support tool, not a guarantee.
- Declare uploaded photos/images and user-provided payload content wherever the
  Play form treats ephemeral processing as collection.
- Link the hosted Privacy Policy from both Play Console and the app/store listing.
