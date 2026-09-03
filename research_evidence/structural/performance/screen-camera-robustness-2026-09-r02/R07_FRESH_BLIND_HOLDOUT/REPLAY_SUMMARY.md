# Multi-frame production candidate replay

Source SHA-256: `718b83f7032ca4e67d494105ed91bea5a14be1aa709c02cea046669a55958c08`

The best 3 geometry-ranked automatic crops in each session were evaluated together. A neutral non-URL payload isolates Structural behaviour; no decoded payload was stored.

## Result

- Correct session rate: 100.0%
- Rescan rate: 0.0%
- Clean false-Blocked rate: 0.0%
- Adversarial false-Safe rate: 0.0%
- Definitive decisions correct: clean 100.0%; adversarial 100.0%
- Pipeline latency: mean 383.4 ms; median 216.5 ms; P95 917 ms
- Definitive-session pipeline latency: mean 383.4 ms; median 216.5 ms; P95 917 ms

## Case x condition

| Case | Distance | >=256 px frames | Analysed | Outcomes |
|---|---|---:|---:|---|
| R7B-01-BF8A9F | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-02-5A41E4 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-03-1FA25B | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-04-F9409B | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-05-2EA7CF | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-06-4F0FC4 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-07-B1579A | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-08-551C47 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-09-1C14A9 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-10-683AF9 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-11-A11129 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-12-473F6A | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-13-C0F52D | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-14-5F3509 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-15-185A0D | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-16-B36FE9 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-17-C4A596 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-18-E9CFED | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-19-D8F6DF | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-20-EA4843 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-21-F5A9DA | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-22-03D724 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-23-1C1B30 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-24-90D5AF | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-25-1381A8 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-26-C08B18 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-27-44E773 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-28-387FB1 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-29-310490 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-30-453F46 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-31-384631 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-32-E60C7B | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-33-FF6F1C | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-34-CE3DDF | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-35-008AC4 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-36-440538 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-37-BE5042 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-38-B5063F | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-39-AEF82D | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-40-099955 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-41-5FA406 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-42-245F1B | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-43-EB242D | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-44-7976D4 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-45-786666 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-46-D739A9 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-47-C889A0 | screen-80 | 3 | 3 | {'correct': 1} |
| R7B-48-574A6B | screen-80 | 3 | 3 | {'correct': 1} |

A rescan is an intentional abstention, not a correct classification. This captured matrix used smaller QR crops than the promoted exact-app holdout, so it validates fail-closed acquisition behaviour but cannot replace the independent deployment gate.
