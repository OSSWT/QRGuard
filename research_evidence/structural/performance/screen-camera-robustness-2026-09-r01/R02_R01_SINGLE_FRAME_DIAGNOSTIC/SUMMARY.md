# Live-camera repeatability results

Source SHA-256: `a69f83022e8af591e9d09f31cdbedb924ad41cf5e9d951feac24ef6577775d58`

Model: `structural-2026.09-r01` / `200a5ff02dbe47623ca738902bdcfe16b97bfbc507398e91dce9845aa7581ac9`

## Integrity

- Sessions / frames: 48 / 240
- Crops whose independently decoded payload hash matched: 194/240
- Globally unique crops: 240; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 0.0% | 0.0% |
| Session first frame | 0.0% | 0.0% |
| Majority of five verdicts | 0.0% | 0.0% |
| Median of five risk scores | 0.0% | 0.0% |

Quality abstention rate: 0.0%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| PHY-ADV-F-01 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.848 / 0.919 / 0.990 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-02 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.967 / 0.979 / 0.994 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-03 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.980 / 0.992 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-04 | screen-80 | {'marginal': 2, 'usable': 3} | {'blocked': 5} | 0.978 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-05 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.926 / 0.997 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-06 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.997 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-07 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.999 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-08 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.904 / 0.981 / 0.992 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-09 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-10 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-11 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-12 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-13 | screen-80 | {'marginal': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-14 | screen-80 | {'usable': 1, 'marginal': 4} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-15 | screen-80 | {'usable': 3, 'marginal': 2} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-F-16 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-01 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.977 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-02 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.997 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-03 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.997 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-04 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.998 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-05 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.979 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-06 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.998 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-07 | screen-80 | {'marginal': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-08 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.984 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-09 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-10 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-11 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.966 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-12 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-13 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-14 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-15 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-ADV-X-16 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| PHY-CLN-01 | screen-80 | {'marginal': 5} | {'safe': 5} | 0.014 / 0.094 / 0.254 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-02 | screen-80 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.003 / 0.004 / 0.022 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-03 | screen-80 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.002 / 0.002 / 0.044 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-04 | screen-80 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.001 / 0.001 / 0.004 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-05 | screen-80 | {'marginal': 5} | {'safe': 5} | 0.004 / 0.008 / 0.015 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-06 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-07 | screen-80 | {'marginal': 5} | {'safe': 5} | 0.001 / 0.002 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-08 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.003 / 0.005 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-09 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.002 / 0.003 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-10 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-11 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.002 / 0.005 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-12 | screen-80 | {'marginal': 4, 'usable': 1} | {'safe': 5} | 0.003 / 0.003 / 0.012 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-13 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-14 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.003 / 0.004 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-15 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.002 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| PHY-CLN-16 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.003 / 0.003 | {'safe': 1} | {'safe': 1} | {'safe': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
