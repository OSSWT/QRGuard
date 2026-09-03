# Structural r07 Colab readiness

Date: 2026-09-03
Candidate: `structural-2026.09-r07`
Run ID: `r07-dense-screen-clean-recovery-v1`

## Why r07 exists

r06 removed synthetic standards-valid topology false positives, but its consumed
physical replay still produced two false blocks and two rescans among 16 clean
identities. Every non-Safe clean case was Version 12, 65 modules and a 132-byte
payload. The remaining problem is therefore a real screen-camera domain gap,
not missing QR-standard mask coverage.

## Locked changes

- Start from the rejected r06 best checkpoint. The deployed r01 artifact remains
  unchanged.
- Admit 80 clean exact-app crops from the consumed M8 archive. The archive is
  permanently development-only and never promotion evidence.
- Exclude all 160 adversarial/tampered M8 crops. The adversarial capture had too
  few verified post-capture surviving attacks to support trustworthy labels.
- Split the 16 clean QR identities as 12 train and 4 validation identities. The
  validation identities cover V3, V6 and two V12 layouts. All five temporal frames
  of one identity remain in one split.
- Give the consumed clean source a 4x multiplier within the existing clean Camera
  sampling allocation; do not change class balance or turn acquisition conditions
  into malicious labels.
- Pair temporal frames under the existing exposure-consistency objective.
- Select checkpoints feasibility-first. A checkpoint satisfying all clean
  constraints outranks a higher aggregate score that violates Camera, topology,
  procedural-clean or consumed-M8-clean limits.
- Require zero row-level and zero session-level false positives on the consumed
  M8 clean development validation split. This is a regression gate only; it does
  not approve deployment.
- A newly generated device/display/session blind holdout remains mandatory.

## Locked identities

- Consumed source archive SHA-256:
  `d5930ffcaf1edc0702afd5ff2b2241584a95edd9f9f0de81fdc8a5a5a7921f6d`
- Consumed clean manifest SHA-256:
  `22e628c14fe04ca93960e04c667899d8212b302d53091abf181eddfd6ae71660`
- Candidate manifest: 14,230 rows, SHA-256
  `dbc595a4542dab8490caed4ee2bbd236743d307e849cb4c03d2955c81761ca5b`
- r06 initial checkpoint SHA-256:
  `95a499bb8e5bf4f95cb9ad311266faffd65d2b25bacefe822fcf5799686f5781`
- r07 config SHA-256:
  `05a4239020933adc0a286e8fe36a0730ed75a4ccd0f7d81623672c685ed7b368`
- Colab ZIP SHA-256:
  `2890615ee514335cf7aeb412a14929208d5fc5cf53fcf4ee3e3bdb7c8c3702fa`

The fast r06-cache rebase and a full recipe rebuild independently produced the
same 14,230-row candidate manifest hash.

## Verification

- 39 focused package/topology/data/sampling/resume tests passed.
- 18 final Colab package and r07 regression tests passed after the final build.
- Python compilation and `git diff --check` passed.
- The generated upload ZIP is 175,445,019 bytes.

No runtime model was replaced, no promotion was performed, and no fresh blind
holdout was generated before the r07 development gates were tested.
