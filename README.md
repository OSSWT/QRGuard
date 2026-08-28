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

## Approved runtime state

| Component | Runtime version | Status |
|---|---|---|
| Structural - Gallery | RUN 5 EfficientNet-B0 | Stable pristine/gallery artifact |
| Structural - Live Camera | `structural-2026.02`, ImageNet-pretrained ResNet-18 | Camera-robust runtime artifact; exact app-crop acceptance collection remains open |
| Semantic | `semantic-2026.02`, hashed character 3–5 gram calibrated linear model | Gates passed and deployed |
| Risk Decision Layer | `decision-2026.02`, QRGuard-Mix-v2 Fusion | Gates passed and deployed |

Camera and Gallery use different calibrated image artifacts for their acquisition
domains. Gallery keeps the continuous `1 - P(clean)` Structural score. Live Camera
retains that raw score for auditability, corrects only global exposure, and uses the
strongest competing manipulation class when the model's winning class is `clean`.
This prevents two losing three-class probabilities from manufacturing a blocked
binary result. A sub-0.95 camera manipulation confidence cannot be the sole reason a
widely recognised low-risk URL becomes Blocked; the disagreement remains Warning.
High-confidence camera attacks, risky URLs, and Gallery attacks keep the normal
Fusion result. RUN 5 remains the Gallery artifact; `structural-2026.02` serves Live
Camera because RUN 5 measured an 80.84% false-positive rate on the QR-DN holdout.

## Measured results

### Structural candidate `structural-2026.02`

- Grouped synthetic test: accuracy 0.8907, macro-F1 0.8892.
- Digital adversarial recall: 0.9611.
- Tampered recall: 0.9222.
- QR-DN external clean holdout: 2,250 images, clean false-positive rate 0.0000.
- Calibration ECE: 0.0126; ONNX CPU P95: 44.63 ms.
- Deployment remains blocked by zero exact QRGuard runtime capture sessions.

### Semantic `semantic-2026.02`

- Frozen domain-grouped test: 80,000 rows.
- Accuracy 0.8983; F1 0.8969; ROC-AUC 0.9566; PR-AUC 0.9617.
- ECE 0.0202; CPU P95 1.03 ms.
- Behavioural acceptance: phishing recall 1.00 and benign FPR 0.04.
- Training and serving share the same URL canonicalisation, including scheme-less
  URLs routed as `http://...`.

### Risk Decision Layer `decision-2026.02`

- QRGuard-Mix-v2: 1,800 samples, 36 payload/evidence cells.
- Held-out test: 540 rows; ROC-AUC 0.9899.
- Blocked-tier precision 0.9943; Safe-tier false-negative rate 0.0139.
- Exact three-tier accuracy 0.8981; security-impact acceptance 0.9870.
- Clean/abstaining camera open Wi-Fi cells: 100% Warning on the fixed holdout.

Full metrics, per-cell tables, confusion matrices, calibration plots, and ablations
are under `ml_training/*/performance/`.

## Live-camera policy

- Require a stable on-device decode before analysis.
- Rank up to five recent observations on the visible Analysing screen and submit one
  clearest rectified QR crop.
- Correct global camera exposure without thresholding, blurring, or removing local
  colour/shape evidence; preserve the raw model score in every response.
- Treat a low-risk known URL plus medium-confidence camera manipulation evidence as
  cross-modal Warning, while high-confidence attacks remain eligible for Blocked.
- If no usable crop exists, report Structural as unavailable and mark the response
  partial; never replace missing image evidence with a zero score.
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
  datasets/             raw/processed/holdout data contract
  references/           dataset registry, licences, BibTeX and verified sources
  deployment/           model registry and rollback material
  configs/              versioned experiment configurations
training/               deployed artifacts and legacy compatibility entry points
scripts/                server, QRGuard-Mix and evaluation utilities
research_evidence/
  structural/           Structural notebooks, manifests and performance evidence
  semantic/             Semantic notebooks, manifests and performance evidence
docs/                   Setup, testing, design and FYP documentation
```

`ml_training/` is the source of truth for new report material. Legacy names such as
Method 1 and RUN numbers remain only where compatibility or historical comparison
requires them.

## Datasets and provenance

- QR-DN1.0 v2: verified archive, 6,750 real screen-camera distorted/noisy images;
  the official 4,500/2,250 split has disjoint QR identities.
- QR Codes on Different Surfaces v1: 67 trustworthy real rectified crops from 92
  photos; all share one QR identity, so they are auxiliary train-only data.
- Dynamsoft selection: 73 verified source blobs. Prepared crops are licence-
  quarantined and used only for acquisition robustness inspection.
- Semantic sources retain source tags and domain-grouped splits; exact cleaning,
  conflict removal, and duplicate counts are stored in each run.

See `ml_training/references/SOURCES.md`, `dataset_registry.csv`,
`DATASET_LICENSES.md`, and `REFERENCES.bib` before citing or redistributing data.
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

The checked Android version is `1.1.0+8007`.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest backend\tests -q
cd app
flutter analyze
flutter test
flutter build apk --release
```

Current verified result: 275 backend tests passed, Flutter analysis reported no
issues, and 67 Flutter tests passed. The release workflow is documented separately
from these source-level checks.

## Known evidence boundary

The remaining Structural deployment blocker is not a software crash: the repository
contains no labelled, group-disjoint exact QRGuard app-camera sessions for clean,
physical adversarial, and tampered classes. Public camera datasets improve optical
coverage but cannot substitute for exact post-crop app inputs. The required minimum
is 100 sessions per class, including at least 20 test sessions per class. Until those
captures exist, the camera-domain artifact is a measured runtime correction rather
than a claim that the exact app-camera deployment gate has passed.
