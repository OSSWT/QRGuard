# Structural v3 local training results — 2026-08-30

Version: **`structural-2026.03-r01` — LATEST CANDIDATE**
Status: **research gates passed; deployment gates failed; not deployed**

> Historical pre-real result. The audited 100x3 dataset was imported after this
> run. See `STRUCTURAL_V3_REAL_100X3_BASELINE_2026-08-30.md` for its locked
> real-camera baseline and `ml_training/CURRENT_CHECKPOINT.md` for current work.

## 给老师或非技术用户的短解释

QRGuard 现在已经训练出一个新的候选模型，让 Gallery 和 Live Camera
可以使用同一套 Structural AI。模型先检查图片是否可用，再判断 QR code
是 clean、adversarial 或 tampered。曝光、模糊、距离、反光和透视本身不是
恶意攻击；图片严重不可用时，系统应要求用户重新扫描，而不是猜测它是
malicious。

这次研究测试表现良好，但还不能说它已经解决真实手机环境的问题。原因是
项目目前没有已标注的 exact app-camera 与 paired Gallery/Camera 测试样本。
所以新模型保持 candidate，旧 Gallery RUN 5 和 Camera 2026.02 仍是 app
默认模型。

## 本次实际训练

- Architecture: ImageNet-pretrained ResNet-18, RGB 224×224.
- Training: 2 head epochs + 5 layer-4 fine-tune epochs, all completed locally
  on CPU.
- Best checkpoint: epoch 5; validation macro-F1 0.9555 and QR-DN validation
  clean false-positive rate 0.0000.
- Manifest: 10,597 rows, group-disjoint, no split leakage.
- Train / validation / grouped test / external holdout rows:
  6,367 / 1,440 / 540 / 2,250.
- Exact QRGuard app runtime holdout rows: **0**.

## 独立测试结果

| Metric | Result |
|---|---:|
| Grouped synthetic test accuracy | 0.9426 |
| Grouped synthetic macro-F1 | 0.9435 |
| Clean recall | 0.9889 |
| Adversarial recall | 0.9111 |
| Tampered recall | 0.9278 |
| QR-DN external clean false-positive rate | 0.0000 |
| Expected calibration error (ECE) | 0.0194 |
| ONNX/PyTorch maximum probability difference | 0.00000137 |
| ONNX P95 latency on this local CPU | 39.88 ms |

These values pass the configured **research** gates. They do not pass the
real-device deployment contract.

## Controlled quality-condition results

These are controlled simulations inside the grouped test set. They show model
development direction, not final real-camera performance.

| Condition | Rows | Accuracy | Clean FPR | Tampered recall |
|---|---:|---:|---:|---:|
| Defocus blur | 32 | 1.0000 | 0.0000 | 1.0000 |
| Far distance | 36 | 0.9444 | 0.0000 | 0.8824 |
| Glare | 23 | 0.9565 | 0.0000 | 0.9167 |
| Motion blur | 35 | 0.9143 | 0.0000 | 0.8125 |
| Normal | 258 | 0.9264 | 0.0256 | 0.9487 |
| Overexposure | 24 | 0.9583 | 0.0000 | 0.9231 |
| Perspective | 40 | 0.9250 | 0.0526 | 0.9048 |
| Screen moiré/compression | 34 | 0.9706 | 0.0000 | 0.9500 |
| Shadow | 26 | 1.0000 | 0.0000 | 1.0000 |
| Underexposure | 32 | 0.9688 | 0.0000 | 0.9444 |

The largest controlled clean false-positive rate is 0.0526 on perspective.
This is a priority real-camera validation slice. Non-normal adversarial recall
is intentionally blank: the current FGSM/PGD data are digital-input attacks.
Claiming that ordinary post-processing preserves an adversarial label would be
invalid; physical adversarial robustness needs EOT and/or real recapture.

## Gallery 与 Camera 一致性检查

With the v3 artifact enabled through the local opt-in environment variable, one
clean test image from each of the 10 quality conditions was sent through both
Gallery and Camera routing. All 10/10 cases returned identical quality status,
predicted class and probability. This verifies same-artifact wiring for the
same pixels.

It is **not** the final paired consistency result. Final evidence must compare a
Gallery original and a separately captured Camera image of the same physical QR
under real acquisition conditions.

## 为什么目前不能部署

The capture audit currently records:

- 0 labelled Camera sessions for clean, adversarial and tampered;
- 0 independent Camera test groups;
- 0 paired Gallery/Camera test groups;
- 0 real Camera sessions for each quality condition.

The locked research scope is 50 independent Camera cases per class, including
10 Camera test groups and 10 paired Gallery/Camera test groups per class. Each
class has five Camera sessions for every configured quality condition. This is
a research evaluation scope and does not satisfy the separate deployment gate.

## Checkpoint 与快速重开

Local reusable state is under:

```text
ml_training/structural/runs/structural-2026.03-r01/checkpoints/
  best_model.pt
  last_checkpoint.pt
  run_state.json
```

The generated performance bundle is under:

```text
ml_training/structural/performance/structural-2026.03-r01/
```

`report_only` displays the saved report without training. `evaluate_only`
reloads `best_model.pt` and regenerates fixed metrics without running epochs.
Colab should store its independent run under:

```text
MyDrive/QRGuard_ML/runs/structural-2026.03-r01/<RUN_ID>/
```

Use the same `RUN_ID` for `resume`, `evaluate_only`, or `report_only`. Do not
copy this candidate into deployed artifacts until real-camera, paired,
decision-layer and end-to-end gates pass.
