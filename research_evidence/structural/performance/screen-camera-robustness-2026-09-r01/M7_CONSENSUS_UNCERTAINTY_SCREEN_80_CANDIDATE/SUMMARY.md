# Multi-frame production candidate replay

Source SHA-256: `4da992cfcb477526ed45843f5a70e702e23fb7d964dd7bb255ef23754e465153`

The best 3 geometry-ranked automatic crops in each session were evaluated together. A neutral non-URL payload isolates Structural behaviour; no decoded payload was stored.

## Result

- Correct session rate: 83.3%
- Rescan rate: 16.7%
- Clean false-Blocked rate: 0.0%
- Adversarial false-Safe rate: 0.0%
- Definitive decisions correct: clean 100.0%; adversarial 0.0%
- Pipeline latency: mean 648.5 ms; median 626.5 ms; P95 879 ms
- Definitive-session pipeline latency: mean 719.4 ms; median 633.0 ms; P95 879 ms

## Case x condition

| Case | Distance | >=256 px frames | Analysed | Outcomes |
|---|---|---:|---:|---|
| RC-LAYOUT-4470 | screen-80 | 9 | 9 | {'correct': 3} |
| RC-LAYOUT-4471 | screen-80 | 9 | 9 | {'correct': 2, 'rescan': 1} |
| RC-LAYOUT-4472 | screen-80 | 9 | 9 | {'correct': 3} |
| RC-MASK-0 | screen-80 | 9 | 9 | {'correct': 3} |
| RC-MASK-1 | screen-80 | 9 | 9 | {'correct': 3} |
| RC-MASK-2 | screen-80 | 9 | 9 | {'correct': 3} |
| RC-MASK-3 | screen-80 | 9 | 9 | {'correct': 3} |
| RC-MASK-4 | screen-80 | 9 | 9 | {'rescan': 1, 'correct': 2} |
| RC-MASK-5 | screen-80 | 0 | 0 | {'rescan': 3} |
| RC-MASK-6 | screen-80 | 9 | 9 | {'correct': 3} |
| RC-MASK-7 | screen-80 | 9 | 9 | {'rescan': 1, 'correct': 2} |
| RC-VERSION-4 | screen-80 | 9 | 9 | {'correct': 3} |

A rescan is an intentional abstention, not a correct classification. This captured matrix used smaller QR crops than the promoted exact-app holdout, so it validates fail-closed acquisition behaviour but cannot replace the independent deployment gate.
