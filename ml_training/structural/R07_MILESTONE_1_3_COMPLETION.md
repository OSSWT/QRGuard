# r07 Milestone 1-3 completion record

No model, production artifact, runtime threshold or deployed default was changed.
No r08 work was started.

## Milestone 1: consumed-holdout root-cause diagnosis

Complete. The source archive was integrity-validated and all 240 frames were
joined to acquisition telemetry without storing raw payload text.

- 16/16 clean sessions remained Safe under temporal consensus.
- One of 80 clean frames was Blocked.
- `R7B-07-B1579A` (V3, 29 modules, mask 0, 24-byte payload) ranged from
  0.0022 to 0.7699 and contained the single-frame false block.
- `R7B-24-90D5AF` (V10, 57 modules, mask 4, 97-byte payload) ranged from
  0.0419 to 0.2512 without a false block.
- Whole-set telemetry correlations were weak. The evidence supports a
  layout/camera interaction hypothesis, not a single proven exposure cause.

Diagnosis:
`single_frame_instability_rescued_by_temporal_consensus`.

Evidence:
`research_evidence/structural/performance/screen-camera-robustness-2026-09-r02/R07_CONSUMED_ROOT_CAUSE/ANALYSIS.json`

SHA-256:
`9ea8e0447f8da60328315788032a6e5d7deefb4cb79c6d827e6a86348ccad0a7`

## Milestone 2: physical attack generation and survival contract

Complete for implementation and pre-capture planning.

- Added a deterministic twelve-view screen-camera EOT suite covering resize,
  mild defocus, luminance, contrast, gamma and small shifts.
- Added two independent projection profiles:
  `screen_camera_robust_v2_function` and
  `screen_camera_robust_v2_alternate`.
- Raised generation-time EOT success required by these profiles from 0.50 to
  0.75 and increased iterative optimisation from 12 to 20 steps.
- Added a 72-case development-only calibration design with 24 paired clean QR
  identities and 48 attacks, balanced at 16 attacks per Version band.
- Extended the post-capture audit with per-band and per-profile survival,
  Wilson lower bounds, explicit minimum-five gates and capture-volume planning.
- Re-audited the consumed capture into a new non-promoting diagnosis. The old
  attack profile retained 2/5 low, 3/5 medium and 1/6 high attacks.

Evidence:
`research_evidence/structural/performance/screen-camera-robustness-2026-09-r02/R07_CONSUMED_ATTACK_SURVIVAL_DIAGNOSIS/ANALYSIS.json`

SHA-256:
`c4179bd2b008f803d6c3931af573021a5f238b442feed117c022453c02e56562`

The subsequent real development capture verified 25/48 physical survivors:
8/16 low-Version attacks, 8/16 medium-Version attacks and 9/16 high-Version
attacks. These represent 5, 5 and 6 independent base QR identities respectively.
The result establishes improved physical yield over the old 6/16 profile, but
remains development-only and cannot promote a model.

Evidence:
`research_evidence/structural/performance/r07-corrective/ATTACK_CALIBRATION_V1_SURVIVAL/ANALYSIS.json`

SHA-256:
`a708747c28abc594846d132c7554cf911d36880c971cb27bd652448fbbd234e3`

## Milestone 3: prospective product acceptance policy

Complete and frozen.

- Functional errors, evidence integrity, candidate binding, per-band recall,
  rescan, physical-survival counts, SEM-05 and SEM-11 remain hard gates.
- A clean raw-score span above 0.15 is an advisory when clean session outcomes
  still pass every hard gate; it is never hidden or called a calibrated
  maliciousness probability.
- Hard gates plus an advisory permit only
  `controlled_pilot_with_documented_limitations`.
- General deployment requires all hard gates and no advisories.
- The consumed `structural-r07-fresh-blind-v1` campaign is explicitly barred
  from this prospective policy, preventing retrospective reclassification.

Policy:
`ml_training/configs/structural-r07-product-acceptance-v1.json`

Policy SHA-256:
`f06cff4bd04057adcae208cd89e38b95e6f71b21c99fc7eadcbb95046ca104f6`

## Verification

- New Milestone unit tests: 13 passed.
- Compatible pack and acceptance regression tests: 18 passed.
- All 24 calibration QR bases decoded to their exact expected payload.
- Python compilation and whitespace validation passed.
