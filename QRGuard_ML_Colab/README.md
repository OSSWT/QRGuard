# QRGuard complete Google Colab ML package

This folder is the self-contained ML hand-off. Structural v3 is the current
FYP2 candidate; Semantic `semantic-2026.02` is frozen and report-only. It
contains the canonical source, dataset contracts, licences, references,
check-pointable Structural notebook, frozen Semantic report notebook, and a
frozen report of the latest Decision/Fusion candidate.

The existing measured baseline/candidate numbers are summarised in
`REFERENCE_RESULTS.md` and their original figures/JSON/CSV files are under
`reference_performance/`. Structural can create a new Drive run; the Semantic
notebook displays its frozen evidence without retraining.

## Start here

1. Upload `QRGuard_ML_Colab.zip` to `MyDrive/QRGuard_ML_Colab.zip`.
2. For Structural, download the official QR-DN1.0 v2 and QR Codes in Surfaces
   v1 archives and place them at:
   - `MyDrive/QRGuard_ML_Data/structural/QR-DN1.0.zip`
   - `MyDrive/QRGuard_ML_Data/structural/qr_codes_in_surfaces.zip`
3. If available, copy labelled exact app captures to
   `MyDrive/QRGuard_ML_Data/structural/runtime_captures/`.
4. Open `01_Structural_Training_Colab.ipynb`, choose `fresh`, `resume`,
   `evaluate_only`, or `report_only`, select a T4 GPU when needed, and Run all.
5. Open `02_Semantic_Frozen_Report_Colab.ipynb` to display the existing measured
   Semantic evidence without retraining.
6. Open `03_Decision_Frozen_Report_Colab.ipynb` to display the saved Fusion
   metrics, per-cell table and ablation without retraining or promotion.
7. Structural checkpoints and outputs are saved under
   `MyDrive/QRGuard_ML/runs/structural-2026.03-r01/<RUN_ID>/`.

Raw third-party datasets are not redistributed in this source package because
they are large and governed by their source terms. Official URLs, DOI/licence,
expected byte sizes, SHA-256 hashes and acquisition code are included. That is
the reproducibility material; the notebooks fetch or verify the actual data.

## Honest camera gate

A QR can decode successfully while the image-integrity model cannot safely use
the camera frames. Decoding and Structural classification are different tasks.
Synthetic camera augmentation alone cannot prove performance on QRGuard's exact
crop pipeline. The checked-in r01 candidate has now passed the labelled 100x3
exact-app and paired gates and was later promoted into the local runtime. GitHub
and external Render deployment remain separate, reviewed steps.

## Colour contract

Structural Training uses RGB, 224×224, `[0,1]` scaling and ImageNet RGB
normalisation. It does not use CMYK or Lab. See
`QRGuard/ml_training/COLOR_PIPELINE.md` for the exact coloured-QR generation,
camera colour-correction and serving parity contract.
