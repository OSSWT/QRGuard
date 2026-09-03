# Live-camera repeatability results

Source SHA-256: `718b83f7032ca4e67d494105ed91bea5a14be1aa709c02cea046669a55958c08`

Model: `structural-r07-corrective-v1` / `71a86dec83c5c63dd3ac4b83705f403c183c9efe8822a424e072a7b95c555033`

## Integrity

- Sessions / frames: 48 / 240
- Crops whose independently decoded payload hash matched: 167/240
- Globally unique crops: 240; duplicate instances: 0
- Raw decoded payload text stored: no

## Observed error rates

| Level/policy | Clean false Blocked | Adversarial false Safe |
|---|---:|---:|
| Individual frame | 1.2% | 0.0% |
| Session first frame | 0.0% | 0.0% |
| Majority of five verdicts | 0.0% | 0.0% |
| Median of five risk scores | 0.0% | 0.0% |

Quality abstention rate: 0.0%.

## Case × distance

| Case | Distance | Quality | Frame verdicts | p_structural min / median / max | First | Majority | Median |
|---|---|---|---|---|---|---|---|
| R7B-01-BF8A9F | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-02-5A41E4 | screen-80 | {'usable': 5} | {'warning': 1, 'safe': 4} | 0.002 / 0.003 / 0.005 | {'warning': 1} | {'safe': 1} | {'safe': 1} |
| R7B-03-1FA25B | screen-80 | {'usable': 5} | {'blocked': 5} | 0.985 / 0.990 / 0.993 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-04-F9409B | screen-80 | {'usable': 5} | {'blocked': 5} | 0.995 / 0.997 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-05-2EA7CF | screen-80 | {'usable': 5} | {'blocked': 5} | 0.996 / 0.998 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-06-4F0FC4 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.993 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-07-B1579A | screen-80 | {'usable': 5} | {'safe': 4, 'blocked': 1} | 0.002 / 0.172 / 0.770 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-08-551C47 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.993 / 0.996 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-09-1C14A9 | screen-80 | {'usable': 5} | {'safe': 5} | 0.008 / 0.010 / 0.029 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-10-683AF9 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.995 / 0.997 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-11-A11129 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.994 / 0.995 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-12-473F6A | screen-80 | {'usable': 5} | {'safe': 5} | 0.003 / 0.006 / 0.011 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-13-C0F52D | screen-80 | {'usable': 5} | {'safe': 1, 'warning': 4} | 0.002 / 0.003 / 0.005 | {'safe': 1} | {'warning': 1} | {'safe': 1} |
| R7B-14-5F3509 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.991 / 0.997 / 0.997 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-15-185A0D | screen-80 | {'usable': 5} | {'safe': 5} | 0.005 / 0.006 / 0.012 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-16-B36FE9 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.986 / 0.992 / 0.994 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-17-C4A596 | screen-80 | {'usable': 5} | {'safe': 5} | 0.002 / 0.014 / 0.047 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-18-E9CFED | screen-80 | {'usable': 5} | {'blocked': 5} | 0.956 / 0.973 / 0.976 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-19-D8F6DF | screen-80 | {'usable': 5} | {'blocked': 5} | 0.994 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-20-EA4843 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.996 / 0.998 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-21-F5A9DA | screen-80 | {'usable': 5} | {'blocked': 5} | 0.821 / 0.978 / 0.988 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-22-03D724 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.998 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-23-1C1B30 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-24-90D5AF | screen-80 | {'usable': 5} | {'safe': 5} | 0.042 / 0.118 / 0.251 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-25-1381A8 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.995 / 0.997 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-26-C08B18 | screen-80 | {'usable': 5} | {'safe': 5} | 0.012 / 0.025 / 0.106 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-27-44E773 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.999 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-28-387FB1 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.997 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-29-310490 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.995 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-30-453F46 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.971 / 0.993 / 0.994 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-31-384631 | screen-80 | {'usable': 5} | {'safe': 5} | 0.010 / 0.012 / 0.027 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-32-E60C7B | screen-80 | {'usable': 5} | {'blocked': 5} | 0.990 / 0.995 / 0.996 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-33-FF6F1C | screen-80 | {'usable': 5} | {'blocked': 5} | 0.990 / 0.993 / 0.996 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-34-CE3DDF | screen-80 | {'usable': 5} | {'warning': 5} | 0.001 / 0.003 / 0.007 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| R7B-35-008AC4 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.990 / 0.998 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-36-440538 | screen-80 | {'usable': 5} | {'safe': 5} | 0.013 / 0.016 / 0.040 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-37-BE5042 | screen-80 | {'usable': 5} | {'safe': 3, 'warning': 2} | 0.017 / 0.028 / 0.039 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-38-B5063F | screen-80 | {'usable': 5} | {'blocked': 5} | 0.998 / 0.999 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-39-AEF82D | screen-80 | {'usable': 5} | {'blocked': 5} | 0.987 / 0.992 / 0.996 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-40-099955 | screen-80 | {'usable': 5} | {'warning': 5} | 0.003 / 0.003 / 0.005 | {'warning': 1} | {'warning': 1} | {'safe': 1} |
| R7B-41-5FA406 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.997 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-42-245F1B | screen-80 | {'usable': 5} | {'blocked': 5} | 0.997 / 0.997 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-43-EB242D | screen-80 | {'usable': 5} | {'safe': 1, 'warning': 4} | 0.008 / 0.012 / 0.022 | {'safe': 1} | {'warning': 1} | {'safe': 1} |
| R7B-44-7976D4 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.997 / 0.998 / 0.999 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-45-786666 | screen-80 | {'usable': 5} | {'safe': 5} | 0.011 / 0.019 / 0.031 | {'safe': 1} | {'safe': 1} | {'safe': 1} |
| R7B-46-D739A9 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.975 / 0.994 / 0.996 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-47-C889A0 | screen-80 | {'usable': 5} | {'blocked': 5} | 0.998 / 0.999 / 1.000 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |
| R7B-48-574A6B | screen-80 | {'usable': 5} | {'blocked': 5} | 0.986 / 0.993 / 0.998 | {'blocked': 1} | {'blocked': 1} | {'blocked': 1} |

## Interpretation constraint

These diagnostic QR references are exposed cases, not an independent deployment test set. They can identify a live-camera failure mode and compare aggregation behaviour, but no production threshold may be promoted until the chosen rule also passes the existing held-out Structural gates.
