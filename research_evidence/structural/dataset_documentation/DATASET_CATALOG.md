# Structural dataset catalogue

Large data is intentionally kept at its canonical path under
`ml_training/datasets/structural/`. This catalogue records what is actually used,
what is evaluation-only, and what is still required.

| Dataset | Status and role | Verified volume | Licence/access | Canonical path or source |
|---|---|---:|---|---|
| QR-DN1.0 v2 | admitted clean training data plus external clean holdout | 6,750 images: 4,500 official train, 2,250 official test; 50/25 disjoint identities | CC BY 4.0 | `ml_training/datasets/structural/processed/qrdn/`; DOI `10.17632/t2bdr663ms.2` |
| QR Codes on Different Surfaces v1 | auxiliary clean train only | 92 photos, 67 accepted crops; one shared QR bitmap | CC BY 4.0 | `ml_training/datasets/structural/processed/qr_surfaces/`; DOI `10.17632/m6mfwc52vk.1` |
| QRGuard procedural examples | admitted clean/adversarial/tampered grouped examples | candidate composition: 900 train per procedural class; 180 validation and 180 grouped test per class where applicable | project-generated | `ml_training/datasets/structural/processed/structural-2026.02/` |
| QRGuard runtime captures | mandatory final deployment evidence | currently 0 exact app-crop sessions; target at least 100 sessions/class and 20 independent test groups/class | project internal | `data/runtime_captures/` |
| Dynamsoft challenging QR data | quarantined acquisition holdout only; never training or class metrics | 73 Git-verified source files, 90,378,510 bytes; 232 image crops and 1 video crop accepted | no repository-wide licence found | `ml_training/datasets/holdout/` |
| BarBeR | possible auxiliary clean source | publisher reports 8,748 images and 9,818 annotations across barcode types | account required; component terms must be verified | official BarBeR site |
| BoofCV QR benchmark | reserve for independent robustness holdout | not admitted | verify redistribution terms | official BoofCV benchmark |
| OQR templates | adversarial source material; recapture locally before use | not admitted | verify artifact terms | USENIX Security 2026 artifact page |
| Sensors 2025 forged QR data | possible auxiliary tampered source | paper reports 5,000 samples | request from authors | DOI `10.3390/s25133855` |

## Candidate composition (`structural-2026.02`)

| Split | Clean | Adversarial | Tampered | Total |
|---|---:|---:|---:|---:|
| Train | 4,567 | 900 | 900 | 6,367 |
| Validation | 1,080 | 180 | 180 | 1,440 |
| Grouped synthetic test | 180 | 180 | 180 | 540 |
| QR-DN external clean holdout | 2,250 | 0 | 0 | 2,250 |

## Integrity checks

- QR-DN1.0 archive: 1,025,545,184 bytes; SHA-256
  `1f175a62239646bd7d6b179245cb0970c03b179c2baf1a5e8e59ba0b156cdf61`.
- QR Surfaces archive: 384,232,282 bytes; SHA-256
  `706352654a744217b6853c77362f4a32cc318d941b715423948ba2108aae7523`.
- QR-DN optical/camera noise is labelled clean acquisition variation; it is not
  re-labelled as tampering.
- Surface photos share one QR bitmap and therefore contribute no independent test
  identities.
- Dynamsoft remains outside training and class metrics until licence and QRGuard
  labels are established.

The snapshot audits under `manifests/` document these decisions without copying
the gigabyte-scale archives or generated images.
