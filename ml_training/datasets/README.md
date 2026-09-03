# Dataset layout and data contract

```text
datasets/
  references/   shared registry/citations plus Structural and Semantic indexes
  structural/
    downloads/   source archives (not tracked)
    raw/         immutable extracted source data (not tracked)
    processed/   QRGuard crops and labels (not tracked)
  semantic/
    raw/         immutable URL corpora (not tracked)
    processed/   canonical conflict-free grouped splits (not tracked)
  holdout/
    raw/         independent robustness sources (not tracked)
    processed/   fixed evaluation inputs (not tracked)
  generated_qr_codes/  generator provenance and model-exposure registry
  qr_codes_demo/       post-training demonstration/evaluation QR pack
  manifests/     schemas/templates; generated manifests are not tracked
```

`references/` is the single source for both branches. It contains the shared
dataset registry, licences and BibTeX plus explicit Structural and Semantic
indexes. `generated_qr_codes/` records QR images created by this project,
including legacy, procedural and capture-reference datasets.

`qr_codes_demo/` is deliberately separate from training and locked evaluation.
It demonstrates the already deployed stack and must remain `demo_only` in every
future manifest.

Structural images are classified through their authoritative manifests. Do not
materialize a second `pictures_by_source` hardlink catalog: it duplicates the
visible workspace without adding training provenance and can be regenerated for
temporary inspection when needed.

For Semantic rows, open the generated `by_source/` catalog under the current
Semantic processed run. It separates `PHIUSIIL_UCI`, `MALICIOUS_URLS_KAGGLE`,
`TRANCO_BENIGN`, and the two explicitly labelled QRGuard-derived hard-probe
groups. Its `source_catalog_manifest.csv` records the official URL and row
count for every source; the canonical train/validation/test files remain the
authoritative training inputs.

Every processed Structural row must include:

- `sample_path`, `label`, `source_dataset`, `source_version`
- `capture_session`, `physical_qr`, `payload_hash`, `device`
- `medium`, `environment`, `is_real_camera`, `is_exact_app_crop`
- `split`, `parent_sample`, `sha256`, `licence`

Structural v3 additionally requires `quality_condition`, `quality_severity`,
`image_source`, `paired_group`, and `is_authoritative`. Quality is metadata and
an evaluation slice; it never replaces the clean/adversarial/tampered target.
Gallery and Camera rows for one case share `paired_group`, while burst frames
share one `capture_session` and contribute only one authoritative model input.

Every processed Semantic row must include:

- `url`, `label`, `source_dataset`, `source_version`
- `canonical_url`, `registrable_domain`, `split`
- `conflict_status`, `sha256`, `licence`

Splits are group-disjoint. Augmented derivatives inherit the parent group. A
video or burst contributes many frames but one independent capture session.
