# Multi-frame production candidate replay

Source SHA-256: `02a8fcafbcaad9e6b1058f02efb0a5ab56faffa8ce268173c98db07e6a1e93e4`

The best 5 geometry-ranked automatic crops in each session were evaluated together. A neutral non-URL payload isolates Structural behaviour; no decoded payload was stored.

## Result

- Correct session rate: 100.0%
- Rescan rate: 0.0%
- Clean false-Blocked rate: 0.0%
- Adversarial false-Safe rate: 0.0%
- Definitive decisions correct: clean 100.0%; adversarial 100.0%
- Pipeline latency: mean 985.1 ms; median 1144.5 ms; P95 1601 ms
- Definitive-session pipeline latency: mean 985.1 ms; median 1144.5 ms; P95 1601 ms

## Case x condition

| Case | Distance | >=256 px frames | Analysed | Outcomes |
|---|---|---:|---:|---|
| ACQ-CLN-V10-LONG | screen-100-brightness-100 | 5 | 5 | {'correct': 1} |
| ACQ-CLN-V10-LONG | screen-100-brightness-30 | 5 | 5 | {'correct': 1} |
| ACQ-CLN-V10-LONG | screen-80-brightness-50 | 5 | 5 | {'correct': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-100 | 5 | 5 | {'correct': 1} |
| ACQ-CLN-V14-LONG | screen-100-brightness-30 | 5 | 5 | {'correct': 1} |
| ACQ-CLN-V14-LONG | screen-80-brightness-50 | 5 | 5 | {'correct': 1} |
| SEM-05-USERINFO | screen-100-brightness-100 | 5 | 5 | {'correct': 1} |
| SEM-05-USERINFO | screen-100-brightness-30 | 5 | 5 | {'correct': 1} |
| SEM-05-USERINFO | screen-80-brightness-50 | 5 | 5 | {'correct': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-100 | 5 | 5 | {'correct': 1} |
| SEM-11-PLAIN-TEXT | screen-100-brightness-30 | 5 | 5 | {'correct': 1} |
| SEM-11-PLAIN-TEXT | screen-80-brightness-50 | 5 | 5 | {'correct': 1} |
| STR-ADV-NORMAL | screen-100-brightness-100 | 5 | 5 | {'correct': 1} |
| STR-ADV-NORMAL | screen-100-brightness-30 | 5 | 5 | {'correct': 1} |
| STR-ADV-NORMAL | screen-80-brightness-50 | 5 | 5 | {'correct': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-100 | 5 | 5 | {'correct': 1} |
| STR-CLN-OVEREXP | screen-100-brightness-30 | 5 | 5 | {'correct': 1} |
| STR-CLN-OVEREXP | screen-80-brightness-50 | 5 | 5 | {'correct': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-100 | 5 | 5 | {'correct': 1} |
| STR-CLN-UNDEREXP | screen-100-brightness-30 | 5 | 5 | {'correct': 1} |
| STR-CLN-UNDEREXP | screen-80-brightness-50 | 5 | 5 | {'correct': 1} |
| STR-TMP-NORMAL | screen-100-brightness-100 | 5 | 5 | {'correct': 1} |
| STR-TMP-NORMAL | screen-100-brightness-30 | 5 | 5 | {'correct': 1} |
| STR-TMP-NORMAL | screen-80-brightness-50 | 5 | 5 | {'correct': 1} |

A rescan is an intentional abstention, not a correct classification. This captured matrix used smaller QR crops than the promoted exact-app holdout, so it validates fail-closed acquisition behaviour but cannot replace the independent deployment gate.
