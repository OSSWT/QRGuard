# SEM-11 physical capture hand-off

## Test pack

- Path: `90_Rebuildable_Caches/SEM11_Root_Cause_Test_Pack_2026-09-r01.zip`
- Bytes: 364,154
- SHA-256: `721B1412DFDF3CB7F16337D749132F614F259644743E6FCB59095942A0678F95`
- Cases: 12 clean Plain Text controls.
- Screening: screen 80%, three five-frame sessions per case (36 sessions).

The pack includes the case cards, control metadata, the digital local results,
screening order and the exact diagnostic capture plan.

## Android collector

- Path: `90_Rebuildable_Caches/qrguard-sem11-root-cause-capture-1.1.4+8011-debug.apk`
- Bytes: 171,105,715
- SHA-256: `444F0E58081DD62C5E73323796BB5DCB6D7D1426129899A4F4CFF8C88EF5FE34`
- Application ID: `com.osswt.qrguard.capture`; installs beside production.
- Plan asset: `assets/capture/sem11_root_cause_capture_plan.json`.
- Local database: campaign-specific and isolated from the older repeatability
  capture campaign.

## Evidence contract

Each session exports five actual rectified PNG crops plus geometry, timestamps,
crop hashes, payload hash, QR Version, mask, module count, dark-module ratio and
the fixed screen condition.  Raw payload text is not stored.

The app verifies the decoded payload hash.  Several mask/version controls share
the same payload, so their exact visual case identity additionally depends on the
operator displaying the selected card; this limitation is explicitly recorded
in every session rather than represented as automatic mask verification.

## Verification before hand-off

- Python root-cause and branch-audit tests: 4 passed.
- Ruff: clean.
- Flutter diagnostic-plan tests: 3 passed.
- Full Flutter suite after the M3 plan integration: 87 passed.
- Flutter analyzer: no issues.
- Debug APK build: passed.

M4 acquisition-policy thresholds are deliberately not changed before these
physical crops are collected.  That avoids tuning frame diversity or Rescan
behaviour from screenshots instead of the pixels seen by the deployed model.
