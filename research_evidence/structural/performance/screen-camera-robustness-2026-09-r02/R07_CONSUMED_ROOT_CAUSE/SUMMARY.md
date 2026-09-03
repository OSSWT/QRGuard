# Consumed Structural holdout diagnosis

This report is development diagnosis only. It cannot be used for promotion.

## Outcome

- Classification: `single_frame_instability_rescued_by_temporal_consensus`
- Clean session consensus safe: True
- Clean single-frame false blocks: 1/80
- Elevated clean layouts: 2
- Model or threshold mutation: none

## Elevated clean layouts

| Case | Version | Modules | Mask | Payload bytes | p min / median / max | Blocked frames |
|---|---:|---:|---:|---:|---:|---:|
| R7B-07-B1579A | 3 | 29 | 0 | 24 | 0.002 / 0.172 / 0.770 | 1 |
| R7B-24-90D5AF | 10 | 57 | 4 | 97 | 0.042 / 0.118 / 0.251 | 0 |

## Guardrails

- Correlations are descriptive and do not establish causation.
- The capture is consumed development evidence and cannot promote a model.
- Layout, display, camera, luminance and module scale remain confounded in one pass.
