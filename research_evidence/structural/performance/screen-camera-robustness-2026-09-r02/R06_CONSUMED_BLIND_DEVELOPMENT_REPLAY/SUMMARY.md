# M8 consumed holdout development replay

Gate passed: **False**

Candidate model SHA-256: `7cb75a2af193b395d03e195c197c53f4433c9f64df1581837ee45601f866a5e2`

## Per-class Version-band results

| Class | Version band | Sessions | Rescan | Class metric |
|---|---|---:|---:|---:|
| clean | low_v1_v3 | 5 | 0.0% | 0.0% |
| clean | medium_v4_v6 | 5 | 0.0% | 0.0% |
| clean | high_v7_plus | 6 | 33.3% | 33.3% |
| adversarial | low_v1_v3 | 1 | 0.0% | 0.0% |
| adversarial | medium_v4_v6 | 0 | 100.0% | 0.0% |
| adversarial | high_v7_plus | 1 | 0.0% | 100.0% |
| tampered | low_v1_v3 | 5 | 0.0% | 100.0% |
| tampered | medium_v4_v6 | 5 | 0.0% | 100.0% |
| tampered | high_v7_plus | 6 | 0.0% | 100.0% |

## Gate failures

- clean/high_v7_plus: rescan rate 0.3333 exceeds 0.2000
- clean/high_v7_plus: false-Blocked rate 0.3333 exceeds 0.0500
- adversarial/low_v1_v3: 1 verified surviving physical attacks; require 5
- adversarial/low_v1_v3: block recall 0.0000 below 0.8000
- adversarial/medium_v4_v6: 0 verified surviving physical attacks; require 5
- adversarial/medium_v4_v6: rescan rate 1.0000 exceeds 0.2000
- adversarial/medium_v4_v6: block recall 0.0000 below 0.8000
- adversarial/high_v7_plus: 1 verified surviving physical attacks; require 5
- clean layout probability span 0.9827 exceeds 0.1500

This audit never copies artifacts, changes production defaults, pushes, or deploys.
