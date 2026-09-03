# Live-camera repeatability results

Source SHA-256: `d5930ffcaf1edc0702afd5ff2b2241584a95edd9f9f0de81fdc8a5a5a7921f6d`

Model: `structural-2026.09-r01` / `200a5ff02dbe47623ca738902bdcfe16b97bfbc507398e91dce9845aa7581ac9`

## Integrity

- Sessions / frames: 48 / 240
- Crops whose independently decoded payload hash matched: 93/240
- Globally unique crops: 240; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 5.0% | 22.5% |
| Session first frame | 0.0% | 25.0% |
| Majority of five verdicts | 6.2% | 25.0% |
| Median of five risk scores | 6.2% | 25.0% |

Quality abstention rate: 2.9%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| BLD-01-634AD9 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.002 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-02-2660E2 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.002 / 0.002 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-03-940C9F | screen-80 | {'usable': 5} | {'safe': 5} | 0.003 / 0.010 / 0.035 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-04-A543A7 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.963 / 0.969 / 0.974 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-05-B2EB90 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.992 / 0.997 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-06-48D796 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-07-1F1497 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-08-8DD40A | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-09-EB4682 | screen-80 | {'usable': 5} | {'safe': 5} | 0.034 / 0.126 / 0.431 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-10-F817CE | screen-80 | {'usable': 5} | {'blocked': 5} | 0.978 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-11-2D22EA | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-12-16F4F3 | screen-80 | {'usable': 4, 'marginal': 1} | {'safe': 4, 'warning': 1} | 0.311 / 0.383 / 0.502 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-13-1DB94C | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-14-C0B3B8 | screen-80 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.002 / 0.002 / 0.025 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-15-1FFEB7 | screen-80 | {'usable': 4, 'marginal': 1} | {'safe': 1, 'warning': 1, 'blocked': 3} | 0.332 / 0.901 / 0.931 | {'safe': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-16-A7FCCD | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.920 / 0.967 / 0.983 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-17-34A075 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.996 / 0.997 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-18-5CD4F5 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.003 / 0.005 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-19-100593 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.994 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-20-16DE27 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.998 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-21-EBECE2 | screen-80 | {'usable': 5} | {'safe': 5} | 0.004 / 0.005 / 0.011 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-22-0E5D74 | screen-80 | {'usable': 5} | {'safe': 3, 'blocked': 2} | 0.114 / 0.498 / 0.848 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-23-2F9C34 | screen-80 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.061 / 0.208 / 0.218 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-24-34902F | screen-80 | {'usable': 5} | {'blocked': 5} | 0.998 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-25-BCBF4C | screen-80 | {'marginal': 1, 'usable': 4} | {'safe': 5} | 0.002 / 0.002 / 0.008 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-26-E211CD | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-27-90C833 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.978 / 0.990 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-28-F08776 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.004 / 0.005 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-29-466F54 | screen-80 | {'usable': 5} | {'safe': 5} | 0.003 / 0.004 / 0.005 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-30-754AFE | screen-80 | {'usable': 5} | {'safe': 5} | 0.004 / 0.006 / 0.008 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-31-6763F8 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-32-62CEDC | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.003 / 0.003 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-33-4F2A63 | screen-80 | {'usable': 5} | {'blocked': 5} | 1.000 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-34-18AE14 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.991 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-35-B2865A | screen-80 | {'usable': 4, 'marginal': 1} | {'safe': 3, 'warning': 1, 'blocked': 1} | 0.100 / 0.427 / 0.845 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-36-88BCFE | screen-80 | {'usable': 5} | {'safe': 5} | 0.003 / 0.003 / 0.003 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-37-419935 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.003 / 0.005 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-38-43248D | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-39-5285E9 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.006 / 0.027 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-40-B711F3 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.941 / 0.951 / 0.965 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-41-098307 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 1.000 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-42-819C84 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.906 / 0.937 / 0.987 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-43-A7B6A5 | screen-80 | {'usable': 5} | {'safe': 5} | 0.001 / 0.002 / 0.003 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-44-D2E154 | screen-80 | {'usable': 5} | {'safe': 5} | 0.047 / 0.080 / 0.199 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| BLD-45-D9AEC1 | screen-80 | {'marginal': 4, 'usable': 1} | {'warning': 4, 'blocked': 1} | 0.766 / 0.766 / 0.766 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| BLD-46-FF9451 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.994 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-47-175860 | screen-80 | {'marginal': 1, 'usable': 4} | {'blocked': 5} | 0.907 / 0.976 / 0.982 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| BLD-48-F47E77 | screen-80 | {'usable': 5} | {'safe': 5} | 0.055 / 0.081 / 0.311 | {'safe': 1} | {'safe': 1} | {'safe': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
