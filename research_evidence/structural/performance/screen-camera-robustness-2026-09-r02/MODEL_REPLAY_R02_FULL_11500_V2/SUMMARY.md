# Live-camera repeatability results

Source SHA-256: `02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4`

Model: `structural-2026.09-r02` / `0f24cc8aaa7a36e3157d0b5ff6eb2d38c673316c779c04b22954f591e4ef2a03`

## Integrity

- Sessions / frames: 24 / 120
- Crops whose independently decoded payload hash matched: 38/120
- Globally unique crops: 120; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 21.1% | 0.0% |
| Session first frame | 22.2% | 0.0% |
| Majority of five verdicts | 27.8% | 0.0% |
| Median of five risk scores | 22.2% | 0.0% |

Quality abstention rate: 4.2%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| ACQ-CLN-V10-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.005 / 0.009 / 0.012 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.007 / 0.010 / 0.022 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.005 / 0.007 / 0.011 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.012 / 0.045 / 0.079 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.021 / 0.028 / 0.048 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.019 / 0.021 / 0.040 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.021 / 0.056 / 0.078 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-05-USERINFO | screen-100-brightness-30 | {'usable': 5} | {'blocked': 1, 'safe': 4} | 0.060 / 0.207 / 0.452 | {'blocked': 1} | {'safe': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-80-brightness-50 | {'usable': 4, 'marginal': 1} | {'safe': 2, 'blocked': 3} | 0.020 / 0.081 / 0.261 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.009 / 0.015 / 0.058 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.010 / 0.061 / 0.106 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-11-PLAIN-TEXT | screen-80-brightness-50 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.008 / 0.010 / 0.028 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-ADV-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.968 / 0.986 / 0.993 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.972 / 0.985 / 0.989 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.980 / 0.987 / 0.991 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-100 | {'usable': 5} | {'safe': 4, 'blocked': 1} | 0.039 / 0.359 / 0.702 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-30 | {'marginal': 1, 'usable': 4} | {'warning': 1, 'blocked': 4} | 0.912 / 0.964 / 0.968 | {'warning': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-80-brightness-50 | {'usable': 3, 'marginal': 2} | {'blocked': 2, 'warning': 2, 'safe': 1} | 0.502 / 0.710 / 0.730 | {'blocked': 1} | {'blocked': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-100 | {'usable': 4, 'marginal': 1} | {'blocked': 3, 'safe': 2} | 0.019 / 0.869 / 0.931 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-30 | {'marginal': 3, 'usable': 2} | {'warning': 1, 'safe': 4} | 0.042 / 0.197 / 0.400 | {'warning': 1} | {'safe': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-80-brightness-50 | {'marginal': 5} | {'safe': 5} | 0.065 / 0.200 / 0.371 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| STR-TMP-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.997 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.997 / 0.998 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.997 / 0.997 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
