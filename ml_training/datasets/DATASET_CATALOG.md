# QRGuard ML dataset catalogue

This is the human-readable source of truth for the data behind the active
QRGuard stack. `DATASET_INVENTORY.json` is the matching machine-readable local
presence and hash audit. Large data are intentionally excluded from GitHub;
GitHub stores the recipes, contracts, provenance, citations, expected hashes,
and post-training QR demo assets.

## Verified state

The local audit verifies every required source, table, manifest, referenced
image, row count, byte size, and locked SHA-256 value. It also verifies the five
canonical private recovery/evidence archives under `04_Datasets`.

The active models are:

- Structural: `structural-r07-corrective-v1`
- Semantic: `semantic-2026.02`
- Decision layer: `decision-2026.03-r05`

## Structural data admitted to r07

| Dataset | Local canonical location | What is present | Role and split boundary | Origin / licence | GitHub policy |
|---|---|---|---|---|---|
| QR-DN1.0 v2 | `structural/downloads/qrdn/QR-DN1.0.zip` plus `processed/qrdn/manifest.csv` | Verified 1,025,545,184-byte archive; 6,750-row manifest | 4,500 official-train clean rows; 2,250 rows from 25 disjoint QR identities are external clean holdout. Optical distortion is not labelled tampering. | Mendeley Data, DOI `10.17632/t2bdr663ms.2`, CC BY 4.0 | Archive/cache ignored; URL, DOI, role, counts and hashes published |
| QR Codes on Different Surfaces v1 | `structural/downloads/qr_surfaces/qr_codes_in_surfaces.zip` plus `processed/qr_surfaces/` | Verified 384,232,282-byte archive; 67 accepted rectified real crops | Auxiliary clean training only. All photographs encode the same QR bitmap, so they provide no independent test identities. | Mendeley Data, DOI `10.17632/m6mfwc52vk.1`, CC BY 4.0 | Archive/cache ignored; provenance and hashes published |
| QRGuard exact-app captures v3 | `data/runtime_captures/manifest_v3.csv` and its session folders | 361 authoritative sessions/frames; every referenced crop and pixel hash verified | Camera: 100 clean, 100 adversarial, 100 tampered. Gallery: 21/20/20. Sixty paired test groups and ten quality conditions per camera class. Primary deployment-domain data. | QRGuard opt-in capture campaign; project-internal data | Private pixels ignored; schema, audit, aggregate counts and hashes published |
| Prepared Gallery references | `data/prepared_gallery_references/structural-2026.03-r01/` | 239 referenced images verified | Train/validation only: clean 59/20, adversarial 60/20, tampered 60/20. Fifty-nine locked-test references were excluded. | QRGuard capture campaign; project-internal data | Metadata only |
| Structural coverage development | `data/structural_coverage_development/2026-09-r01/` | 240 referenced crops verified | Versions 3/5/10, masks 0-7 and payload lengths 24/40/112 bytes. Development train/validation only. | QRGuard diagnostic capture; project-internal opt-in | Metadata only |
| Physical attack development | `data/structural_physical_attack_development/2026-09-r02/` | 130 admitted referenced crops verified | 80 clean plus 50 frames from ten attacks verified to survive the screen/camera channel. Twenty-two non-surviving attack sessions were quarantined. | QRGuard physical capture; project-internal opt-in | Metadata only |
| Acquisition quality development | `data/acquisition_quality_development/2026-09-r02/` | 90 admitted referenced clean crops verified | Exposure/module-scale hard negatives; train only and never reused as independent evaluation. | QRGuard diagnostic capture; project-internal opt-in | Metadata only |
| Consumed blind clean development | `data/structural_consumed_blind_development/2026-09-r01/` | 80 referenced crops verified | Dense-screen/SEM-11 hard negatives. The original holdout was opened; these rows can never be fresh blind evidence again. | QRGuard diagnostic capture; project-internal opt-in | Metadata only |
| Consumed verified attacks | `data/structural_consumed_blind_attack_development/r07-corrective-v1/` | Ten referenced frames from two surviving attacks verified | Corrective train-only hard positives; never promotion evidence. | QRGuard diagnostic capture; project-internal opt-in | Metadata only |
| Procedural topology and attacks | Rebuilt by `structural/src/structural_recipes.py` and `structural/src/train_local.py` | Not stored as another permanent image expansion | Includes standards-valid mask/version/error-correction topology counterfactuals plus grouped synthetic clean/tampered and FGSM/PGD samples. Parent identities stay in one split. | QRGuard deterministic generation | Code/config published; generated cache ignored |

The combined 14,240-row r07 manifest/image cache is intentionally absent after
workspace deduplication. It is reproducibly rebuilt from the retained canonical
inputs or restored from the locked Drive cache. The final manifest identity is
recorded in `configs/structural-r07-corrective-v1.json` as SHA-256
`8d02cb0caf51d555cafeac7d57f4b0f09dc9d4331e9cda905fe944413e585a28`.

## Structural data present but not admitted to training

| Dataset | State | Allowed use | Reason excluded |
|---|---|---|---|
| Dynamsoft QR selection | 73 Git-blob-verified source files; 232 annotated image crops and one detected video crop prepared locally | Acquisition/detection inspection only | No repository-wide data licence was recorded for the acquired QR subsets, and the data have no QRGuard Structural class ground truth |
| Consumed r07 fresh-blind pack | Source and locked reference ZIPs retained under `04_Datasets` and hash-verified | Diagnosis only | It has already been scored and cannot become blind again |
| Attack Calibration v1 | Source and reference ZIPs retained under `04_Datasets` and hash-verified | Controlled-release development calibration | It is disclosed development evidence, not independent promotion evidence |
| BarBeR / BoofCV / OQR / Sensors forged QR | Reference entries only unless separately acquired under verified terms | Future acquisition or holdout work as registered | Not silently added to the current training data |

## Semantic data admitted to semantic-2026.02

Semantic Training consumes decoded text/URLs, not camera pixels. All main
splits are grouped by registrable domain so the same domain cannot be counted
as an independent train and test identity.

| Source | Local canonical location | Exact local identity | Use | Origin / licence | GitHub policy |
|---|---|---|---|---|---|
| PhiUSIIL | `data/method1/phiusiil.csv` | 235,795 rows; SHA-256 `1511c42441eb0360b46c54aae4cf07c98c6affa898a2e205ac2cb65fb13dcfbf` | Primary labelled legitimate/phishing URL source; remapped to `0=benign`, `1=dangerous` | UCI dataset 967, DOI `10.1016/j.cose.2023.103545`, CC BY 4.0 | Data ignored; recipe, citation, counts and hash published |
| Malicious URLs | `data/method1/malicious_phish.csv` | 651,191 rows; SHA-256 `d83ce942075dd63ed4d11560cfdcd9d512caa3d680e292f22cab484e8f074d01` | `benign` becomes 0; phishing/defacement/malware become 1 | Kaggle `sid321axn/malicious-urls-dataset`, CC0 Public Domain on its data page | Data ignored; source and frozen hash published |
| Tranco top 150k | `data/method1/tranco_top150k.csv` | 150,000 rows; SHA-256 `b698a2686a0db066ccb3b0aeda2379791a2ca95466558d63a9fde9b6b2f79f26` | Benign registered-domain augmentation only | Tranco research ranking; cite DOI `10.14722/ndss.2019.23386` and its component attribution terms | Snapshot ignored; frozen hash published |
| QRGuard hard probes | Generated by `semantic/src/contract.py` | 61 hard-benign and 24 hard-phishing rows in the source catalogue; 45 separate acceptance cases | Targeted behavioural training/acceptance checks; exact acceptance cases are excluded from model fitting | QRGuard project-generated | Code and aggregate counts published |

The Tranco snapshot's permanent list ID was not recorded when it was acquired.
The exact local CSV is still frozen by SHA-256, but the missing permanent ID is
an explicit provenance limitation. A future refresh must save the permanent
Tranco list ID before it can replace this snapshot.

### Semantic processed data

| File | Rows | Purpose |
|---|---:|---|
| `combined_clean.parquet` | 1,017,689 | Conflict-cleaned and de-duplicated source pool after reserved acceptance cases are removed |
| `train.parquet` | 240,050 | Bounded, balanced domain-grouped training split including required hard probes |
| `validation.parquet` | 60,000 | Domain-disjoint calibration/model-selection split |
| `test.parquet` | 80,000 | Balanced independent registered-domain test split |
| `by_source/source_catalog_manifest.csv` | 5 source families | Inspection catalogue with per-source rows, file paths, official URLs and SHA-256 values |

All of these files exist locally and match the locked inventory hashes. They are
ignored by Git because they contain a large URL corpus; GitHub includes
`semantic/src/prepare_colab_data.py`, which reacquires and standardises the
three external sources.

## Decision-layer training data

`data/qrguard_mix_v2/manifest.csv` and `images/` are present and verified:

- 1,800 total samples: 1,260 train and 540 test in Decision r05.
- Manifest SHA-256:
  `6c30bba32aba6cd1b80ef21fe556db73ffc0f73ca0d19015c516dcdd6454cc16`.
- Every referenced image exists.
- It crosses benign/dangerous payloads with clean/manipulated image evidence,
  payload kinds and Gallery/Camera-style evidence cells.
- It trains the fusion/threshold layer; it is not a third image/text model.

Decision r05 remains frozen on the branch-signal fingerprint recorded in its
performance bundle. Before training a later Decision version against another
Structural model, regenerate `branch_signals.csv`; do not silently reuse its
older Structural fingerprint.

## GitHub versus local/Drive storage

| Stored in GitHub | Kept local or in Drive |
|---|---|
| Acquisition/preparation/training scripts | Large official archives |
| Dataset registry and licence decisions | Extracted source trees and processed parquet files |
| Manifest schemas and aggregate audits | Private exact-app captures and recovery ZIPs |
| Exact expected sizes and SHA-256 values | Rebuildable combined training image caches |
| Split/leakage policy and citations | Training checkpoints not needed by production |
| QR demo cards, expected outcomes and checksums | Private live-camera evidence |

This is intentional: cloning GitHub gives a reviewable and reproducible data
contract without publishing restricted/private rows or adding gigabytes of
derived files to source control.

## Re-run the audit

From the repository root:

```powershell
.venv\Scripts\python.exe scripts\audit_ml_datasets.py
.venv\Scripts\python.exe scripts\audit_ml_datasets.py --check
```

The audit output contains no wall-clock field; an unchanged workspace produces
the same file.
