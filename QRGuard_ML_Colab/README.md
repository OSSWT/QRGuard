# QRGuard complete Google Colab ML package

This folder is the self-contained hand-off for both trained QRGuard branches.
It contains the canonical training/evaluation/export source, dataset contracts,
licences and references, the current reference performance, and two Run-all
Google Colab notebooks.

The existing measured baseline/candidate numbers are summarised in
`REFERENCE_RESULTS.md` and their original figures/JSON/CSV files are under
`reference_performance/`. A fresh notebook run writes a new complete bundle to Drive.

## Start here

1. Upload `QRGuard_ML_Colab.zip` to `MyDrive/QRGuard_ML_Colab.zip`.
2. For Structural, download the official QR-DN1.0 v2 and QR Codes in Surfaces
   v1 archives and place them at:
   - `MyDrive/QRGuard_ML_Data/structural/QR-DN1.0.zip`
   - `MyDrive/QRGuard_ML_Data/structural/qr_codes_in_surfaces.zip`
3. If available, copy labelled exact app captures to
   `MyDrive/QRGuard_ML_Data/structural/runtime_captures/`.
4. Open `01_Structural_Training_Colab.ipynb`, select a T4 GPU, and Run all.
5. Open `02_Semantic_Training_Colab.ipynb` and Run all. Kaggle may ask you to
   authenticate/accept the Malicious URLs dataset terms on first acquisition.
6. Complete outputs are copied to `MyDrive/QRGuard_ML_Results/`.

Raw third-party datasets are not redistributed in this source package because
they are large and governed by their source terms. Official URLs, DOI/licence,
expected byte sizes, SHA-256 hashes and acquisition code are included. That is
the reproducibility material; the notebooks fetch or verify the actual data.

## Honest camera gate

A QR can decode successfully while the image-integrity model cannot safely use
the camera frames. Decoding and Structural classification are different tasks.
Synthetic camera augmentation cannot prove performance on QRGuard's exact crop
pipeline, so Structural deployment remains `CANDIDATE ONLY` until the labelled
app-camera gate passes. The notebook still produces all tables and figures and
states exactly which gate is missing.

## Colour contract

Structural Training uses RGB, 224×224, `[0,1]` scaling and ImageNet RGB
normalisation. It does not use CMYK or Lab. See
`QRGuard/ml_training/COLOR_PIPELINE.md` for the exact coloured-QR generation,
camera colour-correction and serving parity contract.
