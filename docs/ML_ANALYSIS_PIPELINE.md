# Method 1 & Structural — Full Explainer (Beginner-Friendly)

A complete, plain-language walkthrough of the two AI models we built, the tools used, what
they output, and how those outputs flow into the Fusion Engine. Written for someone new to
machine learning. 给新手看的完整讲解:两个 AI 模型做了什么、用什么工具、输出是什么、怎么进 fusion。

---

# Part 0 — The big picture 全局图

QRGuard analyses a scanned QR code from **two independent angles**, then combines them:

```
                 ┌─────────────────────────────────────────┐
   QR image  ───▶│ STRUCTURAL model — looks at the PICTURE  │──▶ p_structural (0–1)
                 │ "Is the QR image itself manipulated?"    │──▶ predicted_type
                 └─────────────────────────────────────────┘
                 ┌─────────────────────────────────────────┐
 decoded URL ───▶│ METHOD 1 model — looks at the TEXT/URL   │──▶ p_url (0–1)
                 │ "Does the link look like phishing?"      │
                 └─────────────────────────────────────────┘
                                    │
                                    ▼
                        FUSION ENGINE combines both
                        (+ rules + Method 2 LLM)
                                    ▼
                     one risk score 0–100 → Safe / Warning / Blocked
```

**Why two models?** A fraud QR can attack in two totally different ways:
1. The **image** is tampered (a sticker stuck over a real QR) — the *picture* is wrong.
2. The **link** is phishing (a clean-looking QR that points to a fake bank site) — the
   *content* is wrong.
One model cannot see both, so we built one for each. This document explains both.

> **中文:** QRGuard 从两个独立角度看一个 QR:**Structural** 看**图片**(图被没被动过手脚),
> **Method 1** 看**解码出来的 URL 文字**(链接像不像钓鱼)。两种诈骗方式完全不同,所以要两个模型。

---

# Part 1 — METHOD 1: the URL / text model 语义模型

## 1.1 What problem it solves 解决什么问题

A QR code often contains a **URL** (a web link). Method 1 reads that link *as text* and
predicts: **is this link phishing (dangerous) or legitimate (safe)?** — WITHOUT opening it.

Example: it should look at `http://paypal-secure-verify.top/login` and say "this looks like
phishing" just from the shape of the text.

## 1.2 What tool/model we used — DomURLs_BERT

**BERT** is a type of AI model called a **Transformer**. Think of it as a model that reads
text the way you read a sentence — it looks at each piece and understands it *in context*
(the meaning of "bank" depends on the words around it). BERT was a breakthrough because it
reads text in both directions at once.

Normal BERT was trained on ordinary English (Wikipedia, books). But a URL is not ordinary
English — it has dots, slashes, weird domains. So we used **DomURLs_BERT**: a version of BERT
that the authors already **pre-trained on millions of URLs and domain names**. It already
"speaks URL". We just had to teach it OUR specific task (phishing vs legit).

- **Pre-training** (done by the paper's authors, not us): the model reads millions of URLs to
  learn the general structure of web addresses. Like a student who read a whole library.
- **Fine-tuning** (what WE did): we take that knowledgeable model and train it a bit more on
  labelled examples (this URL = phishing, that URL = legit) so it specialises in our task.
  Like giving that well-read student a focused exam-prep course.

**Tools used:** Python, PyTorch (the deep-learning engine), HuggingFace `transformers` (the
library that gives us DomURLs_BERT and the training loop), Google Colab (free cloud computer
with a T4 GPU — a chip that makes training fast), the `datasets` library, scikit-learn (for
metrics), ONNX Runtime (to run the model fast at deployment).

## 1.3 What data we trained on 用什么数据

The model learns from **examples of real URLs, each labelled phishing (1) or legit (0)**:

| Dataset | What it is | Size |
|---|---|---|
| **PhiUSIIL** | A public academic dataset of phishing + legit URLs | 235,795 URLs |
| **malicious_phish** | Another public URL dataset (Kaggle) | 651,191 URLs |
| **Tranco top domains** | The world's most-visited real websites (added as "legit") | 150,000 domains |

We combined all three → about 1 million URLs → the model learns from these.

## 1.4 What we actually did — the 3-run journey 我们做了什么(三次迭代)

We trained three times, because the first two revealed problems (this is normal ML work, and
it is GREAT material for your report — it shows you can diagnose and fix models):

- **RUN 1 (PhiUSIIL only):** scored 99.9% on its own test set BUT failed completely on a
  different dataset (it had memorised a quirk of PhiUSIIL, not real phishing). Lesson:
  **"looks perfect on your own data" can be an illusion** (called *shortcut learning*).
- **RUN 2 (added malicious_phish):** fixed the cross-dataset problem (now ~99% on both) BUT
  scored real `google.com` as phishing. Reason: brand words like "paypal/maybank" appear
  mostly in phishing URLs in the training data, so it learned "brand word = danger" — and
  flagged the REAL brand sites too.
- **RUN 3 (added Tranco real top domains as legit):** taught the model that famous domains
  are safe. Now `google.com` → 0.017 (safe ✓), all phishing still caught (10/10). A small
  residual bias remains on a few strong brands (paypal/maybank) — this is handled later by
  Method 2 (the LLM, which *knows* the real paypal.com) and the Fusion Engine. **We accepted
  RUN 3 as the final Method 1.**

**The step-by-step training process (each RUN, done in the Colab notebook):**
1. **Load & label data** — read the URLs, mark each 1 (phishing) or 0 (legit).
2. **Split safely** — divide into train / validation / test sets **by registered domain** so
   the model is always tested on websites it never saw in training (prevents cheating, called
   *data leakage*).
3. **Fine-tune** — show the training URLs to DomURLs_BERT for 3 passes (*epochs*), adjusting it
   to get better at phishing detection. Keep the best version.
4. **Evaluate** — measure accuracy/precision/recall/F1/ROC-AUC on the untouched test set.
5. **Calibrate** — adjust the model's confidence so its probabilities are honest (see 1.6).
6. **Sanity check** — test on famous real URLs (google, maybank…) to catch silly mistakes.
7. **Export** — save the model in ONNX format so the backend can run it fast on a normal CPU.

## 1.5 A few key terms, simply 几个关键词

- **Epoch:** one full pass through all the training data. We did 3.
- **Accuracy / Precision / Recall / F1:** ways to measure how good the model is.
  - *Recall* = of all the real phishing, how many did we catch? (Method 1 got 10/10 on the
    sanity phishing — excellent; catching phishing is the most important job.)
  - *Precision* = of everything we called phishing, how many really were?
  - *F1* = a balance of the two.
  - *ROC-AUC* = overall ability to separate phishing from legit (1.0 = perfect, 0.5 = random).
    RUN 3 got ~0.99.
- **GPU (T4):** a special chip in Colab that trains models ~10× faster than a normal CPU.
- **ONNX + quantization:** ONNX is a portable file format for the trained model; quantization
  shrinks it (32-bit → 8-bit numbers) to run faster. For Method 1 this gave 31 ms per URL.

## 1.6 Calibration — why the probability must be "honest" 校准

A raw model might say "90% phishing" when it is really right only 70% of the time — it is
*over-confident*. **Temperature scaling** gently rescales the numbers so "90%" really means
90%. This matters because the Fusion Engine later trusts these probabilities, so they must be
truthful. For Method 1 the temperature was ~2.2.

## 1.7 What Method 1 OUTPUTS 输出是什么

For one URL, Method 1 returns a single number:

```python
p_url = 0.93   # a probability from 0.0 (definitely legit) to 1.0 (definitely phishing)
```

Real examples from our final model:
```
https://www.google.com/maps                     → p_url = 0.017  (safe)
http://paypal-secure-verify.top/login/update.php → p_url = 0.990  (phishing)
http://203.0.113.7/account/confirm               → p_url = 0.992  (phishing)
```

**That single number `p_url` is what goes to the Fusion Engine.** (See Part 3.)

---

# Part 2 — STRUCTURAL: the image model 图像模型

## 2.1 What problem it solves 解决什么问题

This model looks at the **QR code image itself** (not the link) and predicts whether the
picture has been **manipulated**. There are two ways a QR image can be attacked:
- **Adversarial noise** — invisible pixel changes designed to fool AI (the QR looks normal to
  you but the pixels are subtly poisoned).
- **Physical tampering** — visible damage: a sticker stuck over part of it, a corner covered,
  blur, scratches (this is the common real-world "sticker over the real QR" scam).

The model sorts every QR image into one of **3 classes**:
```
Class 0: clean        (a normal, untouched QR)
Class 1: adversarial  (invisible pixel poisoning)
Class 2: tampered     (visible sticker / cover / blur / damage)
```

## 2.2 What tool/model we used — EfficientNet-B0 (a CNN)

A **CNN (Convolutional Neural Network)** is the standard AI model for images. It works a bit
like your eye: early layers detect simple things (edges, corners), later layers combine them
into complex patterns (a finder-pattern square, a sticker edge). It looks at the picture and
decides what it is.

**EfficientNet-B0** is a specific, efficient CNN design — small and fast, good for phones and
CPUs, but still accurate. We reused it from your FYP1.

**Transfer learning:** EfficientNet-B0 was already **pre-trained on ImageNet** (millions of
ordinary photos), so it already knows how to "see" shapes and textures. We then fine-tuned it
on QR images. Same idea as DomURLs_BERT — start from a knowledgeable model, specialise it.

**Tools used:** Python, PyTorch, torchvision (gives us EfficientNet-B0), the `qrcode` library
(to generate QR images), `torchattacks` (to create the adversarial noise), OpenCV + PIL +
NumPy (to create the synthetic tampering — stickers, blur, etc.), Google Colab + T4 GPU, ONNX
Runtime (fast deployment).

## 2.3 What data we used — and how we MADE it 用什么数据(我们自己造)

We did not download a QR dataset — we **generated everything ourselves**, which is fully
controllable and reproducible:

1. **Clean QRs (class 0):** we generated ~2,500 real QR codes with the `qrcode` library, from
   varied content, various sizes/error-correction levels. (The *content* doesn't matter —
   structural analysis only cares about the *picture*.)
2. **Adversarial QRs (class 1):** we took the clean QRs and added invisible poison using two
   standard attack methods, **FGSM** and **PGD** (this is exactly your FYP1 method).
3. **Tampered QRs (class 2):** we took the clean QRs and applied **synthetic tampering** —
   randomly one or two of: paste an opaque sticker rectangle, cover a patch, corrupt a corner
   finder pattern, add heavy blur, draw scratch lines. This mimics real sticker-overlay fraud
   and is fully controllable.

**Important — "split first, then attack":** we split the clean QRs into train/val/test FIRST,
and only then made the adversarial and tampered versions *within each split*. This guarantees
the test QRs (and their attacked versions) were never seen in training — no cheating.

## 2.4 What we actually did — the training process 训练流程

Done in the notebook `structural_efficientnet_3class.ipynb`, phase by phase:
1. **Generate clean QRs** (class 0).
2. **Split first, then derive** adversarial (class 1) + tampered (class 2) per split → 3
   balanced classes (train 5,250 / val 1,125 / test 1,125 images).
3. **Fine-tune EfficientNet-B0** — replace its final layer with a 3-way output, then train 15
   epochs, keeping the best version by validation accuracy.
4. **Evaluate** — per-class precision/recall/F1 + a confusion matrix.
5. **Calibrate** — temperature scaling (T ≈ 1.39) so probabilities are honest.
6. **Sanity check** — confirm clean → low risk, adversarial/tampered → high risk.
7. **Export** — ONNX for fast CPU deployment (FP32, 16 ms/image — see note below).

**Result: 99.91% test accuracy**, all three classes near-perfect. One CNN successfully covers
both threat types — which is exactly why we consolidated FYP1's two detectors into one.

*Note on speed:* we tried INT8 quantization (like Method 1) but it does not suit CNNs, so we
deploy the FP32 ONNX model — still only 16 ms per image, far under our 500 ms budget. This is
the correct format choice for a CNN, not a problem.

## 2.5 What Structural OUTPUTS 输出是什么

For one QR image, the model gives three probabilities that add up to 1.0, and we derive the
final signal:

```python
probs = {'clean': 0.9999, 'adversarial': 0.0000, 'tampered': 0.0001}
p_structural   = 1 − probs['clean']          # = 0.0001 here → "how manipulated is it?"
predicted_type = 'clean'                      # the most likely class, for the UI
```

Real examples from our final model:
```
a clean QR       → p_structural = 0.000,  type = clean
an adversarial QR→ p_structural = 0.999,  type = adversarial
a tampered QR    → p_structural = 0.997,  type = tampered
```

**The number `p_structural` (plus `predicted_type` for display) is what goes to Fusion.**

---

# Part 3 — HOW THE OUTPUTS COMBINE INTO FUSION 怎么进 fusion

## 3.1 The two outputs, side by side 两个输出

| Model | Looks at | Main output for fusion | Extra output for the UI |
|---|---|---|---|
| **Structural** (CNN) | the QR **image** | `p_structural` (0–1) | `predicted_type` (clean/adversarial/tampered) |
| **Method 1** (BERT) | the decoded **URL** | `p_url` (0–1) | — |

Both are **calibrated probabilities between 0 and 1**, on the same honest scale — that is what
makes them safe to combine.

## 3.2 The Fusion Engine — combining them into one score 融合成一个分数

Fusion does NOT just average them. It uses a small trained model (a **logistic regression**,
the "meta-classifier") that has learned how much to trust each signal. Here is the flow:

**Step 1 — collect all signals into a fixed list (a "feature vector"):**
```
x = [ p_structural , p_url , llm_score , rule_flag_1 , rule_flag_2 , ... ]
        │             │        │            └──── from the Rule Engine (0/1 each)
        │             │        └──── from Method 2 (the LLM), if it was called
        │             └──── from Method 1 (this document, Part 1)
        └──── from Structural (this document, Part 2)
```
Every signal always sits in the **same position** in this list — that is a fixed contract, so
the trained fusion model always knows which number means what.

**Step 2 — the logistic regression computes one probability:**
```
p_fraud = logistic( w1·p_structural + w2·p_url + w3·llm_score + ... + b )
```
The `w`s (weights) were **learned** from labelled examples (our QRGuard-Mix test set). A bigger
weight = "trust this signal more". This is *why* it is better than averaging: fusion learns,
for instance, to down-weight `p_url` when Method 2 (the LLM) disagrees — which is exactly how
Method 1's residual brand-keyword false positives get corrected at the system level.

**Step 3 — turn it into a 0–100 score and a verdict:**
```
risk_score = round(100 × p_fraud)
   < 30   → Safe 🟢
   30–69  → Warning 🟡
   ≥ 70   → Blocked 🔴
```

## 3.3 A worked example 一个完整例子

Someone scans a QR that is a **clean image** but points to a **phishing link**:

```
Structural model sees the image      → p_structural = 0.03   (image looks fine)
Method 1 sees the URL text           → p_url        = 0.93   (link looks like phishing!)
Rule Engine                          → rule_flags   = [non_https=1, suspicious_tld=1]
Method 2 (LLM) double-checks         → llm_score    = 0.95

Fusion feature vector:
x = [0.03, 0.93, 0.95, 1, 1, ...]

Logistic regression → p_fraud ≈ 0.9  →  risk_score = 90  →  BLOCKED 🔴
Reasons shown to user: "Phishing pattern in link", "No HTTPS", "Suspicious domain"
```

Notice: the image branch said "fine" (0.03) but the URL branch caught it (0.93). **A system
using only the image would have let this fraud through** — this is exactly why we have both
models feeding fusion. The reverse also works: a tampered sticker-QR pointing to a normal-
looking URL is caught by the Structural branch even when Method 1 says "fine".

## 3.4 Where this sits in the code 代码位置

- Structural model → `backend/structural/structural_service.py` → returns `p_structural`,
  `predicted_type`. *(to be built next)*
- Method 1 model → `backend/semantic/method1.py` → returns `p_url`. *(to be built next)*
- Fusion → `backend/fusion/` → takes both (+ rules + Method 2) → risk score + verdict.
  *(built after the two services)*

The trained model files themselves live in `training/artifacts/` (downloaded from Colab):
`structural/` (the CNN) and `method1/` (the BERT).

---

## Summary in one paragraph 一段话总结

We built **two AI models**. **Method 1** is a URL-specialised BERT (DomURLs_BERT) that reads
the decoded link as text and outputs `p_url` (phishing probability); we trained it on ~1M real
URLs, fixing two shortcut-learning problems along the way. **Structural** is an image CNN
(EfficientNet-B0) that looks at the QR picture and outputs `p_structural` (manipulation
probability) across 3 classes (clean/adversarial/tampered); we trained it to 99.91% on QR
images we generated ourselves. Both output an **honest, calibrated 0–1 probability**. The
**Fusion Engine** places both (plus rule flags and the Method 2 LLM opinion) into a fixed
feature vector, runs a small trained logistic regression to get one `p_fraud`, and converts it
to a **0–100 risk score → Safe / Warning / Blocked**. Two angles, one decision.
