# Structural v3 real paired-capture campaign — latest

Campaign ID: **`structural-v3-real-2026.03-r01`**
Status: **deployment count gate passed; 300 Camera sessions and 60 required test pairs audited**

The original `scope_50x3_selection.json` remains the first research hand-off.
The finalized deployment scope combines that hand-off with the audited add-on
and repair captures: 100 Camera cases per class, ten per class/quality condition,
with a locked 60/20/20 train/validation/test split. The 60 required test cases
also have their paired Gallery reference; one additional clean Gallery session
is accepted but does not increase the independent test count.

The canonical strict audit is `data/runtime_captures/audit_v3.json`; its
publishable hash/count summary is `deployment_100x3_audit.json`. All 361
canonical sessions passed with zero rejected sessions and zero split leakage.
The 143 reference-mismatched add-on sessions remain quarantine evidence and are
not present in training-ready data.

Do not place raw QR payloads or personal data in this folder. Use a new,
non-personal test payload for each independent case. Exposure, blur, distance,
glare, shadow, perspective and screen artefacts are quality conditions, not
malicious labels.

No additional bulk capture is required before training. Add data only when a
locked performance slice fails and the new collection targets that failure.
