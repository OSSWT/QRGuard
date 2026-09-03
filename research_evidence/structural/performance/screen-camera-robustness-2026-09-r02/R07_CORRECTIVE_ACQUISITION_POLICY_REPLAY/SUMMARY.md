# Live-camera repeatability results

Source SHA-256: `02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4`

Model: `structural-r07-corrective-v1` / `71a86dec83c5c63dd3ac4b83705f403c183c9efe8822a424e072a7b95c555033`

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

Quality abstention rate: 0.8%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| ACQ-CLN-V10-LONG | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V10-LONG | screen-80-brightness-50 | {'usable': 5} | {'safe': 5} | 0.001 / 0.002 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-100 | {'usable': 5} | {'warning': 4, 'safe': 1} | 0.002 / 0.003 / 0.003 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-30 | {'usable': 5} | {'warning': 5} | 0.002 / 0.002 / 0.003 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| ACQ-CLN-V14-LONG | screen-80-brightness-50 | {'usable': 5} | {'warning': 5} | 0.002 / 0.002 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.001 / 0.002 / 0.002 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-05-USERINFO | screen-100-brightness-30 | {'usable': 5} | {'blocked': 1, 'warning': 4} | 0.001 / 0.002 / 0.002 | {'blocked': 1} | {'warning': 1} | {'safe': 1} |
| SEM-05-USERINFO | screen-80-brightness-50 | {'usable': 5} | {'blocked': 4, 'warning': 1} | 0.001 / 0.001 / 0.002 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-100 | {'usable': 5} | {'safe': 5} | 0.001 / 0.003 / 0.006 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-30 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.007 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| SEM-11-PLAIN-TEXT | screen-80-brightness-50 | {'marginal': 1, 'usable': 4} | {'warning': 1, 'safe': 4} | 0.001 / 0.006 / 0.006 | {'warning': 1} | {'safe': 1} | {'safe': 1} |
| STR-ADV-NORMAL | screen-100-brightness-100 | {'usable': 4, 'marginal': 1} | {'blocked': 4, 'warning': 1} | 0.825 / 0.906 / 0.960 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.826 / 0.927 / 0.964 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-ADV-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.911 / 0.951 / 0.969 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-100 | {'usable': 5} | {'warning': 5} | 0.002 / 0.002 / 0.003 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-30 | {'usable': 5} | {'warning': 5} | 0.002 / 0.002 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-OVEREXP | screen-80-brightness-50 | {'usable': 5} | {'warning': 5} | 0.002 / 0.002 / 0.003 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-100 | {'usable': 4, 'marginal': 1} | {'warning': 5} | 0.001 / 0.001 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-30 | {'usable': 3, 'marginal': 2} | {'warning': 5} | 0.001 / 0.002 / 0.002 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-CLN-UNDEREXP | screen-80-brightness-50 | {'marginal': 5} | {'warning': 5} | 0.002 / 0.003 / 0.003 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| STR-TMP-NORMAL | screen-100-brightness-100 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-100-brightness-30 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| STR-TMP-NORMAL | screen-80-brightness-50 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
