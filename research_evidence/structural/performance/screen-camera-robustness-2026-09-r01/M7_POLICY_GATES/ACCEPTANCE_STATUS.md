# M8 Structural candidate status

Candidate `structural-2026.09-r01` is development-ready but not approved for
production. The frozen model SHA-256 is
`200a5ff02dbe47623ca738902bdcfe16b97bfbc507398e91dce9845aa7581ac9`.

The camera policy applies a 0.70 definitive-manipulation floor only after the
three-frame temporal consensus. A below-floor attack prediction becomes an
inconclusive rescan, never Safe. Gallery behaviour is unchanged.

## Completed gates

- Digital SEM-11: 24/24 branch contracts passed.
- QR demo: 84/84 final and branch contracts passed.
- SEM-05-style masked branch errors: 0.
- SEM-11 physical root-cause replay: 0% false Blocked, 16.7% rescan, 100%
  correctness among definitive clean decisions.
- Balanced coverage development replay: 48/48 sessions correct, 0 rescan,
  0% clean false Blocked and 0% attack false Safe.
- Flutter: 89 tests passed and static analysis found no issues.
- Backend: 399 tests passed and 1 environment-dependent test skipped in the
  final full-suite rerun, including all M8 audit contract tests.

## M8 blind result

The returned archive passed transport and coverage integrity: 48/48 sessions,
240/240 frames, all Version bands, every mask twice per class and all payload
length bins. The candidate was frozen before capture.

- Tampered: 16/16 Blocked.
- Clean: 1/16 false Blocked and 1/16 Rescan. The high-Version false-Blocked rate
  was 16.7%, and the clean layout probability span was 0.8931; both fail.
- Adversarial label survival: only 2/16 digital attacks remained independently
  verified against the victim after screen-camera capture. The remaining 14 are
  excluded from the candidate recall gate rather than being counted as false
  Safe. One of the two surviving attacks was Blocked and one was missed, but two
  cases are far below the required stratified sample size.

This exposed a hidden evidence-protocol bug: digital EOT success is not enough
to retain an adversarial label after physical recapture. Post-capture survival
proof is now a mandatory blind-audit prerequisite.

## Promotion blocker

`structural-2026.09-r01` is rejected for promotion. The next candidate must fix
high-Version clean layout dependence and train only on adversarial captures whose
physical attack survival is verified. It will require a new post-freeze blind
holdout; M8 cannot be reused as that acceptance set.

No runtime artifact was copied, no production default changed, and no push or
deployment was performed.
