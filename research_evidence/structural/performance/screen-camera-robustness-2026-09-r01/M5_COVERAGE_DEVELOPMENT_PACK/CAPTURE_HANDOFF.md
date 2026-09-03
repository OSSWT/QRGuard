# M5 screen-camera capture handoff

Use the diagnostic APK and development ZIP recorded in `BUILD_REPORT.json`.
This campaign does not require printing.

1. Extract `Structural_Coverage_Development_2026-09-r01.zip` on the display
   computer.
2. Open the images under `cards/` in the order listed by `CAPTURE_ORDER.csv`.
   Keep the viewer fixed at 80% for the entire run. Do not zoom above 100%.
3. Install and open
   `QRGuard_Diagnostic_structural_coverage_development_2026-09-r01.apk` on the
   Android test phone. Confirm the title is `QRGuard Diagnostic Capture` and the
   progress target is 48 sessions.
4. For each displayed card, select the same case ID in `Reference case`. The only
   condition is `Screen 80%` and each case needs one session.
5. Keep display brightness, phone distance and phone angle fixed. Make only that
   card visible to the camera, tap `Arm session 1`, and hold steady until all five
   temporal crops are accepted.
6. Confirm the case shows 1/1, then move to the next row. Do not substitute a
   different card if payload verification rejects a capture.
7. At 48/48, use `Export pending ZIP` once and return the saved diagnostic ZIP.

The expected export contains 48 sessions and 240 frames. It is development
train/validation evidence, not the final blind acceptance set.
