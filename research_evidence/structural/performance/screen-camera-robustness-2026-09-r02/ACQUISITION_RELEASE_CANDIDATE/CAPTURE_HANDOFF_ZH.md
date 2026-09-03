# QRGuard r02 无打印屏幕采集说明

## 这次测试的目的

这不是再次盲目扩大 dataset，也不是直接训练或部署模型。它用 24 个短
session 同时验证以下四个问题：

1. SEM-11 的 Version 3 / 29×29 / 短 payload 是否仍会因曝光变化乱判。
2. SEM-05 的恶意 userinfo URL 是否始终由 Semantic 分支维持 Blocked，
   不会被干净的 Structural 图像掩盖。
3. Version 10 与 Version 14 长 payload 是否达到至少 5 pixels/module；
   达不到时必须要求靠近或重扫，不能猜测 Safe。
4. 正常、过曝、欠曝条件下，AF/AE/AWB、EV 调整、调后重采与五帧质量门
   是否稳定工作。

整个流程只使用屏幕。不要打印；viewer scale 最高为 100%，绝不超过
100%。

## 使用文件

- 安装：`QRGuard_Diagnostic_Acquisition_Validation_1.1.4+8011_2026-09-r02.apk`
- 在另一块屏幕解压并打开：`Acquisition_Validation_2026-09-r02.zip`
- 卡片顺序：解压目录内的 `CAPTURE_ORDER.csv`
- 卡片位置：解压目录内的 `cards/`

诊断 APK 与普通 APK 使用相同 package。测试完成后，可以安装普通 r02
APK 覆盖回来。第一次安装本 campaign 时不需要清除 QRGuard 数据。

## 三个条件

每个条件包含相同的 8 张卡，每张只需要一个自动 session；每个 session
由 App 自动保存 5 个合格的时序 crop。

| App 标签 | 图片查看器比例 | 显示器亮度 | 用途 |
|---|---:|---:|---|
| `80% / B50` | 80% | 约 50% | 基线 |
| `100% / B100` | 正好 100% | 100% | 过曝压力 |
| `100% / B30` | 正好 100% | 约 30% | 欠曝压力 |

不要求亮度读数精确到实验室仪器；只需同一条件的 8 张卡保持相同亮度、
环境灯、显示器与相机。不要在一个 session 中途改变亮度。

## 每个 session 的操作

1. 在电脑或第二台设备上只显示 `CAPTURE_ORDER.csv` 指定的单张卡；画面中
   不要出现第二个 QR。
2. 在诊断 App 中选择同名 case 与当前条件。
3. 点击 `Arm session`，将 QR 保持在取景框内并自然持稳。
4. App 会先以 QR 中心请求 AF/AE/AWB。如果像素显示明显过曝或欠曝，最多
   调整一次 EV，并自动丢掉调整前的所有帧。
5. App 只保存通过 Structural crop quality gate 的帧。看到 rejected、move
   closer 或 reduce glare 时，按提示调整；不要为了得到某个 label 人工挑帧。
6. 等待进度达到 `5/5` 并显示 session saved，再换下一张卡。
7. 完成当前条件的 8 张卡后，再切换 viewer scale 和显示器亮度。

若 V10/V14 很难完成，先让手机靠近，不要把图片查看器放大到 100% 以上。
靠近是相机采集尺度的一部分；放大超过 100% 会改变或遮挡参考卡，破坏对照。

## 完成与导出

正常完成时应显示：

- 24 / 24 sessions
- 120 个保存 crop
- 每个 case × condition 只有一个 session

点击右上角 ZIP 图标。文件会保存到 Android
`Downloads/QRGuard/`。把完整 ZIP 复制回电脑后直接给 Codex，不要重新压缩、
改名内部文件、删除 metadata 或挑选图片。

## 自动验收规则

收到 ZIP 后会先运行安全验证和采集审计，再运行锁定 r01 模型 replay：

- archive 必须正好 24 sessions / 120 frames，payload 只保留 SHA-256。
- 保存的 Structural crop 中 `unusable` 必须为 0。
- 每一帧已知版本的 observed scale 必须至少 5 pixels/module。
- 每个 session 最多一次 EV 调整，保存 burst 内曝光状态必须一致。
- SEM-11 在三个曝光条件中 false Blocked 必须为 0；低质量允许 Rescan，
  但不能因证据不足变成 Safe。
- SEM-05 的 masked branch error 必须为 0，三个条件都必须保持语义风险。
- adversarial / tampered 不允许 majority false Safe。
- 曝光条件之间的 verdict agreement 至少 95%。本矩阵只有 8 个 case，实际
  含义是 8 个 case 都必须保持一致。
- clean case 的跨曝光 `p_structural` span P95 不得超过 0.15。

这些是 acquisition development gates。即使全部通过，也不能单独证明 r02
模型可部署；还必须完成 GPU 训练以及新的 device/display/session blind
holdout。

## 返回文件后会自动执行

```powershell
python scripts/audit_acquisition_validation.py <你的ZIP>
python scripts/analyze_live_camera_diagnostic.py <你的ZIP> `
  --plan app/assets/capture/acquisition_validation_plan.json `
  --output research_evidence/structural/performance/screen-camera-robustness-2026-09-r02/MODEL_REPLAY
```

第一条验证 App 实际采集行为；第二条验证锁定模型和最终决策。两者职责不同，
不会用模型 label 来筛选采集帧。
