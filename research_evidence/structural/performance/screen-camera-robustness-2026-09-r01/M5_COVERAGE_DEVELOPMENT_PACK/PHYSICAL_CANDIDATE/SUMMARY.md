# Live-camera repeatability results

Source SHA-256: `f3267b92176414473f0e936059f0a4b45ff9164ad5be8b702041d63c7aaa0bfa`

Model: `structural-2026.09-r01` / `200a5ff02dbe47623ca738902bdcfe16b97bfbc507398e91dce9845aa7581ac9`

## Integrity

- Sessions / frames: 48 / 240
- Crops whose independently decoded payload hash matched: 179/240
- Globally unique crops: 240; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 0.0% | 0.0% |
| Session first frame | 0.0% | 0.0% |
| Majority of five verdicts | 0.0% | 0.0% |
| Median of five risk scores | 0.0% | 0.0% |

Quality abstention rate: 0.0%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| CVG-ADV-V03-M0-01 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.992 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V03-M1-02 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.995 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V03-M2-03 | screen-80 | {'marginal': 3, 'usable': 2} | {'blocked': 5} | 0.986 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V03-M3-04 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V03-M4-05 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V05-M0-09 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V05-M1-10 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.983 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V05-M5-06 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.998 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V05-M6-07 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V05-M7-08 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M2-11 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M3-12 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M4-13 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M5-14 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M6-15 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M7-16 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-CLN-V03-M0-01 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V03-M1-02 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V03-M2-03 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V03-M3-04 | screen-80 | {'usable': 5} | {'safe': 5} | 0.000 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V03-M4-05 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.002 / 0.010 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M0-09 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.002 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M1-10 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.002 / 0.003 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M5-06 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M6-07 | screen-80 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.001 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M7-08 | screen-80 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.001 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M2-11 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M3-12 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.002 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M4-13 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M5-14 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.002 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M6-15 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M7-16 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.002 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-TMP-V03-M0-01 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.997 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V03-M1-02 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.970 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V03-M2-03 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.994 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V03-M3-04 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.928 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V03-M4-05 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.987 / 0.994 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M0-09 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M1-10 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M5-06 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M6-07 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.994 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M7-08 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.998 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M2-11 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.999 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M3-12 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M4-13 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.998 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M5-14 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M6-15 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M7-16 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
