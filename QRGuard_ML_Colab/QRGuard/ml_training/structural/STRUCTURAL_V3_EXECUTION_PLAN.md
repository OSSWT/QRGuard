# Structural v3 execution plan

Version: **`structural-2026.03-r01` — LATEST CANDIDATE**
Status: 100x3 real-capture count gate passed; fresh real-data training and Colab
reproduction pending; not deployed.

## Local execution checkpoint — 2026-08-30

The first complete local CPU run used the fixed public/procedural manifest with
10,597 rows. It completed all seven epochs, restored epoch 5 as the best model,
passed the research gates and exported ONNX. Its grouped synthetic test accuracy
was 0.9426, macro-F1 was 0.9435, adversarial recall was 0.9111, tampered recall
was 0.9278, QR-DN clean false-positive rate was 0.0000 and ECE was 0.0194.

Ten controlled nuisance conditions were reported separately. The worst
controlled clean false-positive rate was 0.0526 on the perspective slice. This
is useful development evidence, not real-camera acceptance evidence. The run
remains **CANDIDATE ONLY** because it contains zero exact app-camera test frames
and zero paired Gallery/Camera groups. The unchanged artifact has now been
measured on the locked 100x3 holdout: Camera adversarial recall 0.0000, Camera
tampered recall 0.0000 and paired verdict agreement 0.7333. It remains a useful
pre-real baseline, not a deployment candidate. The audited real data are now
available for a fresh checkpointed run.

## Outcome

Train one quality-aware Structural model for both Gallery and Live Camera. The
model must learn that exposure, blur, distance, glare, perspective, shadow and
screen artefacts are acquisition conditions, not malicious structural labels.
When image evidence is too weak, the application asks for a rescan instead of
inventing a malicious result.

Semantic `semantic-2026.02` stays frozen. A changed Structural probability
distribution still requires decision-layer recalibration and an end-to-end
Semantic regression test.

## Fixed first-run data budget

| Source | Train | Validation | Test/holdout | Role |
|---|---:|---:|---:|---|
| QRGuard procedural, three balanced classes | 2,700 | 540 | 540 | Controlled clean/attack identities |
| QR-DN1.0 clean camera-noise data | 3,600 | 900 | 2,250 | Legitimate acquisition robustness |
| QR Codes on Different Surfaces | 67 | 0 | 0 | Auxiliary geometry/surface clean data |
| Exact QRGuard app Camera crops, audited | 180 | 60 | 60 | Research-domain evidence before severe-quality filtering |
| **Total** | **6,547** | **1,500** | **2,850** | Before paired Gallery rows and optional challenge sets |

The 300 exact-app Camera sessions are 100 per Structural class. Each class is
split as 60 train, 20 validation and 20 test groups. One clearest crop is
authoritative per session. Extra burst frames are acquisition evidence, not
independent samples.

Those totals are the **Camera-row** audited budget. The 60 locked test groups
also have a paired Gallery crop, producing 120 exact-app test rows while the
independent exact-app test count remains 60. Report row counts and independent
group/session counts separately so paired views are never presented as extra
independent data.

## Label contract

- `label`: `clean`, `adversarial` or `tampered` only.
- `quality_condition`: one of the configured everyday capture conditions.
- `quality_severity`: measured or human-verified severity, separate from attack.
- `paired_group`: joins the Gallery source and exact Camera capture of the same
  physical/payload case.
- No payload, physical QR, session, video or augmented parent may cross splits.
- Split first; derive attacks and nuisance variants only inside the assigned
  split.

All three Structural classes must contain the quality conditions. Otherwise the
model could learn a shortcut such as `overexposed = clean` rather than learning
structural integrity.

Digital adversarial images require transform-first/EOT attack generation or a
real recapture. Post-processing an existing FGSM/PGD image can destroy its attack
property, so nuisance recipes are never allowed to preserve that label blindly.

## Quality-aware inference contract

1. Measure exposure, contrast, blur, glare/clipping and usable QR area.
2. Apply only source-neutral normalisation selected from those pixel measures.
3. Run the same Structural artifact for Gallery and Camera.
4. Return calibrated `P(clean)`, `P(adversarial)` and `P(tampered)`.
5. If quality is below the calibrated usable boundary, return an abstention and
   a user-facing rescan reason. Low quality alone never becomes attack evidence.
6. Evaluate paired Gallery/Camera probability delta and verdict agreement.

The old source-specific model routing remains active until this contract passes
all gates.

For local candidate smoke tests only, set
`QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS` to the exported v3 `artifacts/` folder.
That opt-in makes both Gallery and Camera use the same verified v3 metadata,
quality gate, normalisation and ONNX model. Leaving it unset preserves the
current deployed split routing. This environment switch is not a promotion.

## Colab run modes

| Mode | Behaviour |
|---|---|
| `fresh` | Prepare manifests, initialise ImageNet weights and train from epoch 1 |
| `resume` | Restore model, optimizer, epoch, sampler and RNG state from Drive |
| `evaluate_only` | Load the best checkpoint/export and recompute fixed metrics without training |
| `report_only` | Load and display the saved performance bundle; no GPU, data preparation or training |

Canonical Drive layout:

```text
MyDrive/QRGuard_ML/
  cache/structural-2026.03-r01/    # prepared manifests and image cache
  runs/structural-2026.03-r01/
    <RUN_ID>/
      checkpoints/                 # best/last checkpoint and run_state.json
      outputs/
        artifacts/
        performance/               # metrics, predictions, tables and figures

MyDrive/QRGuard_ML_Data/structural/
  QR-DN1.0.zip
  qr_codes_in_surfaces.zip
  runtime_captures/
```

`resume`, `evaluate_only` and `report_only` must verify the experiment config,
manifest and checkpoint hashes before reusing output. This prevents an old
checkpoint being silently reported against changed data.

## Work phases

1. Audit canonical folders, source licences, duplicate groups and existing
   baselines.
2. Extend the runtime/paired manifest and add quality metadata validation.
3. Add deterministic nuisance recipes and fixed per-condition evaluation slices.
4. Add checkpoint/resume/evaluation/report run control.
5. Train in Colab, then preserve the best checkpoint and raw predictions.
6. Evaluate grouped synthetic, QR-DN, exact app-camera and paired consistency.
7. Export ONNX and verify framework/export parity and CPU latency.
8. Recalibrate fusion while keeping Semantic frozen.
9. Run backend, Flutter and local end-to-end tests.
10. Review cleanup candidates, then request explicit approval before promotion,
    GitHub push or deployment.

## Blocking evidence

Public data and generated nuisance images cannot replace exact app captures.
The required labelled sessions and independent groups now exist and pass the
count/leakage contract. Promotion remains blocked until the fresh artifact
passes the held-out class, calibration, paired-consistency, export and latency
gates.
