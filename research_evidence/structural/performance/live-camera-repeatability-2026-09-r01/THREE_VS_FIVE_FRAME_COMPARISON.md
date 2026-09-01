# Three-versus-five-frame Live Camera comparison

Date: 2026-09-01

This comparison replays the hash-locked 30-session / 150-frame physical-phone
diagnostic archive through the production Structural and Decision artifacts. It
does not retrain or tune either model. A neutral non-URL payload isolates image
acquisition and Structural consensus behaviour.

The proposed client keeps five geometry-ranked observations as a fallback pool,
but prepares, uploads and evaluates only the first three crops that meet the
existing 256 px deployment boundary. The five-frame baseline sends the whole
five-crop pool and lets the backend reject undersized crops.

| Metric | Five crops | Best three eligible crops |
|---|---:|---:|
| Correct sessions | 16.7% | 16.7% |
| Intentional rescan sessions | 83.3% | 83.3% |
| Clean false-Blocked | 0.0% | 0.0% |
| Adversarial false-Safe | 0.0% | 0.0% |
| Definitive clean decisions correct | 100.0% | 100.0% |
| Definitive adversarial decisions correct | 100.0% | 100.0% |
| Definitive-session pipeline median | 194 ms | 115 ms |
| Definitive-session pipeline mean | 253.2 ms | 155.8 ms |
| Definitive-session pipeline P95 | 558 ms | 320 ms |

The best-three policy preserved every diagnostic outcome while reducing the
definitive-session median pipeline time by 40.7% and mean time by 38.5%. These
wall-clock values are machine-load-sensitive; the paired replay is retained for
reproducibility. The high
rescan rate is unchanged because most original medium/far captures are below the
locked deployment scale; it is a fail-closed acquisition result, not a claimed
classification success rate.

The independent 120-row authoritative candidate-stack gate was also rerun after
the code change and passed unchanged: camera clean false-Blocked 0%, camera
adversarial Blocked recall 95%, camera tampered Blocked recall 100%, and paired
Camera/Gallery exact-verdict agreement 98.33%.

Evidence:

- `candidate-best5-comparison/`
- `candidate-best3-comparison/`
- `../../../decision/performance/candidate-stack-three-frame-2026-09-r02/`
