# Dataset split and leakage policy

- Structural derivatives inherit the physical QR, payload and capture-session
  group of their parent. Gallery/Camera pairs share one `paired_group`.
- A camera burst contributes one authoritative session-level model input.
- Semantic rows are grouped by canonical URL and registrable domain before
  train/validation/test assignment.
- Conflicting labels are resolved before splitting; exact duplicates never
  cross splits.
- Independent holdout, locked deployment evidence and post-training demo QR
  cards are never admitted to model fitting or threshold calibration.
- `qr_codes_demo` is demonstration/evaluation material only. It must not be
  reported as a training set or silently added to a future run.
