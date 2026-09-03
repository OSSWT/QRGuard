# Live-camera repeatability results

Source SHA-256: `02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4`

Model: `structural-2026.09-soup-alpha-0p75` / `a850e6b3cca59a0bbffbe63c81e656c072df366ed3cd64e2ed7c32ca70a8f0a9`

## Integrity

- Sessions / frames: 24 / 120
- Crops whose independently decoded payload hash matched: 38/120
- Globally unique crops: 120; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 38.9% | 0.0% |
| Session first frame | 38.9% | 0.0% |
| Majority of five verdicts | 50.0% | 0.0% |
| Median of five risk scores | 50.0% | 0.0% |

Quality abstention rate: 2.5%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| ACQ-CLN-V10-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.009 / 0.022 / 0.049 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.015 / 0.022 / 0.065 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.009 / 0.014 / 0.031 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.017 / 0.051 / 0.115 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.033 / 0.047 / 0.074 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.025 / 0.038 / 0.044 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.024 / 0.092 / 0.140 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-05-USERINFO | screen-100-brightness-30 | {'usable': 4, 'marginal': 1} | {'blocked': 1, 'safe': 3, 'warning': 1} | 0.157 / 0.300 / 0.428 | {'blocked': 1} | {'safe': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-80-brightness-50 | {'usable': 5} | {'safe': 2, 'blocked': 3} | 0.021 / 0.089 / 0.840 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-100 | {'usable': 4, 'marginal': 1} | {'safe': 4, 'warning': 1} | 0.021 / 0.151 / 0.475 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-30 | {'usable': 5} | {'safe': 2, 'blocked': 3} | 0.044 / 0.760 / 0.792 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-11-PLAIN-TEXT | screen-80-brightness-50 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.015 / 0.024 / 0.055 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-ADV-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.998 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.998 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-100 | {'usable': 5} | {'blocked': 3, 'safe': 2} | 0.065 / 0.895 / 0.951 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.957 / 0.997 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.905 / 0.921 / 0.980 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-100 | {'usable': 4, 'marginal': 1} | {'blocked': 3, 'safe': 2} | 0.027 / 0.994 / 0.996 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-30 | {'usable': 3, 'marginal': 2} | {'blocked': 3, 'safe': 2} | 0.084 / 0.915 / 0.940 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-UNDEREXP | screen-80-brightness-50 | {'marginal': 5} | {'warning': 1, 'blocked': 4} | 0.885 / 0.907 / 0.953 | {'warning': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
