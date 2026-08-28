# Method 1 Training Notebook — Phase-by-Phase Code Guide

Explains what every phase of `training/method1_finetune_domurls_bert.ipynb` does, why,
and how to read its output. Written for report writing and viva defence.
供写报告和答辩用:逐 phase 讲解代码作用、原理、如何看输出。

> Current version: **RUN 3** (combined PhiUSIIL + malicious_phish + Tranco benign).
> Design history (RUN 1 → RUN 2 → RUN 3) is recorded in `PROGRESS.md` / `REPORT_NOTES.md`.

---

## The big picture 整体流程

The notebook turns raw URL datasets into a deployable phishing classifier:
**load data → leakage-safe split → fine-tune a URL-pretrained Transformer → evaluate →
calibrate probabilities → sanity-check on real URLs → export a fast CPU model.**
Each phase writes its outputs to Google Drive and **skips itself if already done**, so a
Colab disconnect never loses work (just *Run all* again).

| Phase | Role | Key output on Drive |
|---|---|---|
| 0 | Environment + paths | (none — sets variables) |
| 1 | Build the labelled corpus | `splits/combined_clean.parquet` |
| 2 | Leakage-safe train/val/test split | `splits/{train,val,test}.parquet` |
| 3 | Fine-tune the model | `best_model/` |
| 4 | Measure accuracy (overall + per source) | `eval/metrics_test.json`, plots |
| 5 | Calibrate probabilities | `artifacts/temperature.json` |
| 6 | Real-world sanity check | `eval/sanity_set.json` |
| 7 | Export fast CPU model + latency | `artifacts/model_quant.onnx`, `metrics_summary.json` |

---

## Phase 0 — Setup 环境与路径

**What the code does:** installs libraries (`transformers`, `datasets`, `onnxruntime`,
`optimum`, `tranco`, …), mounts Google Drive, fixes all random seeds to 42, and defines
the folder paths under `RUN_TAG` (`run3_augmented`).

**Why it matters:**
- **Seeds** → reproducibility: the same run gives the same numbers (required for a report).
- **`RUN_TAG` subfolder** → each experiment (RUN 1/2/3) is isolated, so results never
  overwrite each other and can be compared.
- **Drive mount** → persistent storage; Colab's own disk is wiped on disconnect.

**Read the output:** confirm `Device: cuda` and `GPU: Tesla T4`. If it says CPU, enable
the GPU (Runtime → Change runtime type) before Phase 3, or training takes ~10× longer.

> **中文辅助:** Phase 0 = 装库 + 挂 Drive + 固定随机种子 + 设好 `run3_augmented/` 路径。
> 关键看输出里是不是 `Tesla T4`;固定 seed 是为了报告能复现同样的数字。

---

## Phase 1 — Build the labelled corpus 构建训练语料

**What the code does:** loads three sources, reduces each to `url` + binary `label`
(**1 = phishing/malicious, 0 = benign**) + a `source` tag, then combines, removes
label-conflicting and duplicate URLs, and saves one clean table.

- **PhiUSIIL** (UCI #967): majority class = legitimate → label 1 = the minority (phishing).
- **malicious_phish** (Kaggle): `type != 'benign'` → 1 (phishing/malware/defacement all
  count as dangerous — what Method 1 must flag).
- **Tranco top-150k domains → benign** (the RUN 3 fix): real famous domains (incl. genuine
  paypal/maybank/google) added as benign. Half get a real path sampled from the fraud
  datasets' benign URLs so the augmented URLs look structurally like phishing.

**Why the design choices:**
- **Only the URL string is used** — all 50+ handcrafted feature columns are dropped. Method 1's
  whole point is to learn from the raw string (a URL-pretrained Transformer's strength).
- **Tranco augmentation** breaks the *brand-keyword shortcut* discovered in RUN 2 (the model
  had learned "brand word ⇒ phishing" and flagged real paypal.com). Adding legit brand
  domains as benign teaches the opposite.
- **Path sampling** avoids creating a new shortcut ("homepage ⇒ benign, has path ⇒ phishing").

**Read the output:** the per-source `groupby` table shows how many benign/phishing each
source contributed; the combined label balance should be roughly 60–65% benign after adding
Tranco.

> **中文辅助:** Phase 1 = 把三个来源统一成 `url + label(1=钓鱼)`,合并去重。RUN 3 的关键是
> 加入 **Tranco 真实知名域名当 benign**,直接破解 RUN 2 的"brand 词=钓鱼"捷径。只用 URL
> 字符串、丢掉手工特征,是因为 Method 1 就是要靠 Transformer 学字符串本身。

---

## Phase 2 — Leakage-safe split 防泄漏切分

**What the code does:** extracts each URL's **registered domain** (via tldextract), then
assigns whole domain groups to train/val/test (70/15/15), stratified by the domain's
majority label. Asserts the three domain sets are disjoint. Subsamples train to 200k to
keep T4 runtime ~1–2 h. Keeps the `source` tag in each split.

**Why it matters — this is the single most important correctness safeguard:** if you split
by *URL* instead of *domain*, near-identical URLs from the same site (e.g.
`site.com/a`, `site.com/b`) land in both train and test → the model "memorises" the domain
and the test score is falsely inflated (data leakage). Splitting by domain guarantees the
test set contains **only domains the model never saw in training**, so the metrics reflect
true generalization.

**Read the output:** "Domain sets disjoint: OK" must appear. The per-split counts show how
many URLs and the phishing ratio in each.

> **中文辅助:** Phase 2 = 按**注册域名**切分(不是按 URL),保证 test 里的域名训练时从没见过。
> 这是防 data leakage 最关键的一步 —— 按 URL 切会让同站点的相似 URL 泄漏到 test,分数虚高。
> 必须看到 "Domain sets disjoint: OK"。

---

## Phase 3 — Fine-tuning 微调模型

**What the code does:** loads `amahdaouy/DomURLs_BERT` (a BERT pretrained on URLs/domains)
and attaches a fresh 2-class classification head. Trains 3 epochs with the HuggingFace
`Trainer`: learning rate 2e-5, 10% warmup, fp16, **early stopping on validation F1**, keeping
the best checkpoint. Falls back to `bert-base-uncased` with a loud warning if the model
can't load (so a report claim can be corrected).

**Why the design choices:**
- **URL-pretrained model, not generic BERT** → it already understands URL structure; fine-tuning
  on our labels is fast and data-efficient. (This is the "latest method" justification for the
  report — see `docs/design/SEMANTIC_MODULE_SPECIFICATION.md` and the DomURLs_BERT paper.)
- **Early stopping on F1** → stops when validation F1 stops improving, preventing overfitting.
- **fp16** → half-precision training, ~2× faster on the T4.
- The message *"Some weights … newly initialized: ['classifier.weight']"* is **normal** — it
  just means the new classification head starts random and gets trained.

**Read the output:** the epoch table — validation F1 should rise then plateau. `Phase 3 complete`
means the best model is saved to `best_model/`.

> **中文辅助:** Phase 3 = 加载 URL 预训练的 DomURLs_BERT + 新分类头,微调 3 个 epoch,按验证
> F1 早停留最佳。用 URL 专用预训练模型(而非通用 BERT)是报告里"最新方法"的依据。看到
> "classifier.weight newly initialized" 是正常的(新分类头随机初始化后再训练)。

---

## Phase 4 — Evaluation 评估(总体 + 分来源)

**What the code does:** reloads the best model *fresh from Drive* (proving it doesn't depend
on in-memory training state), runs it on the held-out test set, and reports accuracy,
precision, recall, F1, ROC-AUC — **overall and broken down per source** (PhiUSIIL vs
malicious_phish vs Tranco). Saves a confusion matrix and ROC curve, plus 10 false
positives / 10 false negatives for error analysis.

**Why the per-source breakdown:** RUN 1 looked perfect overall but had ROC-AUC 0.53 on the
*other* dataset. Reporting per-source AUC exposes whether the model works across
distributions or just memorised one. Both per-source AUCs being high = the cross-dataset
shortcut is gone.

**Read the output:** `overall.roc_auc` and each `per_source.*.roc_auc`. The saved
`false_positives.csv` / `false_negatives.csv` are gold for the report's error-analysis section.

> **中文辅助:** Phase 4 = 重新从 Drive 加载模型(证明不依赖内存状态),在 test 上评估,并**按来源
> 分开报告 AUC**。这是为了戳穿"总体分高但换个分布就崩"的假象。误报/漏报的 CSV 是报告 error
> analysis 的好素材。

---

## Phase 5 — Probability calibration 概率校准

**What the code does:** fits a single scalar **temperature T** on the *validation* logits
(LBFGS minimising NLL), then reports **Expected Calibration Error (ECE)** on the test set
before vs after dividing logits by T. Saves T to `temperature.json`.

**Why it matters:** a raw neural network is often over-confident — it may output 0.95 when it
is really right only 80% of the time. The Fusion Engine combines Method 1's probability with
others, so that probability must be **honest**. Temperature scaling rescales confidence so
`p_url` means what it says. ECE going *down* after calibration = better-calibrated.

**Read the output:** `T = …` and `ECE … -> …` (after should be ≤ before). The backend loads
this T and computes `p_url = softmax(logits / T)`.

> **中文辅助:** Phase 5 = 用验证集拟合一个温度 T,让模型输出的概率"说话算话"(神经网络常
> 过度自信)。Fusion 要用这个概率,所以必须校准。看 ECE 校准后是否下降。

---

## Phase 6 — Real-world sanity check 真实世界常识检查

**What the code does:** runs the model on ~20 hand-labelled **well-known URLs** (real google,
youtube, maybank, paypal, utar as benign; obvious phishing patterns as phishing) and prints
each score, flagging mistakes with `!!`.

**Why it exists:** this is the check that caught the RUN 2 failure — the model scored real
google.com as 0.996 phishing. In-distribution metrics (Phase 4) can look perfect while the
model fails on obvious real inputs. **This phase is the direct pass/fail test for RUN 3.**

**Read the output:** `Sanity accuracy` should be ≥ 0.9, and specifically the benign famous
sites (google, maybank, paypal) should score **low**. If they still score high, the shortcut
persists and Method 1 needs more work (or leans on Method 2 in fusion).

> **中文辅助:** Phase 6 = 用一批人工标注的知名 URL 做常识检查 —— 就是它抓出 RUN 2 把 google
> 判成 0.996 的问题。**这是 RUN 3 成败的直接判据**:sanity accuracy 要 ≥ 0.9,且 google/
> maybank/paypal 要评低分。

---

## Phase 7 — Export, quantize, benchmark 导出量化与延迟

**What the code does:**
1. Exports the fine-tuned model to **ONNX** (a portable, framework-independent format).
2. Applies **dynamic INT8 quantization** (weights 32-bit float → 8-bit int) → smaller, faster.
3. **Accuracy guard:** compares F1 of PyTorch vs ONNX-FP32 vs ONNX-INT8 on 2,000 test URLs;
   if INT8 loses > 2 percentage points, it deploys FP32 instead (project policy).
4. **Latency benchmark:** median/P95 single-URL inference time on CPU for all three.
5. Defines `predict_url(url) -> p_url` — the exact function the backend will call — and demos it.

**Why it matters:** the app must run on a CPU backend within the latency budget. Quantization
makes inference ~2× faster (RUN 2: 31 ms/URL INT8) with negligible accuracy loss. This phase
produces the actual deployable artifact.

**Read the output:** the `drop … pp` line (should be ≤ 2), the latency table (INT8 median
should be well under 150 ms), and the `predict_url` demo (benign low, phishing high — the
final sanity confirmation).

> **中文辅助:** Phase 7 = 导出 ONNX → INT8 量化(更小更快)→ 检查掉分是否 ≤2pp(否则回退 FP32)
> → 测 CPU 延迟 → 定义并演示 `predict_url()`(backend 就调这个函数)。看掉分、延迟、demo 三样。

---

## After the run 跑完之后

1. Download Drive `MyDrive/FYP2/method1/run3_augmented/artifacts/` → repo
   `training/artifacts/` (gitignored). Contents: `model_quant.onnx` (or FP32 if the 2 pp
   policy triggered — see `deploy_choice.json`), `temperature.json`, tokenizer files,
   `metrics_summary.json`.
2. Also keep `eval/*.png` and `false_*.csv` for report figures.
3. Fill the RUN 3 blanks in `REPORT_NOTES.md`; update the status in `PROGRESS.md`.
4. Only then wire `method1.py` (backend inference around these artifacts) into the pipeline.
