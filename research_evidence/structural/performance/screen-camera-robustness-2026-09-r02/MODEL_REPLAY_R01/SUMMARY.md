# Live-camera repeatability results

Source SHA-256: `02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4`

Model: `structural-2026.03-r01` / `3529df95acaba3f5fe29f7369670de5c0c8c06d60f90e8a2e1959584967c5ad4`

## Integrity

- Sessions / frames: 24 / 120
- Crops whose independently decoded payload hash matched: 38/120
- Globally unique crops: 120; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 30.0% | 0.0% |
| Session first frame | 22.2% | 0.0% |
| Majority of five verdicts | 33.3% | 0.0% |
| Median of five risk scores | 33.3% | 0.0% |

Quality abstention rate: 0.0%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| ACQ-CLN-V10-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.000 / 0.000 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.000 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.000 / 0.000 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.000 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.000 / 0.000 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.000 / 0.000 / 0.000 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.016 / 0.030 / 0.087 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-05-USERINFO | screen-100-brightness-30 | {'usable': 5} | {'blocked': 2, 'safe': 3} | 0.032 / 0.172 / 0.654 | {'blocked': 1} | {'safe': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-80-brightness-50 | {'usable': 5} | {'safe': 2, 'blocked': 3} | 0.009 / 0.020 / 0.513 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.765 / 0.860 / 0.909 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.695 / 0.973 / 0.981 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-11-PLAIN-TEXT | screen-80-brightness-50 | {'marginal': 1, 'usable': 4} | {'safe': 1, 'blocked': 4} | 0.040 / 0.835 / 0.949 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.688 / 0.984 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.739 / 0.995 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.785 / 0.839 / 0.925 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.000 / 0.001 / 0.007 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-30 | {'usable': 5} | {'safe': 2, 'blocked': 3} | 0.003 / 0.975 / 0.994 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.002 / 0.003 / 0.008 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-100 | {'usable': 4, 'marginal': 1} | {'safe': 5} | 0.000 / 0.038 / 0.136 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-30 | {'usable': 3, 'marginal': 2} | {'safe': 5} | 0.000 / 0.001 / 0.013 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-80-brightness-50 | {'marginal': 5} | {'safe': 5} | 0.004 / 0.096 / 0.200 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-TMP-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
