# Dataset split and leakage policy

- Structural derivatives inherit the physical QR, payload and capture-session
  group of their parent. Gallery/Camera pairs share one `paired_group`.
- Exposure variants and temporal partners inherit label, base identity, device,
  display and session. They are derived only after the parent split is locked.
- A promotion holdout must use fresh base identities and a device/display/session
  combination not used for threshold selection. Frames from one burst never count
  as independent evidence.
- A camera burst contributes one authoritative session-level model input.
- Semantic rows are grouped by canonical URL and registrable domain before
  train/validation/test assignment.
- Conflicting labels are resolved before splitting; exact duplicates never
  cross splits.
- Independent holdout, locked deployment evidence and post-training demo QR
  cards are never admitted to model fitting or threshold calibration.
- `qr_codes_demo` is demonstration/evaluation material only. It must not be
  reported as a training set or silently added to a future run.
- A generated adversarial reference is not a physical adversarial training row.
  It is admitted only when the paired post-capture survival audit explicitly sets
  `physical_attack_survival_verified=true`; non-surviving attacks stay quarantined.
- Once a blind holdout is unblinded or replayed during diagnosis, it is permanently
  consumed. Its clean crops may be reclassified as development-only hard negatives
  under a newly locked, group-disjoint split, but they can never count as promotion
  evidence again. Attack crops without verified post-capture survival stay excluded.
