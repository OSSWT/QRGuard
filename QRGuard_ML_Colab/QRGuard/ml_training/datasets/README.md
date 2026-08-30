# Dataset layout and data contract

```text
datasets/
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
  pictures_by_source/  source-prefixed hardlink catalog for inspection (not tracked)
  manifests/     schemas/templates; generated manifests are not tracked
```

For a human-readable folder of QR pictures, open
[`pictures_by_source/`](pictures_by_source/README.md). It contains
`QRDN1.0/`, `QR_SURFACES/`, and `DYNAMSOFT/`; every filename starts with its
source name and `catalog_manifest.csv` maps each alias back to its authoritative
path, hash, split, label, and official URL. The catalog is an inspection view;
training must continue to use the branch manifests.

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
