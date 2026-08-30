# Structural v3 real capture campaign status — 2026-08-30

Latest campaign: **`structural-v3-real-2026.03-r01`**
Status: **100x3 deployment count gate passed; canonical import complete**

## Prepared workload

| Item | Count |
|---|---:|
| Structural classes | 3 |
| Quality conditions per class | 10 |
| Accepted Camera cases per class/condition | 10 |
| Accepted independent Camera cases | 300 |
| Accepted Gallery sessions | 61 |
| Required paired test groups | 60 |
| Canonical accepted sessions | 361 |
| Rejected canonical sessions | 0 |

The finalized scope is balanced at 100 Camera cases per class and uses a
60/20/20 train/validation/test split per class. Every class/condition cell has
ten Camera cases. Severe cases remain quality-abstention evidence and do not
enter the normal three-class classifier training rows.

The strict canonical audit accepted 361 sessions with zero rejection and zero
split leakage: 100 Camera sessions per class, 20 Camera test groups per class,
20 paired test groups per class and ten Camera sessions in every
class/condition cell. The source-evidence quarantine contains 143 mismatched
sessions and is excluded from training-ready data.

## Safeguards implemented

- One hot-switch `_active_case.json` lets the backend change cases without a
  restart while capture dumping remains explicitly opt-in.
- Pair and physical tokens are hashed before metadata storage; raw payloads are
  never stored.
- A pair counts only if Gallery and Camera share the same scheduled case,
  Structural label, condition, severity, pair/physical hashes and payload hash.
- Blur, exposure, glare, distance, shadow, perspective and screen artefacts are
  always quality conditions, never attack labels by themselves.
- Adversarial activation requires a verified EOT/physical method and reference
  SHA-256.
- Tampered activation requires a documented manipulation method.
- Duplicate, mismatched, unplanned and incomplete sessions are reported rather
  than silently counted.

## Validation

- Campaign/API targeted regression: 72 passed.
- Campaign and Structural-v3 loader regression: 11 passed.
- Final Colab package contract: 6 passed.
- Complete backend regression: 343 passed.
- Complete Flutter regression: 72 passed; analyzer clean.
- Ruff checks for the new campaign/offline transport code passed.

## Pilot connection and capture validation

A Xiaomi 10T Pro hosted a private hotspot and connected successfully to the
local capture backend without USB/ADB. The capture-only APK reached the backend
at its hotspot address and `/health` confirmed that Gallery and Camera both use
`structural-2026.03-r01`.

Cases `cln-normal-01` and `cln-normal-02` each produced one Gallery and one
Camera session. Campaign audit accepted all four sessions as two complete pairs
with zero invalid or unplanned sessions. The v3 dataset preparer accepted four
authoritative frames, reported no split leakage and correctly kept the final
deployment gate closed.

## Wi-Fi capture APK prepared

The side-by-side `QRGuard Capture` debug APK has been built and uploaded to:

```text
My Drive/QRGuard_APK/structural-v3-real-2026.03-r01/
```

The recommended arm64 APK is 90,678,832 bytes with SHA-256
`61907BE234E8F547D1BE5605D01372E3407DC133819E0169261469FDBA7FA6FE`.
The Universal fallback is also retained. The package is
`com.osswt.qrguard.capture`, so it does not overwrite the production app.

## Offline capture APK prepared after restart

The same side-by-side package now has a network-free build mode. It queues the
exact QRGuard app crop and hashed campaign metadata on Android, exports no more
than 40 sessions or 96 MB per ZIP batch, and never stores the raw payload. The
desktop importer validates the archive before it can write canonical sessions
and forces the `structural-2026.03-r01` candidate for trusted analysis.

Final local arm64 APK: 108,993,883 bytes, SHA-256
`78889E88AD48805A1E1179DEF34119DF72667CFF6730F825848CB6333FFC1C89`.
It has not been uploaded or installed. See `OFFLINE_CAPTURE_AND_IMPORT.md`.

## Next ML action

No additional bulk capture is required. Train the fresh Structural candidate,
evaluate only the locked test split for deployment, and collect targeted add-on
data only if a named class/quality slice fails.

## First pilot completed

`cln-normal-01` was captured on device `xiaomi-10t-pro`, medium `screen`,
environment `indoor-controlled`. Its unique non-personal Gallery reference was
decoded locally and matched the locked payload hash. The PNG SHA-256 is
`F20A97D310FE68585E6C8122CDE28C52683A10CF4FA7288992297377BE08C2A5`.

The phone download copy is stored at:

```text
My Drive/QRGuard_Capture_Pilot/structural-v3-real-2026.03-r01/
  cln-normal-01/cln-normal-01-gallery-reference.png
```

The Gallery and Camera payload hashes matched. Both predictions were `clean` and
both final verdicts were `safe`. The Gallery Structural probability was
0.0050207 and the Camera probability was 0.0472048, demonstrating expected
confidence variation without a class flip.

Future generated references use a unique HTTPS URL on `example.com`. The first
pair remains valid Structural evidence, but its older plain token was normalised
by the app to a non-resolving HTTP URL and therefore should not be used as a
Semantic demonstration example.

`cln-normal-02` also completed with matching Gallery/Camera payload and pair
hashes. Both predictions were `clean` and `safe`; Structural probabilities were
0.0072806 for Gallery and 0.0129255 for Camera. The next active case is
`cln-overexp-02`, a clean/mild-overexposure screen pilot. Future reference
generation now refuses delivery unless OpenCV decodes the exact payload.

No model was promoted, pushed or deployed during campaign preparation.

## Scoped 50 x 3 camera-first hand-off

The original 50x3 hand-off is retained as historical collection provenance.
The finalized 100x3 scope and strict counts are recorded in
`campaigns/structural-v3-real-2026.03-r01/deployment_100x3_audit.json`.

Final arm64 capture APK: 108,995,289 bytes, SHA-256
`887B7E7B3377F54C7B89DE7A6677287A2DB2E2996F3F078098536ADD83AFD3FE`.

Final numbered reference ZIP: 5,473,156 bytes, SHA-256
`F49256416BA009C22230B38D82E660C6BA96297CD7E2C1E43D6C848EB4F1B20F`.
