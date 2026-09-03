# QR structural coverage audit

Policy: `structural-coverage-2026.09-r01`

Gate passed: **False**; promotion blocked: **True**.

## Existing exact-app test coverage

| Class | Groups | Versions | Masks | Payload byte range |
|---|---:|---|---|---:|
| adversarial | 20 | {8: 20} | {2: 5, 3: 5, 4: 3, 5: 2, 6: 5} | 68-73 |
| clean | 20 | {7: 1, 8: 18, 10: 1} | {1: 1, 2: 8, 3: 6, 4: 2, 6: 2, 7: 1} | 68-111 |
| tampered | 20 | {8: 20} | {2: 5, 3: 9, 4: 2, 5: 1, 6: 2, 7: 1} | 68-73 |

## New low-Version evidence

- Physical production-policy clean false-Blocked rate: 63.9%.
- Physical rescan rate: 8.3%.
- Demo masked branch errors (SEM-05-style): 0.
- Digital forced-mask probability span: 0.506.
- Physical forced-mask probability span: 0.364.

## Blocking failures

- clean: version band low_v1_v3 has 0, requires 5
- clean: version band medium_v4_v6 has 0, requires 5
- clean: mask 0 has 0, requires 2
- clean: mask 1 has 1, requires 2
- clean: mask 5 has 0, requires 2
- clean: mask 7 has 1, requires 2
- clean: payload bin short_1_32 has 0, requires 5
- clean: payload bin long_97_plus has 1, requires 5
- adversarial: version band low_v1_v3 has 0, requires 5
- adversarial: version band medium_v4_v6 has 0, requires 5
- adversarial: mask 0 has 0, requires 2
- adversarial: mask 1 has 0, requires 2
- adversarial: mask 7 has 0, requires 2
- adversarial: payload bin short_1_32 has 0, requires 5
- adversarial: payload bin long_97_plus has 0, requires 5
- tampered: version band low_v1_v3 has 0, requires 5
- tampered: version band medium_v4_v6 has 0, requires 5
- tampered: mask 0 has 0, requires 2
- tampered: mask 1 has 0, requires 2
- tampered: mask 5 has 1, requires 2
- tampered: mask 7 has 1, requires 2
- tampered: payload bin short_1_32 has 0, requires 5
- tampered: payload bin long_97_plus has 0, requires 5
- low-Version physical clean false-Blocked rate 0.6389 exceeds 0.0500
- digital forced-mask probability span 0.5056 exceeds 0.1500
- physical forced-mask probability span 0.3637 exceeds 0.1500

## Conclusion

The failure is not explained by 29x29 or payload length alone. The existing exact-app test set is concentrated in high-Version QR layouts; legal mask/layout differences already move the clean score materially, and screen-camera artefacts amplify that content shortcut. Multi-frame voting repeats the bias and therefore is not a sufficient fix.

The next Structural candidate must satisfy every Version band, every mask and every payload-length bin for all three classes, then pass the branch-level demo audit before promotion.
