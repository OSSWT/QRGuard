# Structural preprocessing candidate screen

No transform in this report changes the runtime. Promotion requires an independent holdout after any selected implementation.

| Candidate | Physical clean FP | Physical mask span | Camera clean FP | Camera adv recall | Camera tamper recall | Pass |
|---|---:|---:|---:|---:|---:|---|
| baseline | 75.6% | 0.364 | 0.0% | 95.0% | 100.0% | False |
| grayscale | 13.3% | 0.578 | 0.0% | 10.0% | 0.0% | False |
| gaussian_0_75 | 14.4% | 0.425 | 10.0% | 95.0% | 100.0% | False |
| gaussian_1_25 | 1.1% | 0.098 | 15.0% | 95.0% | 100.0% | False |
| median_3 | 56.7% | 0.472 | 15.0% | 95.0% | 100.0% | False |
| lattice_box | 2.2% | 0.123 | 50.0% | 85.0% | 95.0% | False |
| gray_gaussian_0_75 | 15.0% | 0.251 | 0.0% | 10.0% | 0.0% | False |

Passing candidates: `[]`.

A transform that makes clean screen crops look normal but also removes adversarial or tampering evidence is rejected. If none passes, the next action is balanced retraining rather than a preprocessing override.
