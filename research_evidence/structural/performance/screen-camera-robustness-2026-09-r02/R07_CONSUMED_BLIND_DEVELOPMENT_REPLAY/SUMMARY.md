# M8 consumed holdout development replay

Gate passed: **False**

Candidate model SHA-256: `a1d1a4f749032ac26a3abe0f3f7aafb83c9c146de7e193a9ca49bc6d05058fee`

## Per-class Version-band results

| Class | Version band | Sessions | Rescan | Class metric |
|---|---|---:|---:|---:|
| clean | low_v1_v3 | 5 | 0.0% | 0.0% |
| clean | medium_v4_v6 | 5 | 0.0% | 0.0% |
| clean | high_v7_plus | 6 | 16.7% | 0.0% |
| adversarial | low_v1_v3 | 1 | 0.0% | 0.0% |
| adversarial | medium_v4_v6 | 0 | 100.0% | 0.0% |
| adversarial | high_v7_plus | 1 | 0.0% | 0.0% |
| tampered | low_v1_v3 | 5 | 0.0% | 100.0% |
| tampered | medium_v4_v6 | 5 | 0.0% | 100.0% |
| tampered | high_v7_plus | 6 | 0.0% | 100.0% |

## Gate failures

- adversarial/low_v1_v3: 1 verified surviving physical attacks; require 5
- adversarial/low_v1_v3: block recall 0.0000 below 0.8000
- adversarial/medium_v4_v6: 0 verified surviving physical attacks; require 5
- adversarial/medium_v4_v6: rescan rate 1.0000 exceeds 0.2000
- adversarial/medium_v4_v6: block recall 0.0000 below 0.8000
- adversarial/high_v7_plus: 1 verified surviving physical attacks; require 5
- adversarial/high_v7_plus: block recall 0.0000 below 0.8000

This audit never copies artifacts, changes production defaults, pushes, or deploys.
