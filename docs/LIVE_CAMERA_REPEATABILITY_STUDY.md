# Live-camera structural repeatability study

## Purpose

This bounded diagnostic study measures whether QRGuard's rectified Structural
input is stable across consecutive live-camera frames and ordinary working
distances. It exists because one `STR-CLN-ANGLE` trial was Safe only at very
close range, while repeated `STR-ADV-NORMAL` trials alternated between Safe and
Blocked. Those observations must not be treated as a deployment-quality result
until the exact app crops are compared frame by frame.

The collector does not retrain the model and does not change the production
verdict. It gathers the evidence needed to decide whether correction belongs in
crop geometry, image-quality abstention, temporal consensus, model calibration,
or a combination of these layers.

## Locked matrix

| Case | Ground truth | Distances | Repeats | Frames per repeat |
|---|---|---:|---:|---:|
| `STR-CLN-ANGLE` | clean | near, medium, far | 5 each | 5 |
| `STR-ADV-NORMAL` | adversarial | near, medium, far | 5 each | 5 |

Total: 30 sessions and 150 rectified temporal crops. The expected payload
SHA-256 for each reference is bundled in
`app/assets/capture/diagnostic_capture_plan.json`; a different QR cannot be
saved under either case.

## Capture controls

- Show one locked reference at a time on a separate screen.
- Keep display brightness, room lighting, camera lens, and reference image
  unchanged across the matrix.
- Change only the named distance. Near targets roughly 60-75% QR coverage,
  medium 30-50%, and far 15-25%, with all four corners visible.
- Arm each session once and let the app automatically retain five unique
  frames. Do not select only a favourable result.
- Do not use real payment, personal, attendance, or unknown QR payloads.

## Export contract

The Android collector is compiled with
`--dart-define=QRGUARD_DIAGNOSTIC_CAPTURE=true`. It runs locally and saves a ZIP
to Android `Downloads/QRGuard`. Each session contains `metadata.json` and five
`crop_00.png` through `crop_04.png` files. The archive manifest identifies the
case, ground truth, distance, repeat, hashes, and paths.

Raw decoded payload text is never persisted. Only its SHA-256 identifier is
stored. Export marks the local sessions as exported but deliberately retains
them on the device.

## Decision gate after import

Desktop analysis will score all 150 crops individually and summarize within-
session variance, distance sensitivity, false-safe rate for the adversarial
case, false-block/abstention rate for the clean case, image-quality flags, and
crop geometry. A production multi-frame consensus rule will be implemented only
after those distributions are measured. The final gate must be rerun on held-
out data; these two exposed demo references are diagnostic evidence, not an
independent deployment test set.

## Imported evidence and diagnosis

The completed archive contains all 30 locked sessions and 150 unique crops. Its
SHA-256 is
`859938e1eb44012cb268f25780cca25734955ba76facb66978f6d0e4ade6b3a3`.
Manifest paths, per-session metadata, crop hashes, dimensions, matrix coverage,
and the no-raw-payload contract all passed strict validation.

The on-device collector decoded the expected payload before every session and
stored its matching SHA-256. Desktop OpenCV could not independently decode the
already rectified second-generation screen captures, so the desktop decoded-
hash count is 0/150. That is a decoder-domain observation, not an archive
identity failure.

The deployed single-frame replay exposed the failure mode:

- clean false-Blocked: 13.3% of frames;
- adversarial false-Safe: 2.7% of frames;
- clean non-Safe: 93.3%, including image-quality abstentions;
- 40.0% of all frames abstained on quality;
- majority-of-five removed the adversarial false-Safe sessions but still left
  13.3% clean false-Blocked sessions.

Most medium/far crops were only about 112-208 pixels across. The promoted
exact-app held-out camera set begins at 257 pixels. Upscaling the smaller crops
cannot recreate lost QR modules and produced confident false manipulation.

## Production candidate selected

The selected correction is an acquisition-and-consensus policy, not retraining
on these two exposed demo references:

1. Require the detected QR to produce a rectified crop of at least 256 pixels.
2. Retain up to five distinct consecutive camera crops and require at least
   three analyzable frames.
3. Apply only a global measured-range exposure correction when detail/focus is
   still recoverable.
4. Aggregate the effective score by median and the Structural class by majority.
5. Return an explicit rescan Warning when the evidence is too small or fewer
   than three frames remain analyzable.

Replaying the exact 30 sessions through this candidate produced five definitive
decisions and 25 intentional rescans. All four definitive clean sessions were
Safe and the one definitive adversarial session was Blocked: 0% clean false-
Blocked and 0% adversarial false-Safe. The 83.3% rescan rate is not a claimed
classification success; it shows that the original near/medium/far captures
mostly fell outside the deployment-supported image scale.

The independent locked candidate-stack gate then passed all 120 authoritative
test rows: camera clean false-Blocked 0%, camera adversarial Blocked recall 95%,
camera tampered Blocked recall 100%, and paired camera/gallery exact-verdict
agreement 98.33%. These held-out results are the regression gate; the two demo
QRs remain diagnostic evidence only.
