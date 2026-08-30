# Structural v3 real paired-capture guide

Target: 50 independent cases per Structural class, distributed across ten
configured quality conditions. Every case requires one Camera session; the
locked test subset also requires a Gallery view of the same displayed QR.

Two acquisition transports are supported:

- trusted private Wi-Fi, where the Backend writes each session immediately;
- the network-free Android queue and bounded ZIP importer documented in
  [`OFFLINE_CAPTURE_AND_IMPORT.md`](OFFLINE_CAPTURE_AND_IMPORT.md).

Both transports must produce the same exact QRGuard app crop and canonical
metadata. A renamed stock-camera photo never becomes exact Live Camera evidence.

## Locked campaign size

| Structural label | Cases | Gallery sessions | Camera sessions |
|---|---:|---:|---:|
| clean | 50 | 10 | 50 |
| adversarial | 50 | 10 | 50 |
| tampered | 50 | 10 | 50 |
| **Total** | **150** | **30** | **150** |

Each class has five selected cases for every condition. `normal` uses severity
`none`. Every other condition includes two `mild`, two `moderate`, and one
`severe` case. Severe inputs test quality abstention and are not normal trainer
rows. Each class is locked to 30 train, 10 validation, and 10 test identities.

## Prepare the versioned campaign once

From the repository root:

```powershell
& ".\.venv\Scripts\python.exe" -m `
  ml_training.structural.src.capture_campaign create `
  ml_training\structural\campaigns\structural-v3-real-2026.03-r01
```

The canonical `campaign.csv` contains opaque case/pair tokens, instructions and
provenance requirements. It contains no raw QR payloads or personal identifiers.

## Start one hot-switch capture session

Set these variables once before starting the local backend:

```powershell
$env:QRGUARD_DUMP_SCANS = Join-Path $PWD "data\runtime_captures"
$env:QRGUARD_CAPTURE_CASE_FILE = "_active_case.json"
```

The case file stays inside `QRGUARD_DUMP_SCANS`. The backend reads it before
every scan, so the operator can change cases without restarting the server.

Activate a clean pilot case:

```powershell
& ".\.venv\Scripts\python.exe" -m `
  ml_training.structural.src.capture_campaign activate `
  ml_training\structural\campaigns\structural-v3-real-2026.03-r01\campaign.csv `
  cln-normal-01 `
  --output data\runtime_captures\_active_case.json `
  --device "phone-model-code" `
  --environment "indoor-controlled"
```

A tampered case additionally requires `--manipulation-method`, for example
`sticker_overlay`. An adversarial case refuses activation unless both a verified
`--attack-method` and 64-character `--attack-reference-sha256` are supplied.

The older per-case environment variables remain supported for isolated
diagnostics, but the backend must be restarted after changing them:

```powershell
$env:QRGUARD_CAPTURE_LABEL = "clean"
$env:QRGUARD_CAPTURE_QUALITY_CONDITION = "glare"
$env:QRGUARD_CAPTURE_QUALITY_SEVERITY = "mild"
$env:QRGUARD_CAPTURE_PAIR_ID = "sheet01-clean-glare-01"
$env:QRGUARD_CAPTURE_PHYSICAL_QR_ID = "sheet01-clean"
$env:QRGUARD_CAPTURE_DEVICE = "test-phone-model"
$env:QRGUARD_CAPTURE_MEDIUM = "printed-paper"
$env:QRGUARD_CAPTURE_ENVIRONMENT = "indoor-window-light"
```

Pair and physical tokens are hashed before capture metadata is stored. Never
put names, phone numbers, URLs or other personal data in these fields.

## Per-case procedure

1. Generate a new reference with `capture_campaign make-pilot`. It uses a
   unique, non-personal HTTPS URL on `example.com`; do not reuse one payload as
   another independent case. Opening the URL is not part of data collection.
2. Human-verify the Structural label and required attack/manipulation provenance.
3. Activate exactly one schedule case.
4. For a locked test case, select the unchanged reference through Gallery.
5. Scan the physical/displayed QR with Live Camera under the scheduled
   condition and severity.
6. Confirm that both generated sessions contain `metadata.json` and one
   authoritative `crop_00.png`.
7. Audit progress before activating the next case.

For offline batches, select the same case inside `QRGuard Capture`, save Camera
and the Gallery test partner when required, export no more than 40 sessions at
once, validate the ZIP, then rerun the importer with `--commit`. The importer
performs the canonical campaign audit after writing; the phone never supplies
trusted model results.

Reusing one payload across several conditions correctly keeps those samples in
one split, but it does not create independent evidence. The backend stores only
the payload hash, never the payload text.

## Quality conditions

```text
normal
overexposure
underexposure
motion_blur
defocus_blur
far_distance
perspective
glare
shadow
screen_moire_or_compression
```

Important label rule:

- exposure, blur, distance, glare, shadow, perspective and screen artefacts are
  quality conditions; they are never adversarial or tampered by themselves;
- `adversarial` requires a documented EOT/physical attack reference verified
  before real recapture;
- `tampered` requires a documented physical manipulation such as an overlay,
  module erasure or finder damage.

Every class must cover every condition. The first strict gate requires at least
five real Camera sessions per class per condition. A quality condition never
changes the Structural ground truth.

Severe cases remain in `manifest_v3.csv` for quality-abstention evaluation but
do not enter the three-class Structural trainer. Their correct outcome is a
rescan request, not a forced attack/clean prediction.

## Campaign progress audit

```powershell
& ".\.venv\Scripts\python.exe" -m `
  ml_training.structural.src.capture_campaign audit `
  ml_training\structural\campaigns\structural-v3-real-2026.03-r01\campaign.csv `
  data\runtime_captures
```

This writes `campaign_progress.csv` and `campaign_progress.json`. A case counts
as complete only when Gallery and Camera agree on case, label, condition,
severity, pair/physical hashes and decoded payload hash.

## Dataset/deployment audit

```powershell
& ".\.venv\Scripts\python.exe" -m `
  ml_training.structural.src.prepare_structural_v3_captures `
  data\runtime_captures
```

This writes `manifest_v3.csv` and `audit_v3.json`. Use `--strict` only for the
final gate. It deliberately fails until the camera-session, independent-test
group and paired-test-group requirements are met.

## Privacy and counting

- Collection is disabled unless `QRGUARD_DUMP_SCANS` is explicitly set.
- Only hashed payload/pair/physical identifiers are stored.
- Campaign and case IDs are opaque non-personal codes.
- One session is one independent unit even if a client supplied several frames.
- Only the selected authoritative crop enters normal model evaluation.
- Never count burst frames or augmented derivatives as independent captures.
