# r07 corrective acceptance hand-off

The frozen `structural-r07-corrective-v1` candidate completed its single fresh
physical blind evaluation. No production artifact was changed or promoted.

## Candidate and evidence identity

- Candidate ONNX SHA-256:
  `71a86dec83c5c63dd3ac4b83705f403c183c9efe8822a424e072a7b95c555033`
- Source capture SHA-256:
  `718b83f7032ca4e67d494105ed91bea5a14be1aa709c02cea046669a55958c08`
- Sealed reference pack SHA-256:
  `44d3fa833d64a6df05cca1a8670b2ab0586e930fcb28dbb2418c7b5531cb3aff`
- Complete evidence: 48 sessions, 240 frames, 16 cases per class
- Candidate binding: matched

## Blind result

The candidate classified all 48 sessions correctly:

- clean: 16/16, zero false blocks;
- adversarial: 16/16 blocked;
- tampered: 16/16 blocked;
- rescan: zero.

Promotion nevertheless failed four pre-registered gates:

1. low-Version band contained 2 verified surviving physical attacks; required 5;
2. medium-Version band contained 3; required 5;
3. high-Version band contained 1; required 5;
4. clean layout probability span was 0.2109; maximum 0.1500.

Only 6/16 digital adversarial references retained the independent victim attack
effect after the screen/camera path. The r07 candidate detected every one of
those six, but insufficient surviving attacks means the attack-recall claim is
under-covered. Two correctly classified clean cases produced elevated raw
Structural probabilities, causing the independent layout-stability failure.

## Decision

`structural-r07-corrective-v1` remains a strong research candidate but is **not
deployment-approved** under the locked policy. Thresholds were not altered,
failed cases were not excluded, and production mutation remained false.

This blind evidence is now consumed. It may be used for diagnosis or future
development, but it can never be presented as an unseen deployment holdout
again. Any corrected r07 candidate requires a newly generated candidate-bound
blind pack and a new physical capture.

## Evidence locations

- Acceptance report:
  `research_evidence/structural/performance/screen-camera-robustness-2026-09-r02/R07_FRESH_BLIND_HOLDOUT/blind_holdout_acceptance.json`
- Physical survival report:
  `research_evidence/structural/performance/screen-camera-robustness-2026-09-r02/R07_FRESH_BLIND_ATTACK_SURVIVAL/ANALYSIS.json`
- Canonical source archives:
  `../04_Datasets/01_Structural/R07_Fresh_Blind_Holdout/`

No r08 work has been started. A further attempt must remain explicitly inside
the r07 corrective workstream and must preserve the consumed-evidence boundary.

## Attack-calibration follow-up

The stronger physical-attack development campaign is complete:

- 72/72 sessions and 360/360 frames passed the locked archive contract;
- 25/48 attacks survived the screen/camera path under the independent victim;
- independent surviving base identities were 5 low, 5 medium and 6 high;
- production-equivalent pixel-quality and exposure-diversity frame selection
  kept every clean base Safe and blocked every analyzable surviving attack base;
- one dense V14/73-module base required Rescan because the 416-430 px crop was
  below the frozen five-pixels-per-module evidence floor;
- the conservative independent-base development gate passed with no clean-score
  advisory; production remained unchanged and the campaign has no promotion rights.

The correct r07 decision is to retain `structural-r07-corrective-v1`, preserve
the module-scale Rescan safety boundary, and prepare a new candidate-bound blind
campaign. Retraining on this calibration is not justified by its functional
result.

Evidence:

- `research_evidence/structural/performance/r07-corrective/ATTACK_CALIBRATION_V1_SURVIVAL/ANALYSIS.json`
- `research_evidence/structural/performance/r07-corrective/ATTACK_CALIBRATION_V1_REPLAY/ANALYSIS.json`

## Milestones 1-3 follow-up

The first three corrective milestones are complete for all automatic work:

- all-frame consumed-holdout diagnosis identified one clean single-frame false
  block, rescued by temporal consensus, and two elevated clean layouts;
- the attack generator now has stronger deterministic screen-camera EOT
  profiles plus a balanced development calibration design and per-band physical
  survival planning;
- `structural-r07-product-acceptance-v1` is frozen prospectively, with
  functional failures as hard gates and clean score span as a disclosed
  advisory only.

The old blind rejection remains historical fact. The prospective policy cannot
be applied to `structural-r07-fresh-blind-v1`. See
`ml_training/structural/R07_MILESTONE_1_3_COMPLETION.md` for evidence hashes and
verification.
