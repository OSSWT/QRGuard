# QRGuard r02 checkpoint — 2026-09-02

## State

Work is intentionally paused at a recoverable boundary. No Python, Dart, or
Flutter command is still running. The repository remains deliberately dirty;
all existing user work and all r01/r02 milestone changes are preserved.

The deployed Structural model is still `structural-2026.03-r01`. The r02
training recipe and Colab bundle are candidates only; no r02 model has been
trained, promoted, or represented as production-ready.

## Completed at this checkpoint

- Camera capture quality gate with exposure, contrast, blur, and small-input
  telemetry. Unusable evidence can request a rescan but cannot produce Safe.
- Five-frame live collection, quality ranking, exposure diversity, and exactly
  three usable crops for backend consensus.
- QR Version-aware module-scale boundary: at least 5 pixels/module when the
  module grid is observable, with a conservative 256 px fallback.
- Vendored `mobile_scanner` CameraX patch: QR-centred AF/AE/AWB metering and
  exposure compensation state/set APIs.
- One bounded EV adjustment per stable QR sequence; pre-adjustment frames are
  discarded and evidence is recollected.
- Diagnostic capture parity: first-frame AF/AE/AWB, bounded EV adjustment,
  post-adjustment-only evidence, quality rejection, and per-frame quality/EV/
  pixels-per-module metadata in exported ZIPs.
- Verified physical r02 development import: 80 clean frames plus 50 frames from
  10 attacks that survived physical recapture. The other 110 attack frames are
  quarantined rather than mislabeled as useful attacks.
- Exposure-invariant r02 recipe: bounded EV/contrast/gamma views, symmetric KL
  consistency loss, exposure sweep metrics, and promotion gates.
- Compact screen-only validation pack: SEM-05, SEM-11, clean over/underexposure,
  adversarial, tampered, Version 10, and Version 14 across 80% baseline, 100%
  high-brightness, and 100% low-brightness. No printing and no zoom above 100%.

## Built artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `90_Rebuildable_Caches/QRGuard_CaptureQuality_Exposure_ModuleScale_1.1.4+8011_2026-09-02_r02-final.apk` | 189,505,154 | `4C98073DD46A546C83BDF4811B025824E3F7A99C451D506F0B7DE4B57CB2215F` |
| `90_Rebuildable_Caches/QRGuard_Diagnostic_Acquisition_Validation_1.1.4+8011_2026-09-r02.apk` | 189,506,206 | `6F4FF4EA70ED5C425985F78FACDF6F71D9132B2252C0C6C8D0EAA0CE46698210` |
| `90_Rebuildable_Caches/Acquisition_Validation_2026-09-r02.zip` | 1,541,643 | `F184662F28F184295E43852B99F7817DE42AA14DB6C9E7CA5C22A24D7D0AA086` |
| `01_Main_Repository/dist/QRGuard_ML_Colab.zip` | 122,127,182 | `7C91E40843BD99DB404D0C966EC62021E9A76A57EDF5BF68FFA38B17900CD61D` |

## Verification state

- Flutter static analysis: no issues.
- Flutter full suite after the diagnostic/plan changes: **100 passed**.
- New acquisition/exposure/module targeted backend suite: **15 passed**.
- Final isolated backend suite including the acquisition ZIP auditor:
  **419 passed, 1 skipped, 0 failed**.
- Colab package contract suite: **10 passed**.
- Ruff on new/touched r02 acquisition files: passed.
- `git diff --check`: passed; only Windows LF-to-CRLF notices were printed.
- Both final APK builds: succeeded. Flutter printed only a future Kotlin plugin
  migration warning for the vendored `mobile_scanner` package.

The final backend rerun completed outside the Windows sandbox after isolating
pytest's temporary directory. The earlier ACL interruption produced no recorded
assertion failure and is superseded by the 419-pass result above.

## Exact resume point

1. User installs the diagnostic APK, opens the validation card ZIP on another
   screen, completes 24 automatic sessions, and returns the exported diagnostic
   ZIP. The app enforces the five-frame quality policy automatically.
2. Analyse that ZIP against the r01 deployment policy and the r02 acquisition
   gates. Do not promote on this development pack.
3. Run the prepared r02 Colab training bundle on a GPU, then evaluate a genuinely
   fresh device/display/session blind holdout before any r02 promotion.

Resume phrase: **“继续 R02 checkpoint”**.
