# Latest ML versions

## Active controlled-release set

| Component | Version | Status |
|---|---|---|
| Structural | **`structural-r07-corrective-v1`** | User-authorized controlled release for Gallery and Camera; formal fresh blind acceptance pending |
| Semantic | `semantic-2026.02` | Frozen accepted model |
| Decision | **`decision-2026.03-r05`** | Accepted; Safe < 26, Blocked >= 76 |
| Full stack | r07 + r05 | Local and Render production paths verified; controlled-release limitations remain disclosed |

The r07 controlled attack-calibration set contains 72 sessions and 360 validated
frames. Twenty-five of 48 planned attack cases survived the physical
screen-to-camera channel. On independent surviving attack bases, recall was 1.00
for low versions, 1.00 for medium versions and 0.8333 for high versions. Every
clean calibration base remained Safe. One dense high-version base required
Rescan because its observed module scale was below the fixed five-pixels-per-
module evidence floor; no analyzable surviving attack was returned as Safe.

This is development evidence, not a substitute for a new independent blind
acceptance. QRGuard therefore discloses r07 as a controlled release and applies
fail-closed runtime rules: inconclusive QR-image evidence requires Rescan, cannot
invoke Deep Check as a bypass, and cannot expose a proceed action.

Decision r05 remains unchanged. It recorded 0.9820 ROC-AUC, 0.9912 Blocked
precision, 0.0194 Safe-tier false-negative rate and 0.9759 policy acceptance on
the fixed 540-row holdout.

## Verification

- Backend: 452 passed, 3 conditional skips.
- Flutter analysis: no issues.
- Flutter tests: 104 passed.
- Android: signed `1.2.0+8012`, 73,462,225 bytes, SHA-256
  `c415337eed98e7d87517cd25c5523d251a3547b5b60277b07940e64f8243e64c`.
- Local and Render production-path health: unified r07 for Gallery and Camera.
- Remote demo smoke: 42/42 Gallery and 42/42 Camera-simulation outcomes matched
  across 84 successful requests.
- Production Web: `1.2.0+8012`; hosted APK SHA-256 matches the signed artifact.

## Rollback and evidence

- Immediate Structural rollback: `structural-2026.03-r01`, referenced by
  `deployment/rollback/structural-before-r07-controlled-release/ROLLBACK.json`.
- Frozen Semantic rollback boundary: `semantic-2026.02`.
- Decision rollback: `decision-2026.02`.
- r07 candidate evidence: `structural/performance/structural-r07-corrective-v1/`.
- Controlled calibration evidence:
  `../research_evidence/structural/performance/r07-corrective/`.

The canonical supervisor QR pack remains `datasets/qr_codes_demo/`. Physical
phone results must continue to be reported separately from automated API checks.
See `CURRENT_CHECKPOINT.md` and `deployment/model_registry.json` for the exact
runtime, formal-gate and external-deployment boundaries.
