# Deployed single-frame baseline replay

Source SHA-256: `859938e1eb44012cb268f25780cca25734955ba76facb66978f6d0e4ade6b3a3`

Model: `structural-2026.03-r01` / `3529df95acaba3f5fe29f7369670de5c0c8c06d60f90e8a2e1959584967c5ad4`

## Integrity

- Sessions / frames: 30 / 150
- Crops whose independently decoded payload hash matched: 0/150
- Globally unique crops: 150; duplicate instances: 0
- Raw decoded payload text stored: no

The collector had already decoded and hash-locked the expected payload on the
phone. The 0/150 line means desktop OpenCV could not re-decode these rectified
second-generation screen captures; it does not mean the captured QR identity
was unverified.

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 13.3% | 2.7% |
| Session first frame | 13.3% | 6.7% |
| Majority of five verdicts | 13.3% | 0.0% |
| Median of five risk scores | 13.3% | 0.0% |

Quality abstention rate: 40.0%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| STR-ADV-NORMAL | near | {'marginal': 20, 'usable': 5} | {'blocked': 23, 'safe': 2} | 0.053 / 0.987 / 1.000 | {'blocked': 4, 'safe': 1} | {'blocked': 5} | {'blocked': 5} |
| STR-ADV-NORMAL | medium | {'marginal': 24, 'usable': 1} | {'blocked': 25} | 0.766 / 0.996 / 1.000 | {'blocked': 5} | {'blocked': 5} | {'blocked': 5} |
| STR-ADV-NORMAL | far | {'marginal': 19, 'usable': 6} | {'blocked': 25} | 0.633 / 0.969 / 0.998 | {'blocked': 5} | {'blocked': 5} | {'blocked': 5} |
| STR-CLN-ANGLE | near | {'unusable': 25} | {'warning': 25} | n/a | {'warning': 5} | {'warning': 5} | {'safe': 5} |
| STR-CLN-ANGLE | medium | {'unusable': 20, 'marginal': 5} | {'warning': 20, 'blocked': 5} | 0.697 / 0.709 / 0.886 | {'warning': 4, 'blocked': 1} | {'warning': 4, 'blocked': 1} | {'safe': 4, 'blocked': 1} |
| STR-CLN-ANGLE | far | {'unusable': 15, 'marginal': 10} | {'warning': 15, 'safe': 5, 'blocked': 5} | 0.198 / 0.522 / 0.998 | {'warning': 3, 'safe': 1, 'blocked': 1} | {'warning': 3, 'safe': 1, 'blocked': 1} | {'safe': 4, 'blocked': 1} |

## Interpretation constraint

These two QR references are exposed diagnostic cases, not an independent
deployment test set. They identified the live-camera failure mode and supported
the candidate design. The selected rule subsequently passed the independent
120-row held-out candidate-stack gate; see `candidate-multiframe/SUMMARY.md` and
the Decision evidence bundle.
