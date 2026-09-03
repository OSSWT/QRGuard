# SEM-11 controlled digital baseline

The 12-case root-cause pack holds the clean Plain Text semantics constant while
separating same-length payload layout, QR masks 0-7 and Version 3/4.  Every case
has Structural ground truth `clean` and intended verdict `Safe`.

This is a digital Gallery and rectified-crop Camera simulation baseline.  It is
not physical Live Camera evidence and contains no screen moire, autofocus or
sensor sampling effect.

## Result

- Requests: 24.
- Branch-contract matches: 22.
- Failing case: `RC-MASK-7` in both Gallery and Camera simulation.
- `RC-MASK-7`: Structural `tampered`, score `0.6454`, risk `76`, final Blocked.
- `RC-MASK-1`: Structural remained `clean`, but score `0.5156` and risk `24`
  place it close to a decision boundary.
- Canonical SEM-11 / mask 4: Structural `clean`, score `0.3172`, risk `7`.
- Same payload forced to Version 4: Structural `clean`, score about `0.221`.

## Interpretation boundary

This controlled result proves that legal QR mask/module layout can materially
change the deployed Structural model output even without physical recapture.
It rejects payload meaning as the cause and makes raw-layout invariance a primary
model requirement.  It does not yet prove that mask 4 causes the physical 80%
failure: the physical screen-camera pass remains required to measure the
additional scale/sampling interaction.

The mask 7 failure must remain in the evidence.  It must not be removed from the
pack, allowlisted, or converted to a special-case Safe rule.
