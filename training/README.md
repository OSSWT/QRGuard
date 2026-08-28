# Legacy training notes and deployed artifact compatibility

The canonical report-facing workspace is now `ml_training/` and is divided into
**Structural Training** and **Semantic Training**. This file retains historical
run measurements and artifact compatibility information; do not use its old
Method/Run names as the current report section titles.

## Current deployment state (2026-08-21)

`training/artifacts/` now contains the retained Structural RUN5 gallery artifact
and the promoted `semantic-2026.02` model. `backend/fusion/fusion_weights.json`
contains promoted `decision-2026.02`. The old Method 1 artifact remains only for
rollback and compatibility tests; it is no longer the automatic Semantic branch.

- Structural RUN 5 measured a 19.08% false-positive rate on its simulated clean
  camera slice, and there are no formal real-photo training sessions in the repo.
- Semantic v2 passes its frozen domain-grouped and behavioural gates. It uses one
  canonical representation in training and serving, fixing the scheme-normalisation
  skew that caused live-camera false positives.
- Decision v2 was fitted on 1,800 QRGuard-Mix-v2 rows across 36 cells. Open Wi-Fi,
  non-URL payloads, gallery states, and live-camera consensus/abstention states are
  all represented and gated.

The replacement sequence remains fail-closed. Steps 4–5 below are complete; exact
runtime capture collection is the remaining Structural gate:

1. Start the backend with `QRGUARD_DUMP_SCANS=<folder>` and one of
   `QRGUARD_CAPTURE_LABEL=clean|adversarial|tampered`. Scan each physical sample
   from several angles. Dumps contain exact app crops and a payload SHA-256 only.
2. Run `python -m ml_training.structural.src.prepare_runtime_captures <folder> --strict`. The split
   unit is payload hash, so frames and physical variants of one QR cannot leak
   across train/validation/test. Formal training requires 100 sessions per class
   and 20 independent test payload groups per class.
3. For the current Structural `.02` candidate, use
   `ml_training/structural/src/structural_recipes.py` followed by
   `ml_training/structural/src/train_local.py`. The existing
   `ml_training/structural/notebooks/structural_training.ipynb` is retained as a
   historical EfficientNet/RUN4 Colab experiment and must not be used to claim
   the current `.02` metrics.
4. Semantic `semantic-2026.02` is complete and deployed. The local reproducible
   implementation is `ml_training/semantic/src/train_local.py`; the canonical
   notebook remains available for Colab documentation.
5. QRGuard-Mix-v2 and Decision `decision-2026.02` are complete and deployed.
   The matrix includes URL, Wi-Fi, text, executable payloads, six source/evidence
   modes, Safe/Warning/Blocked targets, and 36 per-cell reports. Failed future
   candidates remain in `fusion_weights.candidate.json`.

Do not copy a candidate merely because its average accuracy or ROC-AUC is high.
The branch-specific and per-cell gates above are the deployment decision.

两个 notebook 都在 **Google Colab (T4 GPU)** 跑，其余一切在笔电跑。
训练 = 调整几百万个权重，需要 GPU；推论 = 拿成品算一次答案，CPU 就够。

| Notebook | Produces | Runs so far |
|---|---|---|
| `ml_training/structural/notebooks/structural_training.ipynb` | `p_structural` — Structural Training | RUN5 retained; `structural-2026.02` awaits exact app captures |
| `ml_training/semantic/notebooks/semantic_training.ipynb` | `p_url` — Semantic Training | `semantic-2026.02` deployed |
| `ml_training/semantic/legacy/semantic_legacy_run3.ipynb` | historical Semantic notebook | Experiment lineage only |

Colab entry-point summary: use `ml_training/semantic/notebooks/semantic_training_v2.ipynb`
for Semantic `.02`; its script now defaults to `semantic-2026.02` and supports
`QRGUARD_RUN_TAG` for deliberate future runs. For Structural `.02`, run
`ml_training/structural/src/structural_recipes.py` and then
`ml_training/structural/src/train_local.py` after the prepared datasets are
available in the Colab checkout. The Structural notebook in the table above is
historical RUN4/EfficientNet lineage, not the current `.02` pipeline.

The ready-to-open current notebooks are
`ml_training/semantic/notebooks/semantic_training_v2.ipynb` and
`ml_training/structural/notebooks/structural_training_v2.ipynb`.

Artifacts land in `MyDrive/FYP2/<branch>/<run>/artifacts/`, then get copied into
`training/artifacts/structural/` and `training/artifacts/semantic/` (both gitignored).
Superseded runs are kept beside them — `structural_run1/`, `_run2/`, `_run3/`, `_run4/` —
because the report tells the story of the iteration, not just the final number.

**Keep each Phase's documented contract stable.** Several decisions here are
evidence-backed, and changing them previously produced a measurable defect.

---

## Structural Training — `ml_training/structural/notebooks/structural_training.ipynb`

One EfficientNet-B0, three classes: `clean` / `adversarial` / `tampered`.
The fusion signal is `p_structural = 1 − P(clean)`.

### Phase 0 — Setup

Mounts Drive, installs, fixes seeds, names the run.

**Why it matters.** Order is load-bearing: Drive is mounted **before** any install,
and `torchattacks` is installed with `--no-deps`. It declares `requests~=2.25.1`,
which downgrades the `requests` that `google.colab` itself pins, and the next
`drive.mount()` then dies with `ValueError: mount failed`.

`RUN` names the output folder, so a new run never overwrites the previous one.
`CAMERA_FRACTION = 0.5` — half of **every** class is rendered as if photographed.

**Check:** the printed `requests` version is 2.32.x, and the device says `cuda`.

### Phase 1 — Clean QR base set

Generates 2500 codes with the `qrcode` library.

**Why it matters.** This class defines what "normal" means, and getting it too
narrow was a real defect. Codes vary in error-correction level, module size,
quiet-zone width and colour, and roughly half of the high-error-correction ones
carry a **centred logo** — because branded codes carry logos everywhere, and a
logo looks a great deal like a sticker attack. Measured on RUN 3, which had no
logos in training: 20 of 25 legitimate logo codes were called tampered.

**Check:** `Phase 1 complete -- generated 2500 clean QRs`.

### Phase 2 — Split first, then derive adversarial + tampered

Splits the base codes 70/15/15 **before** deriving anything, then builds the
attacked variants and applies the camera simulation.

**Why it matters — three separate things:**

1. **Split first, or the test set leaks.** A base code and its attacked twin share
   almost every pixel; if they land in different splits the test score is fiction.
2. **`blur` is not an attack.** It was one in RUN 1, and the model learned
   "blurry ⇒ tampered": a real photo of a *safe* code scored `p_structural`
   0.9995 where its own PNG scored 0.000146, so every live scan returned Blocked.
   Blur describes how a code was *captured*. The attacks are sticker overlay,
   occlusion, finder-pattern damage and scratches — things an attacker physically
   does, which survive being photographed.
3. **`simulate_capture` runs on every class.** Perspective, uneven lighting,
   resolution loss, focus softness, sensor noise, JPEG — and, since RUN 3, the
   code is first composited onto a generated **surface** (wall / wood / paper /
   gradient / concrete) with clutter and a poster border. RUN 2 warped the code
   alone and replicated its edge pixels, so the model never saw a code with a
   wall *around* it; that single omission left the real camera crop at 0.5973.
   It must apply to all three classes, or the model just relearns "soft ⇒ attacked".

**Check:** `camera-simulated share: ~0.5`, and the per-split counts.

### Phase 3 — Fine-tune EfficientNet-B0

Transfer learning from ImageNet, 20 epochs in deployed RUN 5, best-on-validation saved.

**Why it matters.** `train_tf` augments (blur / colour jitter / perspective) on top
of the baked-in camera simulation; `eval_tf` does not. **Never measure through an
augmenting transform** — validation, test and export all use `eval_tf`.

**Check:** `val_acc` rising then flattening. RUN 5 is deployed; compare runs on fixed
inputs because its higher camera fraction changes the validation/test distribution.

### Phase 4 — Evaluation

Per-class precision / recall / F1, confusion matrix, and the slices.

**Why it matters.** A single average hides the only thing that matters. Metrics are
reported separately for **pristine** and **camera_simulated**, plus the number that
names the RUN 1 bug directly: the false-positive rate on photographed clean codes.

**How to read it** — interpret the per-class metrics carefully. In short:
`clean` reads backwards (its *precision* falling means attacks were missed, its
*recall* falling means safe codes were wrongly flagged), and the `pristine` 1.0000s
are a sanity check rather than an achievement — a perfectly rendered clean QR
*should* always be called clean. Quote the `camera_simulated` slice as the
deployment figure.

**Check:** `photographed CLEAN codes wrongly flagged` — RUN 1 was effectively 1.0,
RUN 4 is 0.0769 on a simulation deliberately harder than reality. RUN 5 is the deployed
model; its real-photograph evaluation is still required.

### Phase 5 — Temperature calibration

Fits a single scalar `T` on the validation set, reports ECE before and after.

**Why it matters.** Fusion multiplies these probabilities by learned weights, so an
over-confident 0.99 that should be 0.7 corrupts the verdict. A rising `T` across
runs (1.39 → 1.08 → 2.12) means the model became **less certain** as the task got
harder — that is correct behaviour, not degradation.

**Check:** `ece_after` under about 0.03. Note ECE is measured on the binary
manipulated-vs-clean projection while `T` is fitted on the 3-class loss, so it can
move slightly the wrong way; both stay small.

### Phase 6 — `p_structural` behaviour

Mean `p_structural` per class, plus clean-pristine vs clean-photographed.

**Why it matters.** Phase 4 measures `argmax`; fusion consumes `p_structural`.
They are not the same thing, and this is the check RUN 1 would have failed.

**Check:** clean LOW, adversarial and tampered HIGH, and **clean-photographed still
LOW**.

### Phase 7 — Export, quantize, benchmark

ONNX FP32 + INT8, accuracy comparison, latency, and a `predict_structural()` demo.

**Why it matters.** The ≤2 pp policy picks the deployed format automatically.
Dynamic INT8 quantization targets Transformer `Linear` layers, so on this
Conv-heavy CNN it collapses accuracy (0.92 → 0.31) **and runs 8× slower**
(169 ms vs 17 ms). FP32 being chosen is the policy working, not a limitation.

**Check:** `INT8 drop > 2pp -> deploying FP32`, latency well under the 500 ms budget.

---

## Semantic Method 1 — `method1_finetune_domurls_bert.ipynb`

Fine-tunes DomURLs_BERT into `p_url`, the phishing probability for a URL string.

### Phase 0 — Setup
Same shape as above: Drive, installs, seeds, run folder.

### Phase 1 — Combine PhiUSIIL + malicious_phish + Tranco benign

**Why it matters.** RUN 1 trained on PhiUSIIL alone, scored 0.9987 in-domain, and
collapsed to **ROC-AUC 0.53** on another corpus — it had learned a dataset-specific
shortcut, not phishing. RUN 2 combined two corpora and fixed that, but then flagged
`google.com/maps` and `paypal.com/signin` as phishing, because brand words appear
mostly in phishing URLs during training. RUN 3 adds real Tranco top-domain benign
URLs to break that shortcut.

**Check:** the combined row count and the benign/phishing ratio.

### Phase 2 — Domain-level 70/15/15 split

**Why it matters.** Splitting by *row* puts `login.evil.com/a` in train and
`login.evil.com/b` in test, which measures memorisation. Splitting by **registered
domain** is what makes the number mean generalisation. The source tag is kept so
Phase 4 can report per-corpus.

### Phase 3 — Fine-tuning
Standard fine-tune of the pretrained encoder with a classification head.

### Phase 4 — Test metrics, overall **and per source**

**Why it matters.** The overall figure is an average over corpora with different
difficulty. Per-source is what exposed the RUN 1 collapse.

**Check:** per-source ROC-AUC — RUN 3 gives 0.996 (malicious_phish) and 0.9875
(phiusiil).

### Phase 5 — Temperature calibration
As above. RUN 3 gives `T = 2.2033`, ECE 0.0202 → 0.0052.

### Phase 6 — Real-world sanity set

A small hand-labelled set of URLs a human can judge instantly.

**Why it matters.** This is the direct check that `google.com/maps` scores LOW. RUN 2
passed every aggregate metric and still failed this, which is why it exists.

**Check:** real brand URLs low, fake brand URLs high.

### Phase 7 — ONNX + INT8 + latency + `predict_url()`

**Why it matters.** Unlike the CNN, INT8 *does* work here — DomURLs_BERT is a
Transformer, which is exactly what dynamic quantization targets. Drop was 0.37 pp,
so INT8 is deployed at ~15 ms/URL against a 150 ms budget.

**Check:** the demo scores match what `backend/semantic/method1.py` produces
locally — there are regression tests pinning these values.

---

## Known limitation worth carrying into the report

Method 1's confident tail is **not** clean. On QRGuard-Mix, `p_url ≥ 0.95` has
precision 0.809, with 101 of 450 benign URLs above the threshold and a benign
maximum of 0.992. Fusion therefore gives `p_url` a small weight (6.05), and that is
correct rather than a defect. A 2026-08-03 hypothesis test tried increasing it,
and the measurement rejected that change.
