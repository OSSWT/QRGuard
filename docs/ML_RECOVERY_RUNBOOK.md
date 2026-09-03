# Live-camera and ML recovery runbook

Current runtime: Gallery remains a single-image path. Live
> Camera now requires a deployment-range QR crop, retains five geometry-ranked
> observations as fallback, and prepares/uploads the best three eligible crops
> for median-score / majority-class consensus. Smaller or insufficient evidence asks
> the user to move closer and rescan. This policy was selected after the locked
> 30-session / 150-frame repeatability study and passed the independent 120-row
> candidate-stack gate. See `LIVE_CAMERA_REPEATABILITY_STUDY.md`.

## Why Gallery was normal and Live camera was not

The payload was not changing. The image distribution was.

1. Gallery submitted one pristine QR crop. Structural RUN 5 scored it low.
2. Live camera submitted one photographed crop. Identical clean codes were
   observed between roughly 0.24 and 0.83 `p_structural` depending on pose.
3. The old runtime rule discarded camera scores below 0.80 but accepted 0.80 and
   above continuously. With the Structural fusion weight at 12.64, moving from
   0.799 to 0.800 could jump from Warning 33 to Blocked about 95.
4. Open Wi-Fi has no `p_url`; its correct policy is Warning. One noisy image
   score therefore dominated the only semantic evidence and produced Blocked.

The live-camera runtime retains up to five independent observations, but stops
after preparing the first three geometry-ranked crops that are at least 256
pixels and pass the image-quality path. Only those three are uploaded. Scores
are aggregated by median and classes by majority. Insufficient evidence makes
Structural abstain and returns a rescan Warning; URL/rule evidence can still
Block on its own. Pixel-identical uploads are de-duplicated and do not count as
independent frames; the training audit rejects such sessions too.

## Collect exact runtime evidence

The capture path is opt-in. Stop the backend, choose one ground-truth class, and
start it from the repo root:

```powershell
$env:QRGUARD_DUMP_SCANS = Join-Path $PWD "data\runtime_captures"
$env:QRGUARD_CAPTURE_LABEL = "clean"  # clean | adversarial | tampered
& ".\.venv\Scripts\python.exe" scripts\run_server.py
```

Scan physical/displayed samples through Live camera, not Gallery. Change the
label only when the physical truth changes. Each accepted scan writes 3–5 exact
post-rectification PNG crops plus `metadata.json`. Metadata contains the payload
SHA-256, dimensions, source, model scores, and verdict; it never stores the raw
payload. The feature is off when `QRGUARD_DUMP_SCANS` is unset.

Capture at least 100 scan sessions per class, including at least 20 independent
payload groups that hash into the test split. Vary phone/camera, distance, angle,
lighting, focus, screen vs paper, module density, QR error correction, colored
codes, and legitimate logos in every class. Do not label blur as tampering.

Audit and split:

```powershell
& ".\.venv\Scripts\python.exe" -m ml_training.structural.src.prepare_runtime_captures `
  data\runtime_captures --strict
```

Copy the audited directory to
`MyDrive/FYP2/runtime_captures/`, then run the Structural notebook on a Colab T4.
The notebook refuses to export until exact app-camera test crops achieve:

- clean false-positive rate at most 5%;
- tampered recall at least 85%;
- adversarial recall at least 80%;
- calibrated manipulated-vs-clean ECE at most 0.05.

These are minimum deployment gates, not claims of statistical certainty. Report
sample counts and confidence intervals alongside observed rates.

## Semantic Training

Open `ml_training/semantic/notebooks/semantic_training_v2.ipynb` on a Colab T4 and Run all. Semantic Training:

- removes canonical URL label conflicts across sources;
- splits by registered domain;
- keeps the behavioural unseen-domain slice out of training;
- adds balanced official-domain hard negatives and lookalike positives;
- calibrates on validation only;
- requires behavioural benign FPR at most 5%, phishing recall at least 90%,
  official-brand maximum `p_url` at most 0.35, and per-source ROC-AUC at least
  0.90 before writing a deploy selector; calibrated ECE must be at most 0.03.

If `DEPLOYMENT_REJECTED.json` exists, keep the deployed baseline installed and inspect the failed
slice. Do not tune on the acceptance set; add independently sourced training data
for the failed pattern, then rerun against the unchanged acceptance contract.

## Rebuild Fusion

After installing only Structural/Semantic artifacts that passed their gates:

```powershell
& ".\.venv\Scripts\python.exe" scripts\build_qrguard_mix.py
& ".\.venv\Scripts\python.exe" scripts\train_fusion.py
```

QRGuard-Mix v2 has 18 cells: three image classes crossed with benign URL,
phishing URL, open Wi-Fi, secure Wi-Fi, plain text, and executable URI. Open
Wi-Fi has a fractional Warning target. The fusion trainer writes a candidate
first and promotes it only if aggregate security targets and every per-cell tier
accuracy gate pass. A rejected candidate never overwrites deployed weights.

Finally run the full backend and Flutter suites and repeat the physical Live
camera matrix. Gallery-only results are not a release check.
