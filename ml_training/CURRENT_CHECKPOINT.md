# Current ML checkpoint

## Outcome

`structural-r07-corrective-v1` is installed in the local production runtime and
deployed to the production Render API as a user-authorized controlled release.
Semantic `semantic-2026.02` and Decision
`decision-2026.03-r05` remain unchanged. The Structural candidate is not recorded
as formally promoted because a new candidate-bound independent blind acceptance
is still pending.

| Component | Runtime version | Status |
|---|---|---|
| Structural | `structural-r07-corrective-v1` | Controlled Gallery/Camera runtime; local and Render production paths verified |
| Semantic | `semantic-2026.02` | Frozen accepted runtime |
| Decision | `decision-2026.03-r05` | Accepted runtime; Safe < 26 and Blocked >= 76 |

## Artifact identity

- Structural ONNX: 44,702,737 bytes; SHA-256
  `71a86dec83c5c63dd3ac4b83705f403c183c9efe8822a424e072a7b95c555033`.
- Structural temperature: `0.6445590340070313`.
- Signed Android release: `1.2.0+8012`, 73,462,225 bytes; SHA-256
  `c415337eed98e7d87517cd25c5523d251a3547b5b60277b07940e64f8243e64c`.
- Android signer certificate SHA-256:
  `ce47b65dab21523731dfd76a414068ad95dcce3e1ee02a54e80b04552191c1ec`.

## Runtime safety policy

- Camera uses quality-ranked, exposure-diverse temporal evidence and three-frame
  Structural consensus.
- Quality checks run before Structural inference.
- Dense QR evidence requires at least 5.0 observed pixels per module.
- Poor focus, motion, glare, exposure or insufficient detail returns Rescan
  instead of Safe.
- A Structural Rescan cannot be bypassed by Deep Check or a proceed action.
- Confirmed non-clean Structural evidence remains at least Blocked.

## Controlled calibration result

- 72 sessions and 360 frames passed the capture contract.
- 25/48 attack cases survived the independent physical-channel check.
- Clean false-block rate was 0.00 in low, medium and high version bands.
- Independent attack-base recall was 1.00 low, 1.00 medium and 0.8333 high.
- One dense V14/73-module base required Rescan because the observed crop detail
  was below the frozen evidence floor.
- No analyzable surviving attack was returned as Safe.

These measurements are development-only. They do not claim universal coverage
across every phone, display, printer, lighting condition or future attack.

## Verification

- Backend regression: 452 passed, 3 conditional skips.
- r07 backend safety subset: 106 passed, 2 conditional skips.
- Flutter analyzer: no issues.
- Flutter tests: 104 passed.
- Production Web and signed Android builds: passed.
- Local Uvicorn health: `unified=structural-r07-corrective-v1`, sources Gallery
  and Camera.
- Production API health: `unified=structural-r07-corrective-v1`, sources Gallery
  and Camera.
- Production demo smoke: 42/42 Gallery and 42/42 Camera-simulation verdicts
  matched their intended outcomes across 84 HTTP 200 responses.
- Production Web reports `1.2.0+8012`; the hosted APK is 73,462,225 bytes and its
  SHA-256 matches the signed release artifact exactly.

## Rollback

The exact pre-r07 runtime remains available from the canonical
`structural-2026.03-r01` source artifacts and Git. The small rollback manifest at
`deployment/rollback/structural-before-r07-controlled-release/ROLLBACK.json`
records all four file hashes. No duplicate 44.7 MB rollback binary is stored.

External deployment status is recorded in `deployment/model_registry.json`.
Remote API health, Web version, inference smoke and hosted-APK checks have passed.
