# Multi-frame production candidate replay

Source SHA-256: `d5930ffcaf1edc0702afd5ff2b2241584a95edd9f9f0de81fdc8a5a5a7921f6d`

The best 3 geometry-ranked automatic crops in each session were evaluated together. A neutral non-URL payload isolates Structural behaviour; no decoded payload was stored.

## Result

- Correct session rate: 77.1%
- Rescan rate: 2.1%
- Clean false-Blocked rate: 18.8%
- Adversarial false-Safe rate: 21.9%
- Definitive decisions correct: clean 80.0%; adversarial 78.1%
- Pipeline latency: mean 313.2 ms; median 331.0 ms; P95 468 ms
- Definitive-session pipeline latency: mean 317.2 ms; median 332 ms; P95 468 ms

## Case x condition

| Case | Distance | >=256 px frames | Analysed | Outcomes |
|---|---|---:|---:|---|
| BLD-01-634AD9 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-02-2660E2 | screen-80 | 3 | 3 | {'false_safe': 1} |
| BLD-03-940C9F | screen-80 | 3 | 3 | {'false_safe': 1} |
| BLD-04-A543A7 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-05-B2EB90 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-06-48D796 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-07-1F1497 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-08-8DD40A | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-09-EB4682 | screen-80 | 3 | 3 | {'false_safe': 1} |
| BLD-10-F817CE | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-11-2D22EA | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-12-16F4F3 | screen-80 | 3 | 3 | {'false_block': 1} |
| BLD-13-1DB94C | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-14-C0B3B8 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-15-1FFEB7 | screen-80 | 3 | 3 | {'false_block': 1} |
| BLD-16-A7FCCD | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-17-34A075 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-18-5CD4F5 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-19-100593 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-20-16DE27 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-21-EBECE2 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-22-0E5D74 | screen-80 | 3 | 3 | {'false_safe': 1} |
| BLD-23-2F9C34 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-24-34902F | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-25-BCBF4C | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-26-E211CD | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-27-90C833 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-28-F08776 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-29-466F54 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-30-754AFE | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-31-6763F8 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-32-62CEDC | screen-80 | 3 | 0 | {'rescan': 1} |
| BLD-33-4F2A63 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-34-18AE14 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-35-B2865A | screen-80 | 3 | 3 | {'false_safe': 1} |
| BLD-36-88BCFE | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-37-419935 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-38-43248D | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-39-5285E9 | screen-80 | 3 | 3 | {'false_safe': 1} |
| BLD-40-B711F3 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-41-098307 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-42-819C84 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-43-A7B6A5 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-44-D2E154 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-45-D9AEC1 | screen-80 | 3 | 3 | {'false_block': 1} |
| BLD-46-FF9451 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-47-175860 | screen-80 | 3 | 3 | {'correct': 1} |
| BLD-48-F47E77 | screen-80 | 3 | 3 | {'false_safe': 1} |

A rescan is an intentional abstention, not a correct classification. This captured matrix used smaller QR crops than the promoted exact-app holdout, so it validates fail-closed acquisition behaviour but cannot replace the independent deployment gate.
