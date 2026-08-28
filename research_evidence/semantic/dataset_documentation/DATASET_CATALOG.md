# Semantic dataset catalogue

The canonical processed data remains under
`ml_training/datasets/semantic/processed/semantic-2026.02/`. This folder contains
only catalogues and audit snapshots, so training and Colab paths remain stable.

| Source | Role | Catalogued rows | Licence/access | Canonical file |
|---|---|---:|---|---|
| Malicious URLs (Kaggle) | multi-class URL source mapped to benign/dangerous | 632,923 | dataset page/Kaggle terms | `.../by_source/MALICIOUS_URLS_KAGGLE/MALICIOUS_URLS_KAGGLE_semantic_rows.parquet` |
| PhiUSIIL (UCI 967) | primary labelled phishing/benign source | 234,683 | CC BY 4.0 | `.../by_source/PHIUSIIL_UCI/PHIUSIIL_UCI_semantic_rows.parquet` |
| Tranco | benign registered-domain augmentation | 149,998 | research list terms; preserve exact list/date | `.../by_source/TRANCO_BENIGN/TRANCO_BENIGN_semantic_rows.parquet` |
| QRGuard hard-benign probes | behavioural acceptance and difficult benign cases | 61 | project internal | `.../by_source/QRGuard_DERIVED_HARD_BENIGN/` |
| QRGuard hard-phishing probes | behavioural acceptance phishing cases | 24 | project internal | `.../by_source/QRGuard_DERIVED_HARD_PHISH/` |

The `...` prefix above is
`ml_training/datasets/semantic/processed/semantic-2026.02`.

## Cleaning audit

| Stage | Rows |
|---|---:|
| Input | 1,037,076 |
| Invalid removed | 7 |
| Conflicting-label rows handled | 7,913 across 3,942 keys |
| Duplicate rows removed | 11,463 |
| Clean output | 1,017,693 |
| Behavioural acceptance rows reserved | 4 |
| Final training-pool output | 1,017,689 |

## Evaluated composition

- Train: 240,050 rows
- Validation: 60,000 rows
- Independent registered-domain-grouped test: 80,000 rows
- Behavioural acceptance: 45 probes

Source identity is preserved in every run so per-source performance can be
reported. The manifests beside this file contain exact row counts and SHA-256
values without duplicating the parquet files.
