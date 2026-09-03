# Multi-frame production candidate replay

Source SHA-256: `a69f83022e8af591e9d09f31cdbedb924ad41cf5e9d951feac24ef6577775d58`

The best 5 geometry-ranked automatic crops in each session were evaluated together. A neutral non-URL payload isolates Structural behaviour; no decoded payload was stored.

## Result

- Correct session rate: 100.0%
- Rescan rate: 0.0%
- Clean false-Blocked rate: 0.0%
- Adversarial false-Safe rate: 0.0%
- Definitive decisions correct: clean 100.0%; adversarial 100.0%
- Pipeline latency: mean 195.3 ms; median 187.5 ms; P95 203 ms
- Definitive-session pipeline latency: mean 195.3 ms; median 187.5 ms; P95 203 ms

## Case x condition

| Case | Distance | >=256 px frames | Analysed | Outcomes |
|---|---|---:|---:|---|
| PHY-ADV-F-01 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-02 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-03 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-04 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-05 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-06 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-07 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-08 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-09 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-10 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-11 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-12 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-13 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-14 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-15 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-F-16 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-01 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-02 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-03 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-04 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-05 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-06 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-07 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-08 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-09 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-10 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-11 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-12 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-13 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-14 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-15 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-ADV-X-16 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-01 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-02 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-03 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-04 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-05 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-06 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-07 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-08 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-09 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-10 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-11 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-12 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-13 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-14 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-15 | screen-80 | 5 | 5 | {'correct': 1} |
| PHY-CLN-16 | screen-80 | 5 | 5 | {'correct': 1} |

A rescan is an intentional abstention, not a correct classification. This captured matrix used smaller QR crops than the promoted exact-app holdout, so it validates fail-closed acquisition behaviour but cannot replace the independent deployment gate.
