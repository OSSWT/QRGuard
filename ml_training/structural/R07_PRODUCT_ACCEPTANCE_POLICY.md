# Structural r07 product acceptance policy

This policy is frozen for the next fresh, candidate-bound blind campaign. It
must not be applied retroactively to `structural-r07-fresh-blind-v1`, because
that campaign and its outcomes are already visible and are development evidence.

## Hard gates

- The archive is complete, internally hashed and bound to the frozen candidate.
- Clean session false-Blocked rate is at most 5% in every Version band.
- Verified, physically surviving adversarial attacks are at least five per
  Version band, and block recall is at least 80% in every band.
- Tampered block recall is at least 85% in every Version band.
- Rescan rate is at most 20% for each class and Version band.
- Version, mask and payload-length coverage minimums all pass.
- SEM-05 masked-branch errors remain zero and the SEM-11 contract gate passes.
- Operator-selected or previously consumed cases cannot promote a candidate.

Any hard-gate failure blocks deployment. Attacks that worked only before being
shown to the camera do not count toward adversarial recall.

## Advisory diagnostics

Clean layout `p_structural` span above 0.15 is an advisory, not an automatic
functional failure, provided all hard clean-session gates still pass. The score
is model evidence rather than a calibrated probability that a QR code is
malicious. A span advisory therefore requires disclosure and follow-up coverage,
but it cannot replace an observed false-Blocked, false-Safe or rescan result.

When all hard gates pass with an advisory, the maximum release tier is a
controlled pilot with documented limitations. General deployment additionally
requires no advisory findings.

## Product disclosure

QRGuard reduces risk; a Safe result is not a guarantee. Camera glare, blur,
moire, exposure and unseen QR layouts can reduce confidence. The app should ask
for a rescan when image quality is inadequate, and release notes must identify
the tested device, capture medium and QR coverage boundaries.
