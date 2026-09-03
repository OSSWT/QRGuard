# QRGuard: Multimodal QR Code Risk Analysis

QRGuard is a Final Year Project (FYP) research prototype that evaluates both the
visual integrity of a QR code and the security risk of its decoded payload. The
system combines a Flutter mobile application with a FastAPI analysis service and
produces a calibrated 0–100 risk score with one of three actions: **Safe**,
**Warning**, or **Blocked**.

## Academic context

| Field | Details |
|---|---|
| Project type | Bachelor of Computer Science (Honours) Final Year Project |
| Author | Ooi Sze Shou |
| Institution | Universiti Tunku Abdul Rahman (UTAR) |
| Faculty | Faculty of Information and Communication Technology, Kampar Campus |

This repository contains the implementation, experiment definitions, evaluation
evidence, and reproducibility material prepared for the project. It is an academic
prototype and must not be treated as a guarantee that a QR code or destination is
safe.

- **Live application:** https://qrguard-app-osswt.onrender.com
- **Backend API:** https://qrguard-api-osswt.onrender.com
- **Android download:** https://qrguard-app-osswt.onrender.com/download.html

## Current architecture

```text
Flutter camera/gallery
  -> on-device QR decode and rectified crop selection
  -> FastAPI /scan
       |-- Structural Training: clean / adversarial / tampered image evidence
       |-- Semantic Training: calibrated URL risk + deterministic payload rules
       `-- Risk Decision Layer: monotonic Fusion + source-aware safety policy
              Safe < 45 <= Warning < 55 <= Blocked
```

The project has two report-facing trained phases:

1. **Structural Training** analyses QR image integrity.
2. **Semantic Training** analyses the decoded URL/payload.

The Risk Decision Layer combines those branches. It is a calibrated decision
component, not a third analysis branch. An optional user-initiated Deep Check adds
redirect and LLM evidence; its weights are not represented as trained in the
automatic QRGuard-Mix-v2 model.

## Active controlled runtime state

| Component | Runtime version | Status |
|---|---|---|
| Structural - Gallery | `structural-r07-corrective-v1`, ImageNet-pretrained ResNet-18 | User-authorized controlled release; development gate passed; fresh formal blind acceptance pending |
| Structural - Live Camera | `structural-r07-corrective-v1`, ImageNet-pretrained ResNet-18 | Same artifact with quality/exposure selection, three-frame consensus and fail-closed Rescan |
| Semantic | `semantic-2026.02`, hashed character 3–5 gram calibrated linear model | Gates passed |
| Risk Decision Layer | `decision-2026.03-r05`, QRGuard-Mix-v2 Fusion | All 36 policy cells passed; Safe `<26`, Blocked `>=76` |

Camera and Gallery use the same calibrated Structural artifact. r07 is deliberately
presented as a controlled release, not a formal promotion: its development
screen-to-camera calibration passed, but a fresh candidate-bound independent blind
acceptance remains pending. The runtime abstains to Rescan when image evidence is
insufficient and never turns an inconclusive Structural result into Safe. The
previous r01 artifact remains the immediate rollback boundary.

## Measured results

### Structural `structural-r07-corrective-v1`

- Controlled attack-calibration capture: 72 sessions and 360 validated frames.
- Physical-channel survival: 25/48 planned attack cases; only verified survivors
  contribute to attack-recall measurements.
- Clean false-block rate: 0.00 in low, medium and high QR-version bands.
- Independent surviving attack-base recall: 1.00 low, 1.00 medium and 0.8333 high.
- One dense high-version base required Rescan; no analyzable surviving attack was
  returned as Safe.
- Formal promotion remains pending a new independent candidate-bound blind test.

### Previous formal baseline `structural-2026.03-r01`

- Exact-app locked test: 120 rows; Camera and Gallery each contain 20 samples per class.
- Camera: clean false-block rate 0.00, adversarial blocked recall 0.95, tampered recall 1.00.
- Gallery: clean false-block rate 0.00, adversarial and tampered recall 1.00.
- Paired Camera/Gallery verdict agreement: 59/60 (0.9833).
- QR-DN external clean holdout: 2,250 images, clean false-positive rate 0.0000.
- ONNX CPU P95: 44.09 ms; all research and deployment gates passed.

### Semantic `semantic-2026.02`

- Frozen domain-grouped test: 80,000 rows.
- Accuracy 0.8983; F1 0.8969; ROC-AUC 0.9566; PR-AUC 0.9617.
- ECE 0.0202; CPU P95 1.03 ms.
- Behavioural acceptance: phishing recall 1.00 and benign FPR 0.04.
- Training and serving share the same URL canonicalisation, including scheme-less
  URLs routed as `http://...`.

### Risk Decision Layer `decision-2026.03-r05`

- QRGuard-Mix-v2: 1,800 samples, 36 payload/evidence cells.
- Held-out test: 540 rows; ROC-AUC 0.9820.
- Blocked-tier precision 0.9912; Safe-tier false-negative rate 0.0194.
- Exact three-tier accuracy 0.8667; policy acceptance 0.9759.
- Every one of the 36 fixed policy cells passed its acceptance gate.

Full metrics, per-cell tables, confusion matrices, calibration plots, and ablations
are under `ml_training/*/performance/`.

## Live-camera policy

- Require five stable on-device sightings before analysis.
- Require deployment-supported crop detail (at least 256 pixels after
  rectification); otherwise ask the user to move closer instead of guessing.
- Retain five geometry-ranked observations as a fallback pool, prepare and
  upload the best three crops that meet the 256 px gate, then aggregate scores
  by median and classes by majority.
- Snapshot the active browser video before stopping a Web scan because
  `mobile_scanner` Web detections do not include encoded image bytes.
- Correct only recoverable global camera exposure without thresholding, blurring,
  or removing local colour/shape evidence; preserve the raw median model score.
- Treat a low-risk known URL plus medium-confidence camera manipulation evidence as
  cross-modal Warning, while high-confidence attacks remain eligible for Blocked.
- A declared Camera/Gallery scan must contain a decodable crop. If acquisition
  fails, ask the user to rescan instead of silently degrading to URL-only Partial.
- An open or WEP Wi-Fi payload always has a Warning floor. It is not labelled fraud
  merely because the network is open.
- Recognise the narrow `Q01:*:` hi-hive attendance envelope as an opaque token,
  report Warning, and open only the official app for the user to scan again.

## Canonical project layout

```text
app/                    Flutter mobile application and widget/unit tests
backend/                FastAPI pipeline, Structural/Semantic services and tests
data/                   runtime/evaluation inputs (large generated data ignored)
ml_training/
  structural/           Structural source, runs and report-ready performance
  semantic/             Semantic source, runs and report-ready performance
  decision_layer/       Fusion runs, per-cell metrics and figures
  datasets/             Structural/Semantic data, references, generated QR provenance and demo pack
  deployment/           model registry and rollback material
  configs/              versioned experiment configurations
training/               current deployed artifacts and explicit rollback boundary
scripts/                server, QRGuard-Mix and evaluation utilities
research_evidence/
  structural/           Structural notebooks, manifests and performance evidence
  semantic/             Semantic notebooks, manifests and performance evidence
docs/                   Current recovery, repeatability and reference notes
```

`ml_training/` is the source of truth for report material. Historical run numbers
remain only where they identify reproducible r07 lineage or an active rollback
boundary. Obsolete runtime implementations and duplicate model copies are not
kept in the active repository.

## Datasets and provenance

- QR-DN1.0 v2: verified archive, 6,750 real screen-camera distorted/noisy images;
  the official 4,500/2,250 split has disjoint QR identities.
- QR Codes on Different Surfaces v1: 67 trustworthy real rectified crops from 92
  photos; all share one QR identity, so they are auxiliary train-only data.
- Dynamsoft selection: 73 verified source blobs. Prepared crops are licence-
  quarantined and used only for acquisition robustness inspection.
- Semantic sources retain source tags and domain-grouped splits; exact cleaning,
  conflict removal, and duplicate counts are stored in each run.

See the complete
[`DATASET_CATALOG.md`](ml_training/datasets/DATASET_CATALOG.md), machine-readable
[`DATASET_INVENTORY.json`](ml_training/datasets/DATASET_INVENTORY.json), and the
supporting `references/SOURCES.md`, `dataset_registry.csv`,
`DATASET_LICENSES.md`, and `REFERENCES.bib` before citing or redistributing data.
The reusable post-training QR scan cards and result templates are in
[`qr_codes_demo/`](ml_training/datasets/qr_codes_demo/README_%E4%B8%AD%E6%96%87_English.md).
The organised evidence entry point is
`research_evidence/README.md`; it deliberately does not duplicate
the large canonical training datasets.

## Run the system

### VS Code one-key development

Open this repository folder, press `Ctrl+Shift+D`, select
**Full stack: backend + Android Emulator (live webcam)**, and press `F5`. The
checked-in task starts or checks `Small_Phone`; the backend profile explicitly uses
`.venv\Scripts\python.exe`.

PowerShell alternative:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev\Start-QRGuardDevelopment.ps1
```

See `scripts/dev/README.md` for the individual backend, emulator, Flutter, and
retired-package cleanup commands. Repeated `flutter run` builds replace the same
`com.osswt.qrguard` package and do not add another icon.

### Backend

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv\Scripts\python.exe scripts\run_server.py --port 8001 --lan --no-reload
```

The Android emulator currently uses `http://10.0.2.2:8001`. A physical phone must
use the computer's LAN address shown by `run_server.py --lan`.

### Flutter

```powershell
cd app
flutter pub get
flutter run
```

The checked Android version is `1.2.0+8012`.

Release `1.2.0+8012` is built, signed and deployed to the production endpoint. Its
APK is 73,462,225 bytes with SHA-256
`c415337eed98e7d87517cd25c5523d251a3547b5b60277b07940e64f8243e64c`.
The hosted APK matches that hash. The production API reports unified
`structural-r07-corrective-v1`, and the production Web version endpoint reports
`1.2.0+8012`.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest backend\tests -q
cd app
flutter analyze
flutter test
flutter build apk --release
```

Current change verification: 470 backend tests passed with three conditional
skips, Flutter analysis reported no issues, and 104 Flutter tests passed. The
production-endpoint Web build and signed Android release both completed; the APK
identity and signer certificate were verified independently of the build step.
The deployed API also completed the canonical 42-case remote demo smoke with
42/42 intended Gallery outcomes, 42/42 intended Camera-simulation outcomes and
84/84 HTTP 200 responses.

## Evidence boundary

The Structural runtime audit contains 300 accepted Camera sessions (100 per class),
including 20 locked test sessions per class, plus paired Gallery evidence. r07 adds
controlled physical calibration across QR-version bands, but that evidence is
development-only. These measurements cover the defined campaign and devices; they
are not a claim of universal performance on every camera, display, print, lighting
condition or unseen manipulation method. The exact controlled-release, formal-gate
and deployment state is recorded in `ml_training/deployment/model_registry.json`.
