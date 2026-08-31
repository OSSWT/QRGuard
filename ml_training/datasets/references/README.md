# QRGuard dataset references

This is the single reference entry point for both trained branches. It records
source identity, access conditions, licences, citations, hashes and each
dataset's admitted role without redistributing restricted source archives.

- [`structural/README.md`](structural/README.md) lists image, camera, generated
  and acquisition-holdout sources used by Structural training and evaluation.
- [`semantic/README.md`](semantic/README.md) lists URL/payload corpora and
  QRGuard behavioural probes used by Semantic training and acceptance checks.
- [`dataset_registry.csv`](dataset_registry.csv) is the machine-readable shared
  registry. Its `branch` column is the authoritative Structural/Semantic split.
- [`SOURCES.md`](SOURCES.md) contains verified source and acquisition notes.
- [`DATASET_LICENSES.md`](DATASET_LICENSES.md) contains redistribution and use
  decisions.
- [`REFERENCES.bib`](REFERENCES.bib) is the report-ready citation database.

Generated QR images and demo-only QR cards are catalogued separately under
`../generated_qr_codes/` and `../qr_codes_demo/`; they are not external dataset
references.
