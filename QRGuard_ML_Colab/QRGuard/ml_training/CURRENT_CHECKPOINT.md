# Current ML checkpoint

Last updated: 2026-08-31.

## Outcome

Structural r01 and Decision r05 are deployed. The rebuilt backend/static/APK
package passed local smoke, GitHub `main` was updated, and both Render services
passed remote health, scan, page and hosted-APK verification.

| Component | Production version | Status |
|---|---|---|
| Structural | `structural-2026.03-r01` | Unified Gallery/Camera runtime; live |
| Semantic | `semantic-2026.02` | Frozen accepted runtime |
| Decision | `decision-2026.03-r05` | All aggregate and 36 cell gates passed; live |
| Full stack | r01 + r05 | Local and remote production smoke passed |

## Artifact identity

- Structural ONNX: 44,702,737 bytes; SHA-256
  `3529df95acaba3f5fe29f7369670de5c0c8c06d60f90e8a2e1959584967c5ad4`.
- Decision weights: 12,694 bytes; SHA-256
  `e0d49a92cc0926e3025b3d431590084ece7ba476ce8041294f68f1ffac3b8385`.
- Canonical capture manifest SHA-256:
  `dc7e220712f7604cc74a1c7cecabc0b73ee63733fd48338311b01b386c415b96`.
- Locked prediction CSV SHA-256:
  `657ced911160249dffba8d73648952a971cdbe6469d9d888f9e9ff19faa9f922`.

## Locked production-path measurements

| Metric | Result | Gate |
|---|---:|---:|
| Camera clean false-block rate | 0.0000 | <= 0.05 |
| Camera adversarial Blocked recall | 0.9500 | >= 0.80 |
| Camera tampered Blocked recall | 1.0000 | >= 0.85 |
| Gallery clean false-block rate | 0.0000 | <= 0.05 |
| Gallery adversarial/tampered Blocked recall | 1.0000 / 1.0000 | reported |
| Final Camera/Gallery verdict agreement | 0.9833 (59/60) | >= 0.95 |
| Structural ONNX P95 latency | 44.09 ms | <= 500 ms |

The one pair disagreement is a genuine Camera Structural miss on an adversarial
sample. It remains in the evidence and was not hidden by a source override.

## Post-promotion verification

- Backend regression: 356 tests passed.
- Production-path exact-app evaluator: all gates passed on 120 locked rows.
- Actual Uvicorn health: unified r01, Semantic 2026.02, Safe < 26 and
  Blocked >= 76.
- HTTP smoke: Camera clean Safe, Camera adversarial Blocked, Gallery clean Safe,
  Gallery tampered Blocked; all HTTP 200 and non-Partial.
- Flutter analyzer: no issues; Flutter tests: 72 passed.
- Render static package: home, download, privacy and APK endpoints all HTTP 200.
- Hosted production APK `1.1.2+8009`: 72,810,512 bytes; SHA-256
  `52c74130822e92dcb27b3e0f2043cd190419c29195a3b40b9dba8169cf5b638c`;
  remote download hash matched and APK Signature Scheme v2 verification passed.

Docker CLI is not installed on this workstation. The Docker packaging contract
passed locally and Render's actual Docker build completed successfully.

## External deployment identity

- GitHub main commit: `e942bbf583d6be227007e5821b2c5c0dd01c239b`.
- Render source commit: `6f17d664e0d1f3f4e30d643c3592dceacabd32fa`.
- API deploy: `dep-daa8vopf2nfc739j8f4g` — live; `/health` reports unified r01.
- Web deploy: `dep-daa8vthf2nfc739j8vbg` — live; pages, capture plan and APK HTTP 200.
- Remote scans: Camera clean Safe 5, Camera adversarial Blocked 81, Gallery
  clean Safe 5, Gallery tampered Blocked 81; all non-Partial HTTP 200.

No promotion milestone remains. Continue normal monitoring and use the recorded
RUN5/Structural 2026.02/Decision 2026.02 rollback set if a regression appears.

Evidence: `ml_training/deployment/promotion/structural-2026.03-r01__decision-2026.03-r05/`.
