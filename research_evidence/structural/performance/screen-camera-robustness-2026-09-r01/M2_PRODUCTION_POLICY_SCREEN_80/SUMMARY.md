# Multi-frame production candidate replay

Source SHA-256: `4da992cfcb477526ed45843f5a70e702e23fb7d964dd7bb255ef23754e465153`

The best 3 geometry-ranked automatic crops in each session were evaluated together. A neutral non-URL payload isolates Structural behaviour; no decoded payload was stored.

## Result

- Correct session rate: 27.8%
- Rescan rate: 8.3%
- Clean false-Blocked rate: 63.9%
- Adversarial false-Safe rate: 0.0%
- Definitive decisions correct: clean 30.3%; adversarial 0.0%
- Pipeline latency: mean 147.4 ms; median 149.0 ms; P95 170 ms
- Definitive-session pipeline latency: mean 160.8 ms; median 150 ms; P95 170 ms

## Case x condition

| Case | Distance | >=256 px frames | Analysed | Outcomes |
|---|---|---:|---:|---|
| RC-LAYOUT-4470 | screen-80 | 9 | 9 | {'correct': 3} |
| RC-LAYOUT-4471 | screen-80 | 9 | 9 | {'false_block': 3} |
| RC-LAYOUT-4472 | screen-80 | 9 | 9 | {'false_block': 3} |
| RC-MASK-0 | screen-80 | 9 | 9 | {'correct': 1, 'false_block': 2} |
| RC-MASK-1 | screen-80 | 9 | 9 | {'false_block': 3} |
| RC-MASK-2 | screen-80 | 9 | 9 | {'correct': 1, 'false_block': 2} |
| RC-MASK-3 | screen-80 | 9 | 9 | {'correct': 2, 'false_block': 1} |
| RC-MASK-4 | screen-80 | 9 | 9 | {'false_block': 3} |
| RC-MASK-5 | screen-80 | 0 | 0 | {'rescan': 3} |
| RC-MASK-6 | screen-80 | 9 | 9 | {'correct': 1, 'false_block': 2} |
| RC-MASK-7 | screen-80 | 9 | 9 | {'false_block': 1, 'correct': 2} |
| RC-VERSION-4 | screen-80 | 9 | 9 | {'false_block': 3} |

A rescan is an intentional abstention, not a correct classification. This captured matrix used smaller QR crops than the promoted exact-app holdout, so it validates fail-closed acquisition behaviour but cannot replace the independent deployment gate.
