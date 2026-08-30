# Risk Decision Layer Performance — decision-2026.03-r01

Status: **PASSED; candidate not promoted**

The model was trained on 1,260 QRGuard-Mix-v2 rows and evaluated on a fixed,
cell-stratified 540-row holdout. The holdout covers six payload types crossed with
six gallery/live-camera evidence modes (36 cells). Runtime policy is applied during
evaluation, so open Wi-Fi floors and camera-abstention handling are not omitted.

## Main results

- ROC-AUC: 0.9818
- Blocked-tier precision: 0.9942
- Safe-tier false-negative rate: 0.0194
- Exact three-tier accuracy: 0.8778
- Security-impact policy acceptance: 0.9759
- Thresholds: Safe < 14; Warning < 55; Blocked >= 55

Exact tier and policy acceptance are both reported. For a dangerous URL, Warning is
counted as cautious (not Safe) but its Blocked recall is gated separately. For benign
content, Warning is reported as an exact-tier miss while only a false Block is treated
as a security-impact failure. Deterministic open-Wi-Fi, executable, and manipulation
cells retain exact-tier gates.

## Per-cell results

| Cell | n | Exact tier | Policy acceptance | Safe | Warning | Blocked |
|---|---:|---:|---:|---:|---:|---:|
| camera_clean_consensus_benign_url | 15 | 0.8667 | 1.0000 | 0.8667 | 0.1333 | 0.0000 |
| camera_clean_consensus_executable_uri | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| camera_clean_consensus_phishing_url | 15 | 0.8667 | 0.9333 | 0.0667 | 0.0667 | 0.8667 |
| camera_clean_consensus_plain_text | 15 | 0.9333 | 1.0000 | 0.9333 | 0.0667 | 0.0000 |
| camera_clean_consensus_wifi_open | 15 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| camera_clean_consensus_wifi_secure | 15 | 0.9333 | 1.0000 | 0.9333 | 0.0667 | 0.0000 |
| camera_tampered_consensus_benign_url | 15 | 0.9333 | 0.9333 | 0.0667 | 0.0000 | 0.9333 |
| camera_tampered_consensus_executable_uri | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| camera_tampered_consensus_phishing_url | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| camera_tampered_consensus_plain_text | 15 | 0.9333 | 0.9333 | 0.0667 | 0.0000 | 0.9333 |
| camera_tampered_consensus_wifi_open | 15 | 0.9333 | 0.9333 | 0.0000 | 0.0667 | 0.9333 |
| camera_tampered_consensus_wifi_secure | 15 | 0.9333 | 0.9333 | 0.0667 | 0.0000 | 0.9333 |
| camera_uncertain_abstain_benign_url | 15 | 0.2667 | 0.9333 | 0.2667 | 0.6667 | 0.0667 |
| camera_uncertain_abstain_executable_uri | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| camera_uncertain_abstain_phishing_url | 15 | 0.6667 | 1.0000 | 0.0000 | 0.3333 | 0.6667 |
| camera_uncertain_abstain_plain_text | 15 | 0.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| camera_uncertain_abstain_wifi_open | 15 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| camera_uncertain_abstain_wifi_secure | 15 | 0.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| gallery_adversarial_benign_url | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| gallery_adversarial_executable_uri | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| gallery_adversarial_phishing_url | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| gallery_adversarial_plain_text | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| gallery_adversarial_wifi_open | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| gallery_adversarial_wifi_secure | 15 | 0.9333 | 0.9333 | 0.0000 | 0.0667 | 0.9333 |
| gallery_clean_benign_url | 15 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| gallery_clean_executable_uri | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| gallery_clean_phishing_url | 15 | 0.8667 | 1.0000 | 0.0000 | 0.1333 | 0.8667 |
| gallery_clean_plain_text | 15 | 0.9333 | 1.0000 | 0.9333 | 0.0667 | 0.0000 |
| gallery_clean_wifi_open | 15 | 0.9333 | 0.9333 | 0.0000 | 0.9333 | 0.0667 |
| gallery_clean_wifi_secure | 15 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| gallery_tampered_benign_url | 15 | 0.8667 | 0.8667 | 0.0667 | 0.0667 | 0.8667 |
| gallery_tampered_executable_uri | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| gallery_tampered_phishing_url | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| gallery_tampered_plain_text | 15 | 0.9333 | 0.9333 | 0.0667 | 0.0000 | 0.9333 |
| gallery_tampered_wifi_open | 15 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.0000 |
| gallery_tampered_wifi_secure | 15 | 0.8667 | 0.8667 | 0.0667 | 0.0667 | 0.8667 |

## Reproducibility

The deployed weights, model fingerprints, thresholds, branch-cache fingerprints,
and complete metrics are stored beside this report. Generated charts are
`tier_confusion_matrix.png`, `score_distribution.png`, and `ablation.png`.
