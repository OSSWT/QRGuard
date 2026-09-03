# Screen-camera robustness baseline

Recorded: 2026-09-01 (Asia/Kuala_Lumpur).

## Source and runtime identity

- Git branch: `main`.
- Git commit: `8deefe5a23cd30f225f9c6ebff575241c800c195`.
- Source tree was clean before this milestone began.
- Flutter version: `1.1.4+8011`.
- Production source recorded by the root README: `c82bb9e`.
- Structural runtime: `structural-2026.03-r01`.
- Semantic runtime: `semantic-2026.02`.
- Decision runtime: `decision-2026.03-r05`.

## Locked artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `training/artifacts/structural/structural_fp32.onnx` | 44,702,737 | `3529DF95ACABA3F5FE29F7369670DE5C0C8C06D60F90E8A2E1959584967C5AD4` |
| `training/artifacts/semantic/semantic_model.joblib` | 6,060,168 | `A15A5A409DF739465C2B94371C059CBD728C1B1E1C879F69E0400A858ED230CE` |
| `backend/fusion/fusion_weights.json` | 12,694 | `E0D49A92CC0926E3025B3D431590084ECE7BA476CE8041294F68F1FFAC3B8385` |
| `ml_training/datasets/qr_codes_demo/MANIFEST.json` | 40,870 | `4E19C47C6244973B2ABA25CA884AAC12BC532BCD90F6CE58A7F7BAEC41FF0E93` |
| `ml_training/datasets/qr_codes_demo/EXPECTED_RESULTS.csv` | 18,427 | `1D38D1494587125EB7FA082BA89195E446F87390DBB9557868282D5D9D098189` |
| `online-qrguard-1.1.4+8011.apk` | 73,139,643 | `09873FADAE5EC0E17C6ED8E047B72459D531C1CCCC67D2469F25FB7BF4BD0AAC` |

The APK is a rebuildable local cache outside the repository.  This record does
not promote or deploy a new artifact.

## Automated baseline

- Backend: 366 passed, 1 skipped.
- Flutter tests: 86 passed.
- Flutter analyzer: no issues.
- The first sandboxed pytest invocation reached 100% but Windows denied cleanup
  of pytest's temporary link.  The authoritative run used an isolated temporary
  directory outside that restriction and exited successfully.

## Physical screen-camera evidence

| Evidence archive | SHA-256 | Observation |
|---|---|---|
| `CamGalleryDemo.zip` | `9565B1121CA4480EFBBF59E1EC837FC8A1919327835FAF7CA0DA9C931EE5117E` | Gallery 12/12 intended; Camera 11/12 final verdicts; SEM-05 carried a hidden Structural false positive. |
| `SEM-11-PLAIN-TEXT 1 CamGallery.zip` | `0EA63D719C8D45ECB460FD59676AA8D43B37F19EB75F8B41146F02289D8E14E7` | Gallery 4/4 Safe; Camera 3/4 false Blocked. |
| `SEM-11-PLAIN-TEXT %.zip` | `EB5F09CEA491CEB698F21CAC8B71FAD5C6B039794FD438060C472C57C8E27D34` | 60%: 3/3 Safe; 80%: 1/3 Safe; 100%: 3/3 Safe. |
| `SE,-11-PLAIN-TEXT % 10T.zip` | `009DAF2D961351DC46E15968360E1286234CE33FB0675E45AB515B6F68AD999B` | Current display condition: 10/10 Safe, Structural 0.11-0.40. |

Screenshots establish the visible failure but are not model-input fixtures.  M3
must collect the actual rectified Camera crops before model retraining or a
physical-input regression claim.

## Frozen boundary

M0 freezes identity and evidence only.  It does not claim that SEM-11 is fixed,
does not treat final-verdict agreement as branch correctness, and does not
change runtime thresholds, model artifacts, fusion weights or deployment.
