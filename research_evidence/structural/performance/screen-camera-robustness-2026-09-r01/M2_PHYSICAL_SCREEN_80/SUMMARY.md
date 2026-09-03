# Live-camera repeatability results

Source SHA-256: `4da992cfcb477526ed45843f5a70e702e23fb7d964dd7bb255ef23754e465153`

Model: `structural-2026.03-r01` / `3529df95acaba3f5fe29f7369670de5c0c8c06d60f90e8a2e1959584967c5ad4`

## Integrity

- Sessions / frames: 36 / 180
- Crops whose independently decoded payload hash matched: 178/180
- Globally unique crops: 180; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 75.6% | 0.0% |
| Session first frame | 69.4% | 0.0% |
| Majority of five verdicts | 77.8% | 0.0% |
| Median of five risk scores | 77.8% | 0.0% |

Quality abstention rate: 0.0%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| RC-LAYOUT-4470 | screen-80 | {'marginal': 15} | {'blocked': 2, 'warning': 5, 'safe': 8} | 0.389 / 0.511 / 0.642 | {'blocked': 2, 'safe': 1} | {'warning': 1, 'safe': 2} | {'safe': 3} |
| RC-LAYOUT-4471 | screen-80 | {'marginal': 15} | {'blocked': 15} | 0.597 / 0.937 / 0.980 | {'blocked': 3} | {'blocked': 3} | {'blocked': 3} |
| RC-LAYOUT-4472 | screen-80 | {'marginal': 15} | {'safe': 2, 'blocked': 13} | 0.182 / 0.757 / 0.976 | {'safe': 2, 'blocked': 1} | {'blocked': 3} | {'blocked': 3} |
| RC-MASK-0 | screen-80 | {'usable': 1, 'marginal': 14} | {'safe': 4, 'blocked': 11} | 0.103 / 0.682 / 0.833 | {'safe': 1, 'blocked': 2} | {'safe': 1, 'blocked': 2} | {'safe': 1, 'blocked': 2} |
| RC-MASK-1 | screen-80 | {'usable': 1, 'marginal': 14} | {'safe': 2, 'blocked': 13} | 0.046 / 0.722 / 0.899 | {'safe': 1, 'blocked': 2} | {'blocked': 3} | {'blocked': 3} |
| RC-MASK-2 | screen-80 | {'marginal': 15} | {'safe': 3, 'blocked': 12} | 0.179 / 0.675 / 0.783 | {'safe': 1, 'blocked': 2} | {'safe': 1, 'blocked': 2} | {'safe': 1, 'blocked': 2} |
| RC-MASK-3 | screen-80 | {'marginal': 15} | {'safe': 6, 'blocked': 9} | 0.241 / 0.560 / 0.775 | {'safe': 1, 'blocked': 2} | {'blocked': 3} | {'blocked': 3} |
| RC-MASK-4 | screen-80 | {'marginal': 15} | {'blocked': 15} | 0.531 / 0.849 / 0.956 | {'blocked': 3} | {'blocked': 3} | {'blocked': 3} |
| RC-MASK-5 | screen-80 | {'marginal': 15} | {'blocked': 14, 'safe': 1} | 0.054 / 0.682 / 0.820 | {'blocked': 3} | {'blocked': 3} | {'blocked': 3} |
| RC-MASK-6 | screen-80 | {'marginal': 15} | {'safe': 2, 'blocked': 13} | 0.210 / 0.799 / 0.895 | {'safe': 1, 'blocked': 2} | {'blocked': 3} | {'blocked': 3} |
| RC-MASK-7 | screen-80 | {'marginal': 15} | {'safe': 9, 'blocked': 5, 'warning': 1} | 0.144 / 0.486 / 0.687 | {'safe': 2, 'blocked': 1} | {'safe': 3} | {'safe': 3} |
| RC-VERSION-4 | screen-80 | {'marginal': 15} | {'safe': 1, 'blocked': 14} | 0.484 / 0.859 / 0.954 | {'safe': 1, 'blocked': 2} | {'blocked': 3} | {'blocked': 3} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
