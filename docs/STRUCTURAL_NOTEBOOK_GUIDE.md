# Structural CNN Notebook — Phase-by-Phase Code Guide

Explains `training/structural_efficientnet_3class.ipynb`: one EfficientNet-B0, 3-class
(clean / adversarial / tampered). For report writing and viva defence.
供写报告和答辩:逐 phase 讲解代码作用、原理、如何看输出。

> Consolidates FYP1's two image-level detectors (adversarial CNN + structural-feature RF)
> into ONE 3-class CNN. Reuses FYP1's EfficientNet-B0 + 224×224/ImageNet preprocessing +
> FGSM/PGD generation. Tampered class = synthetic (Option B). Design rationale is in
> `PROGRESS.md` and this repo's discussion history.

---

## Why one 3-class CNN 为什么用一个三分类 CNN

FYP1 proved adversarial noise and physical tampering are **orthogonal threats** (adversarial
leaves QR structure intact; tampering breaks finder patterns). FYP1 handled them with two
separate models (EfficientNet-B0 + Random-Forest-on-14-features). For **real-time deployment**
we consolidate into **one EfficientNet-B0 with a 3-way head**: one model, one preprocessing,
one ONNX file — no separate OpenCV feature pipeline (which FYP1 itself flagged as a latency
cost). Fusion consumes `p_structural = 1 − P(clean)`; the UI shows the predicted type.

> **中文辅助:** adversarial 和 tampering 是两种正交威胁,FYP1 用两个模型(CNN+RF)。FYP2 为
> 了实时部署合并成**一个 EfficientNet-B0 三分类头**:一个模型、一套预处理、一个 ONNX,省掉
> OpenCV 特征提取(FYP1 自己都说它是延迟负担)。fusion 用 `p_structural = 1 − P(clean)`。

---

## Phase 0 — Setup
Installs `qrcode`, `torchattacks`, ONNX tools; mounts Drive; fixes seeds; sets constants
(224×224, ImageNet mean/std, `CLASS_NAMES = [clean, adversarial, tampered]`). Confirm
`Device: cuda / Tesla T4`.

> **中文:** 装库 + 挂 Drive + 固定种子 + 常量。确认是 T4 GPU。

## Phase 1 — Clean QR base set 干净 QR 基础集
Generates ~2,500 **real QR codes** with the `qrcode` library from varied contents (URLs,
Wi-Fi, text) at random versions/error-correction/box-sizes. QR **content is irrelevant** to
structural analysis — only the images matter — so generation is fully self-contained,
reproducible, and needs no download. (Set `USE_FIGSHARE=True` to use Figshare QRv2 from
Drive instead, for FYP1 continuity.)

**Why generate:** controllable, reproducible, no dataset licensing, and every clean QR is a
genuine valid code. **Read output:** "generated 2500/2500".

> **中文:** 用 qrcode 库生成 ~2500 个真实 QR(内容随机,结构分析不看内容)。完全自包含、可复现、
> 无需下载。也可改用 Figshare QRv2 保持 FYP1 连续性。

## Phase 2 — Split first, then derive the 3 classes 先切分再生成
Splits the base clean QRs 70/15/15 **before** any manipulation, then for each base image
creates: class 0 = clean copy, class 1 = **adversarial** (FGSM or PGD, random eps, ResNet-18
victim — FYP1's method), class 2 = **tampered** (synthetic). Every derived image stays in its
base image's split → **no leakage**. Result: 3 balanced classes per split.

**Synthetic tampering (Option B)** applies 1–2 of: `sticker` (opaque rectangle overlay),
`occlude` (black/white patch), `finder` (corrupt a corner finder pattern), `blur` (Gaussian),
`scratch` (random lines). These mirror real quishing attacks (sticker overlay is the most
common real-world QR fraud) and are fully controllable.

**Why split-first:** if you split *after* generating, an adversarial/tampered copy of a train
QR could land in test → leakage → inflated scores. **Read output:** per-split counts (train
≈ 5250, val/test ≈ 1125 each).

> **中文:** 先把干净 QR 切 70/15/15,再对每张生成 clean/adversarial/tampered 三个版本 —— 派生图
> 留在同一 split,**防泄漏**(FYP1 的 split-first 策略)。tampering 合成 = 贴纸/遮挡/finder 损坏/
> 模糊/划痕(贴纸覆盖是最常见的真实 QR 诈骗)。adversarial 沿用 FYP1 的 FGSM/PGD + ResNet-18 victim。

## Phase 3 — Fine-tune EfficientNet-B0 (3-class) 微调
Transfer learning from ImageNet; the classifier head is replaced with a 3-way `Linear`.
Adam (lr 1e-4), CrossEntropy, ReduceLROnPlateau, 15 epochs, best-by-val-accuracy checkpoint —
the same recipe family as FYP1. **Read output:** `val_acc` rising per epoch.

> **中文:** ImageNet 迁移学习,分类头换成 3 类。Adam + CrossEntropy + 学习率衰减 + 按验证准确率
> 存最佳 —— 和 FYP1 同一套配方。看每个 epoch 的 val_acc 上升。

## Phase 4 — Evaluation 评估(分类别 + 混淆矩阵)
Reloads the best checkpoint fresh; prints per-class precision/recall/F1 and saves the
confusion matrix. **The key thing to check:** BOTH `adversarial` and `tampered` recall are
high — that's the whole point of one CNN covering both threats. The confusion matrix shows
whether the model confuses the two manipulation types (acceptable) or confuses either with
clean (bad — that's a missed attack).

> **中文:** 重载最佳模型,报告**每一类**的 precision/recall/F1 + 混淆矩阵。**重点看** adversarial
> 和 tampered 的 recall 都要高(这就是一个 CNN 覆盖两种威胁的意义)。最怕把它们和 clean 混淆(=漏检)。

## Phase 5 — Temperature calibration 概率校准
Fits one temperature T on validation logits; reports ECE (on the manipulated-vs-clean view,
which is what fusion uses) before/after. Ships as `temperature.json`. The backend computes
`p_structural = 1 − softmax(logits/T)[clean]`.

**Why:** fusion combines this probability with the semantic branch, so it must be honest, not
over-confident. **Read output:** ECE after ≤ before.

> **中文:** 用验证集拟合温度 T,让概率"说话算话"(fusion 要用)。看 ECE 校准后下降。backend 用
> `p_structural = 1 − softmax(logits/T)[clean]`。

## Phase 6 — p_structural behaviour p_structural 行为检查
Prints mean `p_structural` per true class: `clean` should be LOW, `adversarial` and
`tampered` HIGH; plus manipulated-vs-clean accuracy at threshold 0.5. This is the direct
check that the deployed signal is usable by fusion.

> **中文:** 打印每个真实类别的平均 p_structural:clean 要低,adversarial/tampered 要高。这是"部署
> 信号能不能用"的直接判据。

## Phase 7 — Export, quantize, benchmark 导出量化与延迟
ONNX export → dynamic INT8 quantization → accuracy guard (≤ 2 pp drop else deploy FP32) →
single-image CPU latency (median/P95) → `predict_structural(pil_image)` returning
`p_structural`, `predicted_type`, and per-class probs. This is the exact function the backend
`structural_service.py` will call. **Read output:** the drop (≤ 2 pp), latency (should be
tens of ms), and the demo (clean → low p_structural, adversarial/tampered → high).

> **中文:** 导出 ONNX → INT8 量化 → 掉分 ≤2pp 检查 → CPU 延迟 → 定义 `predict_structural()`
> (backend 就调它)。看掉分、延迟、demo(clean 低分、被动过的高分)。

---

## After the run 跑完之后
1. Download `MyDrive/FYP2/structural/artifacts/` → repo `training/artifacts/structural/`
   (`structural_int8.onnx` or fp32 per `deploy_choice.json`, `temperature.json`,
   `metrics_summary.json`). Keep `eval/confusion_matrix.png` for the report.
2. Fill the structural section in `REPORT_NOTES.md`; update `PROGRESS.md`.
3. Then build `structural_service.py` (backend inference around these artifacts).
