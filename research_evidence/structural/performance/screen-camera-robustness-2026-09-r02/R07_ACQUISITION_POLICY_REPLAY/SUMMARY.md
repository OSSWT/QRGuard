# Live-camera repeatability results

Source SHA-256: `02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4`

Model: `structural-2026.09-r07` / `a1d1a4f749032ac26a3abe0f3f7aafb83c9c146de7e193a9ca49bc6d05058fee`

## Integrity

- Sessions / frames: 24 / 120
- Crops whose independently decoded payload hash matched: 40/120
- Globally unique crops: 120; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 11.1% | 0.0% |
| Session first frame | 16.7% | 0.0% |
| Majority of five verdicts | 11.1% | 0.0% |
| Median of five risk scores | 11.1% | 0.0% |

Quality abstention rate: 0.0%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| ACQ-CLN-V10-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-100 | {'usable': 5} | {'warning': 4, 'safe': 1} | 0.001 / 0.001 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-30 | {'usable': 5} | {'warning': 5} | 0.001 / 0.001 / 0.001 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-80-brightness-50 | {'usable': 5} | {'warning': 5} | 0.001 / 0.001 / 0.001 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.001 / 0.001 / 0.001 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-05-USERINFO | screen-100-brightness-30 | {'usable': 5} | {'blocked': 1, 'warning': 4} | 0.001 / 0.001 / 0.001 | {'blocked': 1} | {'warning': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-80-brightness-50 | {'usable': 5} | {'blocked': 4, 'warning': 1} | 0.000 / 0.001 / 0.001 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.000 / 0.000 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-11-PLAIN-TEXT | screen-80-brightness-50 | {'marginal': 1, 'usable': 4} | {'warning': 1, 'safe': 4} | 0.001 / 0.002 / 0.002 | {'warning': 1} | {'safe': 1} | {'safe': 1} |
| STR-ADV-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.884 / 0.977 / 0.994 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.949 / 0.974 / 0.992 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.983 / 0.988 / 0.993 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-100 | {'usable': 5} | {'warning': 5} | 0.001 / 0.001 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-30 | {'usable': 5} | {'warning': 5} | 0.001 / 0.001 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-OVEREXP | screen-80-brightness-50 | {'usable': 5} | {'warning': 5} | 0.001 / 0.001 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-100 | {'usable': 4, 'marginal': 1} | {'warning': 5} | 0.000 / 0.001 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-30 | {'usable': 3, 'marginal': 2} | {'warning': 5} | 0.001 / 0.001 / 0.001 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-80-brightness-50 | {'marginal': 5} | {'warning': 5} | 0.001 / 0.002 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-TMP-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.999 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
