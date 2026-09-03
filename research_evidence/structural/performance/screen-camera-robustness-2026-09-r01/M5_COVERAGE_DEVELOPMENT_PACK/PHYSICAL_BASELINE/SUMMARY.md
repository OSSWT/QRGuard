# Live-camera repeatability results

Source SHA-256: `f3267b92176414473f0e936059f0a4b45ff9164ad5be8b702041d63c7aaa0bfa`

Model: `structural-2026.03-r01` / `3529df95acaba3f5fe29f7369670de5c0c8c06d60f90e8a2e1959584967c5ad4`

## Integrity

- Sessions / frames: 48 / 240
- Crops whose independently decoded payload hash matched: 179/240
- Globally unique crops: 240; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 15.0% | 11.2% |
| Session first frame | 12.5% | 21.9% |
| Majority of five verdicts | 12.5% | 6.2% |
| Median of five risk scores | 12.5% | 9.4% |

Quality abstention rate: 0.0%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| CVG-ADV-V03-M0-01 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.730 / 0.862 / 0.989 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V03-M1-02 | screen-80 | {'marginal': 5} | {'blocked': 5} | 0.836 / 0.922 / 0.995 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V03-M2-03 | screen-80 | {'marginal': 3, 'usable': 2} | {'blocked': 4, 'warning': 1} | 0.580 / 0.971 / 0.989 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V03-M3-04 | screen-80 | {'usable': 5} | {'safe': 1, 'blocked': 4} | 0.255 / 0.725 / 0.873 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V03-M4-05 | screen-80 | {'usable': 5} | {'safe': 2, 'blocked': 2, 'warning': 1} | 0.275 / 0.540 / 0.659 | {'safe': 1} | {'blocked': 1} | {'safe': 1} |
| CVG-ADV-V05-M0-09 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 1, 'safe': 4} | 0.157 / 0.287 / 0.834 | {'blocked': 1} | {'safe': 1} | {'safe': 1} |
| CVG-ADV-V05-M1-10 | screen-80 | {'usable': 5} | {'safe': 3, 'blocked': 2} | 0.328 / 0.446 / 0.589 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-ADV-V05-M5-06 | screen-80 | {'usable': 5} | {'blocked': 4, 'safe': 1} | 0.256 / 0.716 / 0.948 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V05-M6-07 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.814 / 0.876 / 0.948 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V05-M7-08 | screen-80 | {'usable': 5} | {'safe': 1, 'blocked': 4} | 0.312 / 0.732 / 0.949 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M2-11 | screen-80 | {'usable': 5} | {'safe': 1, 'blocked': 4} | 0.004 / 0.961 / 0.974 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M3-12 | screen-80 | {'usable': 5} | {'blocked': 4, 'safe': 1} | 0.368 / 0.846 / 0.977 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M4-13 | screen-80 | {'usable': 5} | {'safe': 1, 'blocked': 4} | 0.324 / 0.690 / 0.950 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M5-14 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.776 / 0.933 / 0.995 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M6-15 | screen-80 | {'usable': 5} | {'blocked': 4, 'safe': 1} | 0.328 / 0.703 / 0.958 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-ADV-V10-M7-16 | screen-80 | {'usable': 5} | {'safe': 1, 'blocked': 4} | 0.218 / 0.702 / 0.733 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-CLN-V03-M0-01 | screen-80 | {'usable': 5} | {'safe': 4, 'blocked': 1} | 0.065 / 0.377 / 0.908 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V03-M1-02 | screen-80 | {'usable': 5} | {'safe': 4, 'blocked': 1} | 0.239 / 0.408 / 0.652 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V03-M2-03 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.621 / 0.944 / 0.988 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-CLN-V03-M3-04 | screen-80 | {'usable': 5} | {'safe': 1, 'blocked': 4} | 0.048 / 0.754 / 0.897 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-CLN-V03-M4-05 | screen-80 | {'usable': 5} | {'safe': 5} | 0.214 / 0.348 / 0.413 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M0-09 | screen-80 | {'usable': 5} | {'safe': 5} | 0.004 / 0.007 / 0.015 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M1-10 | screen-80 | {'usable': 5} | {'safe': 5} | 0.011 / 0.038 / 0.096 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M5-06 | screen-80 | {'usable': 5} | {'safe': 5} | 0.039 / 0.102 / 0.157 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M6-07 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 1, 'safe': 4} | 0.010 / 0.040 / 0.796 | {'blocked': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V05-M7-08 | screen-80 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.106 / 0.189 / 0.472 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M2-11 | screen-80 | {'usable': 5} | {'safe': 5} | 0.000 / 0.001 / 0.006 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M3-12 | screen-80 | {'usable': 5} | {'safe': 5} | 0.000 / 0.001 / 0.001 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M4-13 | screen-80 | {'usable': 5} | {'safe': 5} | 0.004 / 0.022 / 0.119 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M5-14 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.011 / 0.059 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M6-15 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.004 / 0.019 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-CLN-V10-M7-16 | screen-80 | {'usable': 5} | {'safe': 5} | 0.000 / 0.001 / 0.005 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| CVG-TMP-V03-M0-01 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.882 / 0.922 / 0.965 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V03-M1-02 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 3, 'safe': 1, 'warning': 1} | 0.529 / 0.685 / 0.792 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V03-M2-03 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.868 / 0.923 / 0.974 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V03-M3-04 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.714 / 0.982 / 0.989 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V03-M4-05 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.963 / 0.984 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M0-09 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.804 / 0.871 / 0.954 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M1-10 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.976 / 0.986 / 0.995 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M5-06 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.986 / 0.989 / 0.994 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M6-07 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.975 / 0.990 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V05-M7-08 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.974 / 0.989 / 0.996 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M2-11 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.967 / 0.998 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M3-12 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.980 / 0.992 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M4-13 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.995 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M5-14 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M6-15 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| CVG-TMP-V10-M7-16 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.997 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
