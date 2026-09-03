# Structural r05 Colab audit and r06 readiness

Date: 2026-09-02 (Asia/Kuala_Lumpur)

## r05 candidate identity

- Version: `structural-2026.09-r05`
- Run ID: `colab-r05-topology-counterfactual-v1`
- Imported result ZIP SHA-256: `f448e41055e566b55b7c54aeb9170e1cc4821d987b370a7bb8961abde2d3a687`
- Best checkpoint SHA-256: `295326bd72d1ef68c91cb4f25341dc569b6dee032571ed82c56bb671c3d45224`
- FP32 ONNX SHA-256: `a78084377b445510f73a8f5748fff04dd09fbc9f73aeb093bdad57f524049fa1`
- Locked config SHA-256: `1ff38596f2b528871b9b84c34701355df802e2228dba0ec2ddf5ea72d2608cab`
- Locked manifest SHA-256: `d079321d615db5d3faa3d95a643ed8348fed52647d13406cc3a55b81b67d61c6`

Training completed normally for five fine-tuning epochs. Epoch 2 was selected
with score `0.4729154`. The process returned code 2 only after writing a complete
report because locked research/deployment gates rejected the model. No runtime
artifact was replaced.

## r05 measured result

- Grouped synthetic test macro-F1: `0.885905`
- Synthetic clean recall: `0.738889`
- Synthetic adversarial recall: `0.988889`
- Synthetic tampered recall: `0.933333`
- QR-DN clean false-positive rate: `0.0`
- Exact-app Camera holdout: clean FPR `0.0`, adversarial recall `1.0`, tampered recall `1.0`
- Exact-app Gallery holdout: clean FPR `0.0`, adversarial recall `1.0`, tampered recall `1.0`
- Exact-app paired Gallery/Camera verdict agreement: `1.0`
- Exported 120-session test: clean FPR `0.0`, adversarial recall `0.925`, tampered recall `1.0`
- Exported Camera-only test: clean FPR `0.0`, adversarial recall `0.85`, tampered recall `1.0`
- Exposure verdict agreement: `1.0`
- Clean exposure probability-span P95: `0.011454`
- Synthetic test ECE: `0.035780`

The exposure and exact-app Camera recovery is real on the locked development
evidence, but it is not enough for promotion.

## Topology diagnosis

On the r05 independent-payload topology validation matrix, r04 produced `33/512`
clean false positives (`0.064453`) and a full-family probability-span P95 of
`0.799788`. r05 reduced this to `9/512` (`0.017578`) and `0.520148`, so training
learned most of the legal-mask variation but did not pass the locked `0.01` FPR
or `0.15` span gates.

The remaining nine errors were confined to V3/V5 and masks 3, 4 and 7. The
within-condition mask-span P95 was `0.503423`, while the same-mask
normal-versus-moire span P95 was only `0.077983`. This isolates the remaining
problem as legal mask/layout sensitivity, not exposure or screen-moire
sensitivity.

A second regression was hidden by the large clean topology slice: on the 180
ordinary procedural clean validation rows, r04 had `2/180` false positives
(`0.011111`) while r05 had `46/180` (`0.255556`). The grouped synthetic test clean
recall fell from r04's `0.966667` to r05's `0.738889`. r05's sampler placed the
ordinary and topology-generated clean rows in one procedural family, allowing
the topology multiplier to take more than half of that family's clean draw mass.

## Consumed physical replay

The previously opened blind archive was replayed only with evidence role
`development_replay`; it can never be used for promotion.

- Clean false blocks improved from r04 `3/16` to r05 `1/16`.
- Two additional high-version clean sessions became rescan rather than Safe or
  Blocked.
- Clean layout probability span remained `0.9274`, above the `0.15` limit.
- Tampered sessions remained `16/16` blocked.
- Only two adversarial sessions contained verified capture-surviving physical
  attacks, so that archive remains statistically insufficient for an attack
  gate; its broader false-Safe result is development diagnosis only.

## r05 decision

`r05` is rejected and unpromoted. Research gates failed because topology clean
FPR was `0.017578 > 0.01` and probability-span P95 was `0.520148 > 0.15`.
Deployment additionally lacks a fresh device/display/session blind holdout.
The synthetic clean regression is treated as a further blocker even though the
older r05 config did not yet expose a dedicated clean-recall gate.

## r06 locked design

`structural-2026.09-r06` starts from the rejected r05 checkpoint but changes the
training contract rather than weakening any threshold:

- 2,560 topology rows and 160 payload groups: three independent training
  payloads and two independent validation payloads for every Version × L/M/Q/H
  combination, with all masks 0-7 and normal/screen-moire conditions;
- separate ordinary-procedural (`0.30`) and topology-counterfactual (`0.20`)
  quotas inside the clean class, preventing topology rows from displacing the
  older clean distribution;
- deterministic consistency partners use the opposite condition and mask
  `(mask + 4) mod 8`, replacing the weak adjacent-row ring used by r05;
- checkpoint selection penalises ordinary procedural clean FPR above `0.08`;
- final gates require synthetic macro-F1 `>= 0.90` and clean/adversarial/tampered
  recall each `>= 0.90`, in addition to the unchanged Camera, exposure,
  topology, SEM-05 and fresh-blind gates.

Locked r06 identities:

- Manifest: 14,150 rows; SHA-256 `c553efd57c707d1f60457ade0ffa2d2675e225727b95d8cea17820ed56a96d16`
- Config SHA-256: `79b9046021591a2cece22294334a2390d22bef5649ad13086eb96019a9817b05`
- Topology train: 1,536 rows / 96 groups
- Topology validation: 1,024 rows / 64 groups

Before r06 training, the frozen r05 model was evaluated on the new r06
development-validation payloads. It produced `14/1024` false positives
(`0.013672`), full-family span P95 `0.525293`, within-condition mask span P95
`0.479694`, and same-mask condition span P95 `0.064614`. This is the locked
training-start baseline; it is not blind evidence.

## r06 Colab handoff

- Bundle: `dist/QRGuard_ML_Colab.zip`
- Bytes: `156531328`
- SHA-256: `90419c1c35d5e5ff3612359cb13846f5ba961586dbaed4e9d2b440a13335ef8b`
- Notebook run ID: `r06-topology-generalisation-v1`
- Focused package/topology/notebook contract tests: `17 passed`
- Full related manifest/sampling/exposure/package test set: `38 passed`

The user will start Colab manually. A fresh blind capture must not be generated
until r06 first passes every development gate. The notebook still never
promotes, pushes, or deploys automatically.
