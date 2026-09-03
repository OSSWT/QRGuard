# Dataset licence and access register

Status is intentionally conservative. A source is not admitted to training until
its exact downloaded version has been checked.

| Dataset | Current licence/access finding | Training decision |
|---|---|---|
| QR-DN1.0 v2 | CC BY 4.0 on Mendeley Data | Permitted with attribution; auxiliary camera/noise only |
| QR Codes on Surfaces v1 | CC BY 4.0 on Mendeley Data | Permitted with attribution; separate real originals from synthetic data |
| ZVZ-real / ZVZ-synth | ABBYY repository code is Apache-2.0; linked dataset terms are not stated as repository-wide terms | Quarantine images until the downloaded archive has an explicit data licence; detector/acquisition evaluation only |
| Barcode-30k | Paper documents 30,000 synthetic barcode/QR segmentation images; no verified dataset licence/download record | Reference only; do not download into training without exact archive terms |
| EgoQR | Paper describes an internally collected 528-image/697-QR benchmark; no verified public data licence | Method and evaluation-design reference only; not an available training source |
| BarBeR | Account required; aggregated component datasets | Verify component terms after download before training |
| Dynamsoft datasets | Public repository; no repository-wide licence found in the acquired revision | Downloaded files remain quarantined; acquisition robustness inspection only, never training/class metrics |
| BoofCV QR benchmark | Public benchmark page and downloads | Verify redistribution terms; reserve as independent evaluation |
| OQR | USENIX paper/artifact availability | Use templates only after artifact terms are recorded; locally recaptured images are project data |
| Sensors 2025 genuine/forged | Available from corresponding author on reasonable request | Do not claim possession until written access is received |
| PhiUSIIL | CC BY 4.0 via UCI | Permitted with attribution |
| Malicious URLs (Kaggle) | Subject to the dataset page/Kaggle terms | Retain locally; do not redistribute archive |
| Tranco | Research ranking service | Record exact list ID/date and cite the NDSS paper |
| QRGuard consumed M8 clean replay | Project-internal opt-in captures; original holdout has been unblinded | Clean crops only for r07 development; never promotion evidence; do not redistribute |

`dataset_registry.csv` is the machine-readable source of truth. Archive hashes and
retrieval dates will be added after each successful acquisition.
