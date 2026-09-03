# Live-camera repeatability results

Source SHA-256: `02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4`

Model: `structural-2026.09-soup-alpha-0p25` / `ac8a5f43ff09a6627240a2e2e6afa5e7b29fc997ef3be11d4471925bcaba0c05`

## Integrity

- Sessions / frames: 24 / 120
- Crops whose independently decoded payload hash matched: 38/120
- Globally unique crops: 120; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 25.6% | 0.0% |
| Session first frame | 33.3% | 0.0% |
| Majority of five verdicts | 27.8% | 0.0% |
| Median of five risk scores | 27.8% | 0.0% |

Quality abstention rate: 6.7%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| ACQ-CLN-V10-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.008 / 0.017 / 0.023 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.012 / 0.018 / 0.041 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.009 / 0.012 / 0.021 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.019 / 0.063 / 0.122 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.034 / 0.049 / 0.076 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.030 / 0.038 / 0.059 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.034 / 0.119 / 0.123 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-05-USERINFO | screen-100-brightness-30 | {'usable': 4, 'marginal': 1} | {'blocked': 1, 'safe': 3, 'warning': 1} | 0.129 / 0.245 / 0.368 | {'blocked': 1} | {'safe': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-80-brightness-50 | {'usable': 4, 'marginal': 1} | {'safe': 2, 'blocked': 3} | 0.032 / 0.112 / 0.360 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.014 / 0.049 / 0.211 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.021 / 0.311 / 0.364 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-11-PLAIN-TEXT | screen-80-brightness-50 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.015 / 0.017 / 0.030 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-ADV-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.985 / 0.994 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.987 / 0.993 / 0.995 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.991 / 0.994 / 0.996 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-100 | {'marginal': 2, 'usable': 3} | {'warning': 2, 'blocked': 1, 'safe': 2} | 0.058 / 0.163 / 0.815 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.799 / 0.982 / 0.984 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-80-brightness-50 | {'usable': 4, 'marginal': 1} | {'blocked': 4, 'warning': 1} | 0.738 / 0.807 / 0.851 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-100 | {'usable': 4, 'marginal': 1} | {'blocked': 3, 'safe': 2} | 0.024 / 0.945 / 0.965 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-30 | {'usable': 1, 'marginal': 4} | {'blocked': 1, 'warning': 2, 'safe': 2} | 0.063 / 0.077 / 0.735 | {'blocked': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-80-brightness-50 | {'marginal': 5} | {'safe': 4, 'warning': 1} | 0.144 / 0.360 / 0.434 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-TMP-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
