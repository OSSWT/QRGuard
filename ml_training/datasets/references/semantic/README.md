# Semantic dataset references

| Source | Admitted role | Current measured catalogue |
|---|---|---:|
| PhiUSIIL (UCI dataset 967) | primary labelled phishing/legitimate URLs | 234,683 rows |
| Malicious URLs (Kaggle) | benign/phishing/defacement/malware URL source | 632,923 rows |
| Tranco | registered-domain-grouped benign augmentation | 149,998 rows |
| QRGuard hard-benign probes | behavioural acceptance | 61 rows |
| QRGuard hard-phishing probes | behavioural acceptance | 24 rows |

The canonical `semantic-2026.02` cleaning output contains 1,017,693 rows before
the four reserved behavioural cases are excluded from the 1,017,689-row
training pool. Its measured train/validation/independent-test composition is
240,050 / 60,000 / 80,000 rows, with 45 behavioural acceptance probes.

The exact URLs and dataset IDs are in `../dataset_registry.csv`; licence and
redistribution decisions are in `../DATASET_LICENSES.md`.

The three frozen standardised source files are stored locally under
`data/method1/`; the active processed pool/splits are under
`ml_training/datasets/semantic/processed/semantic-2026.02/`. Both locations are
Git-ignored. Their exact row counts and SHA-256 identities are published in
`../../DATASET_INVENTORY.json` and explained in `../../DATASET_CATALOG.md`.

Known limitation: the retained Tranco CSV is hash-locked, but its permanent
Tranco list ID was not recorded at acquisition. Do not invent one; a future
replacement must preserve its permanent ID.
