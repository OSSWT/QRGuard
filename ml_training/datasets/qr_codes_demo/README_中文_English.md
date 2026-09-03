# QRGuard QR Codes Demo

This pack demonstrates the already deployed QRGuard stack:

- Structural `structural-r07-corrective-v1`
- Semantic `semantic-2026.02`
- Decision `decision-2026.03-r05`

It is post-training demonstration/evaluation material. It is not an independent
training or deployment-accuracy dataset and must never be added to model fitting
or threshold calibration.

## Use with a supervisor

1. Open `PRESENTATION_DEMO.html`, or follow `QUICK_DEMO_ORDER.csv`, for the
   15-case presentation sequence covering every defined demo type.
2. For Live Camera, display one card on another screen or print it. Structural
   cards already embed a recorded app crop with the named condition, so scan them
   normally; adding another degradation would create a different test.
3. For Gallery parity, import the same PNG directly into QRGuard.
4. Record the phone result and screenshot name in `ACTUAL_RESULTS.csv`.
5. Do not open decoded destinations. Network-style risk cases use reserved or
   documentation-only destinations, except the shortener card, which is scan-only.

`EXPECTED_RESULTS.csv` records intended behaviour. Run
`python scripts/validate_qr_codes_demo.py --target local` and then `--target remote`
to generate automated Gallery and Camera-simulation results. Camera simulation uses
the decoded payload plus a perspective-corrected QR crop; it is not a substitute for
the phone's physical Live Camera evidence. Structural cards are derived from the
recorded production dataset and therefore are not independent performance evidence.
Rebuilding them requires the local/private exact-app capture dataset; the cards,
manifest and hashes are the public demonstration artefacts.

## 中文说明

这个资料包用于向 supervisor 展示已经部署的 QRGuard，不是新的训练集。
先打开 `PRESENTATION_DEMO.html`，或按照 `QUICK_DEMO_ORDER.csv` 扫描 15 个核心案例。
Live Camera 情况下，把图片
显示在另一个屏幕或打印出来。Structural 图片已经包含当时记录的 angle、glare、far
等情况，请正常扫描，不要再叠加一次环境变化。Gallery 可以使用同一张 PNG 做 parity
check。扫描后把结果和 screenshot 文件名填写进 `ACTUAL_RESULTS.csv`。不要打开 QR
内的 destination。
