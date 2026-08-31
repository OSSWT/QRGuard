# Live-camera repeatability evidence

This directory keeps the before/after evidence from the hash-locked 30-session,
150-frame diagnostic archive.

- Root `FRAME_RESULTS.csv`, `SESSION_RESULTS.csv`, `ANALYSIS.json`, and
  `SUMMARY.md`: deployed single-frame baseline recorded before the correction.
- `candidate-multiframe/`: the same five-frame sessions replayed through the
  selected size gate, recoverable exposure handling, and temporal consensus.
- The independent 120-row regression gate is stored under
  `research_evidence/decision/performance/candidate-stack-live-camera-multiframe-2026-09-r01/`.

The two QR references are exposed diagnostic cases. They are not training data
and do not replace the independent deployment set.
