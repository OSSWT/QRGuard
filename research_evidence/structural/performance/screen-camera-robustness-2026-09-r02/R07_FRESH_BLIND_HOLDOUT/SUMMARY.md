# M8 blinded Structural acceptance

Gate passed: **False**

Candidate model SHA-256: `71a86dec83c5c63dd3ac4b83705f403c183c9efe8822a424e072a7b95c555033`

## Per-class Version-band results

| Class | Version band | Sessions | Rescan | Class metric |
|---|---|---:|---:|---:|
| clean | low_v1_v3 | 5 | 0.0% | 0.0% |
| clean | medium_v4_v6 | 5 | 0.0% | 0.0% |
| clean | high_v7_plus | 6 | 0.0% | 0.0% |
| adversarial | low_v1_v3 | 2 | 0.0% | 100.0% |
| adversarial | medium_v4_v6 | 3 | 0.0% | 100.0% |
| adversarial | high_v7_plus | 1 | 0.0% | 100.0% |
| tampered | low_v1_v3 | 5 | 0.0% | 100.0% |
| tampered | medium_v4_v6 | 5 | 0.0% | 100.0% |
| tampered | high_v7_plus | 6 | 0.0% | 100.0% |

## Gate failures

- adversarial/low_v1_v3: 2 verified surviving physical attacks; require 5
- adversarial/medium_v4_v6: 3 verified surviving physical attacks; require 5
- adversarial/high_v7_plus: 1 verified surviving physical attacks; require 5
- clean layout probability span 0.2109 exceeds 0.1500

This audit never copies artifacts, changes production defaults, pushes, or deploys.
