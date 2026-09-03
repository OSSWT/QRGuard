# Structural dataset references

| Source | Admitted role | Current status |
|---|---|---|
| QR-DN1.0 v2 | clean training and independent clean holdout | downloaded, hash-verified and prepared |
| QR Codes on Different Surfaces v1 | auxiliary clean training only | downloaded, hash-verified and prepared |
| QRGuard real app captures | primary exact Gallery/Camera deployment evidence | 361 accepted sessions; 300 locked Camera rows and 60 Gallery/Camera pairs evaluated |
| Dynamsoft QR datasets | acquisition robustness inspection only | licence-quarantined; excluded from training/class metrics |
| BarBeR, BoofCV, OQR and Sensors forged QR | documented optional/conditional sources | not silently admitted |

The exact URLs and dataset IDs are in `../dataset_registry.csv`; licence and
redistribution decisions are in `../DATASET_LICENSES.md`. Procedurally generated
QRs are project data and are recorded under `../../generated_qr_codes/`.

Exact local paths, archive/manifest hashes, row counts and the distinction
between admitted, quarantined, consumed and regenerable data are in
`../../DATASET_CATALOG.md` and `../../DATASET_INVENTORY.json`.
