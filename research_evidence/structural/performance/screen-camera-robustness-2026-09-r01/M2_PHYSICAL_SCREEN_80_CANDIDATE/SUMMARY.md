# Live-camera repeatability results

Source SHA-256: `4da992cfcb477526ed45843f5a70e702e23fb7d964dd7bb255ef23754e465153`

Model: `structural-2026.09-r01` / `200a5ff02dbe47623ca738902bdcfe16b97bfbc507398e91dce9845aa7581ac9`

## Integrity

- Sessions / frames: 36 / 180
- Crops whose independently decoded payload hash matched: 178/180
- Globally unique crops: 180; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 16.1% | 0.0% |
| Session first frame | 11.1% | 0.0% |
| Majority of five verdicts | 11.1% | 0.0% |
| Median of five risk scores | 11.1% | 0.0% |

Quality abstention rate: 0.0%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| RC-LAYOUT-4470 | screen-80 | {'marginal': 15} | {'safe': 15} | 0.024 / 0.065 / 0.437 | {'safe': 3} | {'safe': 3} | {'safe': 3} |
| RC-LAYOUT-4471 | screen-80 | {'marginal': 15} | {'blocked': 8, 'safe': 7} | 0.143 / 0.529 / 0.969 | {'blocked': 2, 'safe': 1} | {'safe': 1, 'blocked': 2} | {'safe': 1, 'blocked': 2} |
| RC-LAYOUT-4472 | screen-80 | {'marginal': 15} | {'safe': 14, 'blocked': 1} | 0.012 / 0.112 / 0.900 | {'safe': 3} | {'safe': 3} | {'safe': 3} |
| RC-MASK-0 | screen-80 | {'usable': 1, 'marginal': 14} | {'safe': 14, 'blocked': 1} | 0.008 / 0.142 / 0.607 | {'safe': 3} | {'safe': 3} | {'safe': 3} |
| RC-MASK-1 | screen-80 | {'usable': 1, 'marginal': 14} | {'safe': 13, 'blocked': 2} | 0.004 / 0.227 / 0.610 | {'safe': 3} | {'safe': 3} | {'safe': 3} |
| RC-MASK-2 | screen-80 | {'marginal': 15} | {'safe': 14, 'blocked': 1} | 0.030 / 0.255 / 0.685 | {'safe': 3} | {'safe': 3} | {'safe': 3} |
| RC-MASK-3 | screen-80 | {'marginal': 15} | {'safe': 15} | 0.024 / 0.042 / 0.143 | {'safe': 3} | {'safe': 3} | {'safe': 3} |
| RC-MASK-4 | screen-80 | {'marginal': 15} | {'blocked': 4, 'safe': 11} | 0.092 / 0.318 / 0.989 | {'blocked': 1, 'safe': 2} | {'blocked': 1, 'safe': 2} | {'blocked': 1, 'safe': 2} |
| RC-MASK-5 | screen-80 | {'marginal': 15} | {'safe': 14, 'blocked': 1} | 0.027 / 0.343 / 0.660 | {'safe': 3} | {'safe': 3} | {'safe': 3} |
| RC-MASK-6 | screen-80 | {'marginal': 15} | {'safe': 11, 'blocked': 4} | 0.022 / 0.359 / 0.816 | {'safe': 3} | {'safe': 3} | {'safe': 3} |
| RC-MASK-7 | screen-80 | {'marginal': 15} | {'safe': 8, 'blocked': 7} | 0.019 / 0.286 / 0.897 | {'safe': 2, 'blocked': 1} | {'safe': 2, 'blocked': 1} | {'safe': 2, 'blocked': 1} |
| RC-VERSION-4 | screen-80 | {'marginal': 15} | {'safe': 15} | 0.005 / 0.047 / 0.145 | {'safe': 3} | {'safe': 3} | {'safe': 3} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
