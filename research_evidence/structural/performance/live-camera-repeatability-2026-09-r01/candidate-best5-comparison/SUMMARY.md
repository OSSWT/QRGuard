# Multi-frame production candidate replay

Source SHA-256: `859938e1eb44012cb268f25780cca25734955ba76facb66978f6d0e4ade6b3a3`

The best 5 geometry-ranked automatic crops in each session were evaluated together. A neutral non-URL payload isolates Structural behaviour; no decoded payload was stored.

## Result

- Correct session rate: 16.7%
- Rescan rate: 83.3%
- Clean false-Blocked rate: 0.0%
- Adversarial false-Safe rate: 0.0%
- Definitive decisions correct: clean 100.0%; adversarial 100.0%
- Pipeline latency: mean 42.2 ms; median 0.0 ms; P95 208 ms
- Definitive-session pipeline latency: mean 253.2 ms; median 194 ms; P95 558 ms

## Case x distance

| Case | Distance | >=256 px frames | Analysed | Outcomes |
|---|---|---:|---:|---|
| STR-ADV-NORMAL | near | 4 | 4 | {'rescan': 4, 'correct': 1} |
| STR-ADV-NORMAL | medium | 0 | 0 | {'rescan': 5} |
| STR-ADV-NORMAL | far | 0 | 0 | {'rescan': 5} |
| STR-CLN-ANGLE | near | 19 | 18 | {'correct': 4, 'rescan': 1} |
| STR-CLN-ANGLE | medium | 0 | 0 | {'rescan': 5} |
| STR-CLN-ANGLE | far | 0 | 0 | {'rescan': 5} |

A rescan is an intentional abstention, not a correct classification. This captured matrix used smaller QR crops than the promoted exact-app holdout, so it validates fail-closed acquisition behaviour but cannot replace the independent deployment gate.
