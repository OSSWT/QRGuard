# FYP2 Development Plan — QRGuard (Revised v2)
## Real-Time Fraud Detection in QR Code Scanning Using AI Approach
**Student:** Ooi Sze Shou · **Supervisor:** Ms Tseu Kwan Lee · **UTAR Kampar, Bachelor of Computer Science (Honours)**

> **v2 revision notes (agreed in discussion, July 2026):**
> 1. Problem Statement / Project Scope / Objectives are **retained verbatim from the Proposal Writing (IIPSPW)** — no additions, no rewording of objectives.
> 2. Top-level framing follows the proposal's own terminology: **Structural Analysis + Semantic Analysis → Fusion**.
> 3. Latency requirement revised to a **two-tier target**: model inference ≤ 500 ms; median end-to-end scan-to-verdict ≤ 3 s.
> 4. Semantic Analysis uses **two complementary methods** (not main-vs-baseline): a fine-tuned URL-pretrained Transformer + an LLM reasoning analyzer. No traditional ML as a method.
> 5. FYP1 is included as a **condensed supporting section (a few pages)** in the FYP2 report.

---

## 0. Continuity Story: Proposal → FYP1 → FYP2

The proposal promised a dual-branch system: **Structural Analysis + Semantic Analysis fused into a unified risk score**. FYP1 delivered and validated the **Structural Analysis** half (= proposal Objective 1). FYP2 delivers the remaining half and the integration (= proposal Objectives 2, 3, 4). Nothing is redefined; the project simply executes the proposal in two phases.

| Proposal Objective (original wording, unchanged) | Status |
|---|---|
| **Obj 1** — Structural analysis module: AI/computer-vision evaluation of visual integrity (finder patterns, alignment modules, quiet zones, distortions, overlays, blurring) | ✅ **Completed in FYP1**: EfficientNet-B0 adversarial-noise detector (96.42% acc, ROC-AUC 0.980) + 14-feature Random Forest structural tampering classifier (98.7% acc). The CNN detector covers the proposal's "distortions / capture artefacts" at pixel level; the structural classifier covers finder patterns, quiet zones, overlays. |
| **Obj 2** — Semantic analysis module: interpretation of decoded payloads (URLs, redirection chains, embedded scripts), classification by domain reliability, redirection behaviour, phishing indicators | 🔨 **FYP2 core work** |
| **Obj 3** — Integration of both analyses into a unified dual-branch framework producing a real-time risk score, optimized for mobile devices | 🔨 **FYP2 core work** (Fusion Engine + QRGuard application) |
| **Obj 4** — Validation and evaluation: accuracy, precision, recall, F1, false positive rate, latency, resource efficiency | 🔨 **FYP2** (structural part already evaluated in FYP1; FYP2 adds semantic, fusion, and system-level evaluation) |

> **中文解释：** Proposal 本来就承诺了 Structural Analysis + Semantic Analysis + Fusion。FYP1 完成并验证了 Structural Analysis 这一半（= Objective 1）：EfficientNet-B0 负责检测 adversarial noise，14 个 structural features + Random Forest 负责检测 physical tampering。FYP2 做剩下的 Objectives 2–4：Semantic Analysis module、Fusion、application development 和完整 evaluation。整个故事线是"按 proposal 分两阶段执行"，不是改题，所以 Problem Statement / Scope / Objectives 全部照抄 proposal 原文即可，FYP2 report 里只需要一段衔接文字说明这个分工。

---

## 1. Title and System Name

Registered title (unchanged): **"Real-Time Fraud Detection in QR Code Scanning Using AI Approach"**
System / application name: **QRGuard**

The report may use the descriptive subtitle: *"a dual-branch framework combining Structural Analysis and Semantic Analysis with real-time risk fusion"* — this is the proposal's own vocabulary.

> **中文解释：** 注册 title 不动。App 叫 QRGuard。副标题直接用 proposal 的原词（Structural Analysis、Semantic Analysis、risk fusion），保持三份文件术语一致。

---

## 2. Problem Statement — RETAIN FROM PROPOSAL

**Action: copy the Problem Statement section from IIPSPW (proposal) into the FYP2 report unchanged.** The proposal already frames the problem as: existing systems separate QR verification into structural validation *or* semantic inspection, rarely combining both in real time, leaving users exposed to quishing before interaction.

Only one supplementary paragraph is added at the end (new text, not a modification):

> *"FYP1 addressed the structural dimension of this problem by developing and validating an image-level dual-detector framework. FYP2 completes the proposed system by developing the semantic analysis module, the fusion mechanism, and the real-time application, as set out in Objectives 2–4."*

> **中文解释：** Problem Statement 原文照抄 proposal，一个字不改。只在末尾**追加**一段衔接文字（不是修改），说明 FYP1 解决了 structural 维度、FYP2 完成 semantic + fusion + application。这样和 FYP1 report、proposal 三方都不冲突。

---

## 3. Project Scope — RETAIN FROM PROPOSAL, ONE REVISION

**Action: copy the Project Scope from the proposal.** It already covers: dual-branch pipeline (structural branch: finder patterns, alignment modules, quiet zones, distortions, overlays, capture artefacts; semantic branch: URLs, redirects, domain features, embedded scripts), fused unified risk score, real-time decision before user interaction, lightweight models for mobile, interpretable outputs, dataset curation with augmentation, evaluation protocols, and the exclusions (no email/voice phishing, no cryptographic QR issuance, no new QR standards).

**The single agreed revision — the latency sentence.**

- Original: *"end-to-end responses in under 500 milliseconds on mid-range mobile hardware"*
- Revised: *"The system targets **AI model inference within 500 ms** on CPU-class hardware, and a **median end-to-end scan-to-verdict response within 3 seconds** on mid-range mobile hardware. Latency introduced by third-party redirection tracing of shortened URLs is bounded by a 3-second timeout and reported separately."*

Rationale (for the report's discussion): inference latency is what the system controls (quantized EfficientNet-B0 ≈ 20–50 ms + Random Forest ≈ 5 ms + quantized URL Transformer ≈ 50–150 ms ⇒ ≈ 200–300 ms total, within budget). Network round-trip and third-party redirect servers are outside system control and are therefore specified and measured separately — standard practice in systems evaluation.

Two scope commitments and how they are honoured realistically:
- **"embedded scripts"** → implemented as deterministic rule checks for executable payload indicators (`javascript:` URIs, `data:` URIs, executable content flags), not full script analysis.
- **"safe / warning / block" feedback with contextual reasoning** → exactly the QRGuard three-tier verdict UI with reason cards.

> **中文解释：** Scope 照抄 proposal，只改一句 latency：改成两级指标 —— **model inference ≤ 500ms**（自己能控制的部分，估算 quantized EfficientNet-B0 约 20–50ms + Random Forest 约 5ms + quantized URL Transformer 约 50–150ms，总共 200–300ms，有余量）+ **end-to-end median ≤ 3s**（包含网络往返和 shortened URL 的 redirect tracing，这些不受系统控制，单独报告）。另外 proposal 里的 "embedded scripts" 用 rule checks 实现（检测 `javascript:`、`data:` URI），"safe/warning/block" 就是 QRGuard 的三级判定界面 —— 两个承诺都能兑现，不用改字。

---

## 4. Project Objectives — RETAIN FROM PROPOSAL, ZERO CHANGES

**Action: copy the four objectives from proposal Section 3.2 verbatim. Do not add objectives.** The FYP2 report reports progress against them: Objective 1 achieved in FYP1 (with evidence summarized in the condensed FYP1 section); Objectives 2–4 achieved in FYP2.

> **中文解释：** 四个 objectives 原文照抄，**不追加任何新 objective**。FYP2 report 按 objective 汇报：Objective 1 → FYP1 完成（证据在浓缩的 FYP1 支撑章节），Objectives 2–4 → FYP2 完成。这样避免出现一堆需要逐条"解决"的新 objectives。

---

## 5. System Architecture (Structural + Semantic → Fusion)

```
┌────────────────────────── QRGuard Mobile App (Flutter) ─────────────────────────────┐
│  Camera scan → QR localization & decode (on-device, ML Kit / ZXing)                 │
│  ├─ QR region crop (image) ───────────┐                                             │
│  └─ Decoded payload (string) ─────────┤        [Analyzing screen]                   │
└───────────────────────────────────────┼─────────────────────────────────────────────┘
                                        ▼  HTTPS (image crop + payload)
┌────────────────────────── FastAPI Backend (Python) ─────────────────────────────────┐
│                                                                                      │
│  STRUCTURAL ANALYSIS (from FYP1 — Objective 1, completed)                            │
│  ├─ S1 Adversarial-noise detector: EfficientNet-B0 (ONNX INT8) → p_adv               │
│  └─ S2 Structural tampering classifier: 14 features + Random Forest → p_tamper       │
│                                                                                      │
│  SEMANTIC ANALYSIS (FYP2 — Objective 2, two COMPLEMENTARY analyzers)                 │
│  ├─ M1 Payload router & URL normalizer (payload type, canonicalization)             │
│  ├─ M2 String-level analyzer: fine-tuned DomURLs_BERT → p_url   (every URL, <150ms) │
│  ├─ M3 Shortener / redirect expansion (server-side, HEAD only, SSRF-protected)      │
│  ├─ M4 Behavioral-contextual analyzer: LLM reasoning (zero/few-shot)                │
│  │     — triggered ONLY for: uncertain band ∪ shortened/redirected ∪ unseen domain  │
│  │     → llm_verdict + natural-language explanation                                  │
│  └─ M5 Rule engine: javascript:/data: URI, IP-literal host, punycode, non-HTTPS     │
│                                                                                      │
│  FUSION (FYP2 — Objective 3)                                                         │
│  calibrated stacking (logistic meta-classifier) + override rules                     │
│  → risk_score ∈ [0,100] → Safe (<30) / Warning (30–69) / Blocked (≥70) + reasons     │
│                                                                                      │
│  EXPLAINABILITY: Grad-CAM (S1) · feature deviations (S2) · LLM explanation (M4)      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Design decisions: QR decode runs on-device (fast, offline-capable); model inference runs on the backend (app stays light, models updatable without app releases). Structural Analysis models are reused from FYP1 with two engineering upgrades only: probability calibration (temperature scaling) and ONNX INT8 quantization — **no retraining**.

> **中文解释：** 顶层就是 proposal 说的三块：**Structural Analysis**（FYP1 原模型，只做两件工程升级：probability calibration 和 ONNX INT8 quantization，**不重新训练**）+ **Semantic Analysis**（FYP2 新做，两个互补 analyzer，见第 7 节）+ **Fusion**（校准概率 stacking → 0–100 risk score → 三级判定）。手机端只负责扫码和解码，模型推理放 backend。

---

## 6. Main Application Modules

| # | Module | Function | Origin |
|---|--------|----------|--------|
| A1 | Scanner Module | Live camera, QR localization, decode, region crop | New |
| A2 | Adversarial-Noise Detector (S1) | EfficientNet-B0 → p_adv | **FYP1 reuse** (calibrated + quantized) |
| A3 | Structural Tampering Classifier (S2) | 14 features + Random Forest → p_tamper | **FYP1 reuse** |
| A4 | Payload Router & URL Normalizer | Payload-type detection, URL canonicalization | New |
| A5 | String-Level Semantic Analyzer | Fine-tuned DomURLs_BERT → p_url | New — **the only model trained in FYP2** |
| A6 | Redirect Expansion Service | httpx HEAD, 3 s timeout, ≤5 hops, private-IP blocklist | New |
| A7 | Behavioral-Contextual Analyzer | LLM reasoning on expanded URL + redirect chain (zero/few-shot, temperature 0) | New — no training required |
| A8 | Rule Engine | `javascript:`/`data:` URI, IP-literal, punycode/homoglyph, suspicious TLD, non-HTTPS | New |
| A9 | Fusion Risk Engine | Calibration + logistic stacking + override rules → score/verdict | New (replaces FYP1 OR rule) |
| A10 | Explainability Module | Grad-CAM, feature deviations, LLM explanation text → reason cards | New (A7 output reused here) |
| A11 | Result UI + Scan History | Safe/Warning/Blocked screens, reason cards, local history | New |

> **中文解释：** 11 个 module。A2、A3 直接复用 FYP1。**FYP2 只需要训练一个模型（A5 的 DomURLs_BERT fine-tuning）**；A7 的 LLM analyzer 是 zero/few-shot，不用训练，只要设计 prompt 和评估。A7 的输出同时喂给 A10 当解释文字，Explainability 基本免费。

---

## 7. Semantic Analysis: Two Complementary Methods (agreed design)

**Design principle — same philosophy as FYP1.** FYP1's Structural Analysis used two detectors covering orthogonal threat surfaces (CNN for adversarial noise; structural features for physical tampering). FYP2's Semantic Analysis mirrors this: two analyzers covering orthogonal semantic surfaces — the **string level** and the **behavioral/contextual level**. They are complementary, **not** a main-method-vs-baseline comparison.

| | **Method 1 — String-level: DomURLs_BERT (fine-tuned)** | **Method 2 — Behavioral-contextual: LLM reasoning (zero/few-shot)** |
|---|---|---|
| Covers | Lexical/morphological phishing patterns: typosquatting, suspicious domain morphology, mass-generated phishing URLs, character-level anomalies. Runs on **every** URL, <150 ms, offline. | Deception requiring world knowledge and reasoning: expanded shortened links, redirect-chain behaviour, brand impersonation ("claims to be Maybank but registered under .xyz"), novel unseen patterns. Also generates the natural-language explanation. |
| Weak at | Cannot see behaviour (redirects); blind to innocuous-looking new domains and shortened URLs; no world knowledge; no explanations. | Latency (1–3 s), API cost, output variance. |
| Weakness covered by | → Method 2 analyzes the expanded chain and context. | → Method 1 filters clear-cut cases; LLM is invoked **only** for the uncertain band ∪ shortened/redirected URLs ∪ unseen domains (estimated <20% of scans). |

**Pipeline:** every URL → Method 1 → high-confidence verdicts exit immediately; otherwise expand redirects (A6) → Method 2 reasons over the full chain → verdict + explanation.

**Supporting literature (2024–2026, non-traditional-ML as required):**
- Method 1: DomURLs_BERT — pre-trained BERT for malicious domain/URL detection ([arXiv:2409.09143](https://arxiv.org/html/2409.09143v1), 2024); URLBERT / continuous multi-task pre-training for malicious URL detection (*Computer Networks*, 2025; [arXiv:2402.11495](https://arxiv.org/abs/2402.11495)).
- Method 2: PhishLLM — LLM reasoning + classifier hybrid for real-time phishing defence (Springer, 2026); benchmarking LLMs for zero/few-shot phishing URL detection ([arXiv:2602.02641](https://arxiv.org/pdf/2602.02641), 2026); least-to-most reasoning for phishing URL detection ([arXiv:2601.20270](https://arxiv.org/pdf/2601.20270), 2026); MemoPhishAgent ([arXiv:2602.21394](https://arxiv.org/pdf/2602.21394), 2026).
- Literature-review-only (cited, not implemented): URL2Graph++ graph learning ([arXiv:2509.10287](https://arxiv.org/pdf/2509.10287), 2025); traditional-ML quishing detection (Trad & Chehab 2025) as related work; lightweight BERT variants (2025) as deployment context.

**Method 2 reproducibility protocol (for the report):** fixed model version, temperature 0, structured JSON-output prompt, all prompts/responses logged; offline fallback = Method 1 + rule engine with a "partial analysis" notice.

> **中文解释：两个互补 method 的分工。** Method 1（DomURLs_BERT fine-tuning）守 **string level**：typosquatting、可疑 domain 形态、批量生成的 phishing URL —— 每条 URL 必过、毫秒级、离线。Method 2（LLM reasoning，zero/few-shot）守 **behavioral/contextual level**：shortened URL 展开后的 redirect chain、需要世界知识的 brand impersonation、没见过的新攻击 —— 只在 Method 1 不确定、或遇到短链/新 domain 时触发（预计 <20% 的扫描），顺便生成给用户看的解释文字。两者互相补弱点：Method 1 看不懂行为 → Method 2 补；Method 2 慢且有成本 → Method 1 把明确案例先过滤掉。这和 FYP1 的 dual-detector 设计哲学同构（CNN 检测 adversarial noise，structural features 检测 physical tampering，各守一个 attack surface），report 里非常好写。**FYP2 只训练 Method 1 一个模型**，Method 2 不用训练。

---

## 8. Dataset Plan

| Dataset | Use | Size | Status |
|---|---|---|---|
| Figshare QR Code Dataset V2 | Structural Analysis — adversarial (FYP1) | 2,782 clean → FGSM/PGD | Done in FYP1 |
| QR-DN1.0 Extended | Structural Analysis — tampering (FYP1) | 4,575 labelled | Done in FYP1 |
| **PhiUSIIL Phishing URL Dataset** ([UCI #967](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset), 2024) | Method 1 fine-tuning | 235,795 URLs (134,850 legit / 100,945 phishing) | Download |
| Kaggle "Malicious URLs" (malicious_phish) | Cross-dataset generalisation test for Method 1 | ~651k URLs | Download |
| **LLM evaluation subset** | Method 2 evaluation | ~300–500 URLs sampled across families (shorteners, punycode, brand impersonation, benign) | Build in FYP2 |
| **QRGuard-Mix test set** (self-built) | Fusion + end-to-end evaluation | ~500–1,000 QR images: {clean, tampered, adversarial} × {benign, phishing} + printed-and-photographed subset | Build in FYP2 |

Leakage controls: deduplicate URLs by registered domain across splits; QR images for QRGuard-Mix generated from URLs never seen in Method 1 training.

> **中文解释：** Structural 的两个 dataset FYP1 已用完不动。FYP2 下载 **PhiUSIIL**（UCI 官方，23.5 万条 URL）来 fine-tune Method 1，用 Kaggle malicious_phish 做 cross-dataset 泛化测试。另外自建两个小集：**LLM evaluation subset**（300–500 条，按攻击家族分层抽样，评估 Method 2）和 **QRGuard-Mix**（500–1000 张 QR code，六种组合 + 打印拍摄子集，是证明 fusion 优于单支的关键证据）。防泄漏：按 registered domain 去重。

---

## 9. Training and Testing Plan

Only **one model is trained in FYP2** (Method 1); everything else is engineering, prompting, and evaluation.

- **T1 (Wk 2–4) — Method 1 fine-tuning:** DomURLs_BERT on PhiUSIIL (URL string input, max length 128, 2–3 epochs, Colab T4); probability calibration; cross-dataset test on malicious_phish; export to ONNX INT8.
- **T2 (Wk 4–6) — Method 2 prompt engineering & evaluation:** design structured JSON prompt (verdict + risk factors + explanation); evaluate on the LLM evaluation subset; measure agreement with ground truth per attack family; fix version/temperature; log everything.
- **T3 (Wk 4–6) — Structural Analysis operationalization:** temperature-scaling calibration; ONNX INT8 export; re-run FYP1 test suite + extended degradation set (blur, occlusion, perspective, brightness); accept ≤2 pp accuracy drop else fall back to FP16.
- **T4 (Wk 6–8) — Fusion training:** build QRGuard-Mix; collect [p_adv, p_tamper, p_url, llm_verdict, rule flags]; train logistic meta-classifier; tune thresholds (Blocked precision ≥ 0.95; Safe-tier false-negative rate ≤ 2%).
- **T5 (Wk 9–12) — System testing:** two-tier latency profiling (inference ≤ 500 ms; end-to-end median ≤ 3 s); ablation (Structural-only vs Semantic-only vs fused; Method 1-only vs Method 1+2); robustness spot checks; UI walkthrough.

> **中文解释：** FYP2 只训练一个模型（T1：DomURLs_BERT 在 PhiUSIIL 上 fine-tune，Colab T4 跑 2–3 个 epoch 就够）。T2 是 Method 2 的 prompt 设计 + 评估（不是训练）。T3 是 FYP1 模型的工程化（calibration + quantization，量化掉精度超过 2 个百分点就回退 FP16）。T4 训练 fusion 的 logistic meta-classifier 并调三级阈值。T5 做系统级测试：两级 latency、ablation（Structural-only vs Semantic-only vs fused，以及 Method 1 单独 vs Method 1+2），证明"融合更强、互补有效"。

---

## 10. Backend Architecture

- **FastAPI** on Uvicorn; endpoints: `POST /scan` (image crop + payload → verdict JSON), `POST /analyze-url` (fast path), `GET /health`.
- **Inference:** ONNX Runtime CPU (EfficientNet-B0 INT8, DomURLs_BERT INT8); joblib (Random Forest); models loaded once at startup.
- **Redirect expansion:** httpx, HEAD-only, 3 s timeout, ≤5 hops, private-IP/localhost blocklist (SSRF protection), full chain logged.
- **LLM analyzer:** API call to a small fast model (e.g., Haiku/Flash class), temperature 0, JSON schema output, invoked only per the trigger rules; graceful degradation to "partial analysis" when unavailable.
- **Demo deployment:** Docker on free-tier host or local machine + LAN; optional SQLite scan log.

> **中文解释：** FastAPI 后端，三个 endpoint。推理用 ONNX Runtime（CPU 跑量化模型足够）。Redirect expansion 只发 HEAD 请求、3 秒超时、最多 5 跳、屏蔽内网 IP（防 SSRF）。LLM 用便宜的小模型 API，temperature 0、JSON 输出、只按触发规则调用，不可用时优雅降级为 "partial analysis"。演示用 Docker 或本机局域网。

---

## 11. Frontend / Mobile App Screen Flow (QRGuard, 5 screens)

1. **Home / Scan** — full-screen camera, auto-detect, history/settings.
2. **Analyzing** — staged progress ("Checking image integrity → Analyzing link → Computing risk"); covers the 1–3 s window including LLM calls.
3. **Safe (green, score < 30)** — risk dial, destination domain, "Open Link" primary button, expandable details.
4. **Warning (amber, 30–69)** — reason cards (LLM explanation text appears here); "Don't Open" primary / "Open Anyway (not recommended)" secondary.
5. **Blocked (red, ≥ 70)** — prominent reasons; "Back to Scan" primary; opening requires two-step override in details.

Rules: never auto-open URLs; always show the **expanded final URL**; every verdict shows ≥1 human-readable reason; colour + icon + text (accessibility).
**Technology:** Flutter + `mobile_scanner`; fallback React PWA if Flutter slips (week-7 checkpoint).

> **中文解释：** 五屏流程不变（之前已批准）。Analyzing 屏的分阶段进度正好覆盖 LLM 调用的 1–3 秒。Warning/Blocked 页的 reason cards 直接显示 Method 2 (LLM) 生成的解释文字。三条铁律：不自动打开链接、永远显示展开后的最终 URL、每个结果至少一条人话原因。

---

## 12. Fusion Engine Design

**Inputs:** p_adv (S1), p_tamper (S2), p_url (Method 1), llm_verdict (Method 2, may be absent), rule flags, payload-type indicator.
**Stage 1 — Calibration:** temperature scaling (CNN/Transformer), Platt/isotonic (Random Forest) so probabilities are comparable.
**Stage 2 — Meta-classifier:** logistic regression over the calibrated vector → p_fraud; risk score = round(100 × p_fraud). Logistic weights are directly interpretable per branch.
**Stage 3 — Override rules:** confirmed blocklist hit → Blocked; non-URL payload → Semantic Analysis abstains (rule-based handling); low-quality image crop → Structural Analysis abstains ("partial analysis"); missing LLM verdict handled as absent feature, not zero.
**Stage 4 — Decision policy:** Safe < 30 ≤ Warning < 70 ≤ Blocked (thresholds tuned in T4; threshold-sensitivity curve reported).

Why not FYP1's OR rule: OR cannot express "two weak signals jointly indicate fraud", provides no graded score for the Warning tier, and inflates false positives as branches are added.

> **中文解释：** 四阶段：probability calibration → logistic regression stacking（输出 0–100 分，每个 branch 的贡献可解释）→ override rules 兜底（blocklist 直接 Blocked；非 URL payload 时 Semantic 弃权；图像质量差时 Structural 弃权；LLM 缺席按 missing feature 处理）→ 三级判定。不用 FYP1 的 OR rule 的原因：OR 表达不了"两个弱信号叠加 = 危险"、给不出 Warning 档需要的分数、branch 越多 false positive 越高。

---

## 13. Evaluation Metrics

| Level | Metrics |
|---|---|
| Structural Analysis | FYP1 metrics re-verified post-quantization (accuracy/F1/ROC-AUC delta ≤ 2 pp); extended degradation robustness |
| Semantic — Method 1 | Accuracy, precision, recall, F1, ROC-AUC on PhiUSIIL test; cross-dataset F1 on malicious_phish |
| Semantic — Method 2 | Agreement with ground truth on LLM evaluation subset, per attack family; trigger rate (% of scans invoking LLM); explanation quality (rubric-scored sample) |
| Semantic — combined | Coverage analysis: cases Method 1 misses that Method 2 catches (and vice versa) — the complementarity evidence |
| Fusion | 3-class confusion matrix on QRGuard-Mix; Blocked precision ≥ 0.95; Safe-tier FNR ≤ 2%; ablation (Structural-only / Semantic-only / fused); Expected Calibration Error |
| System | **Tier 1: model inference latency ≤ 500 ms** (per-module breakdown); **Tier 2: end-to-end median ≤ 3 s** (Wi-Fi and 4G); redirect-expansion timeout rate |
| Usability | 5–8 participant walkthrough; comprehension of Warning reasons; correct-action rate; SUS (descriptive) |

> **中文解释：** 评估分七层。最重要的两个新表：**complementarity evidence**（Method 1 漏掉但 Method 2 抓到的案例，反之亦然 —— 证明"互补"不是嘴上说说）和 **ablation**（Structural-only vs Semantic-only vs fused）。Latency 按两级指标分开报告：inference ≤ 500ms（逐 module 分解）+ end-to-end median ≤ 3s（Wi-Fi 和 4G 两种网络）。

---

## 14. Expected Contribution

1. A complete dual-branch QR fraud detection system executing the proposal's vision: **Structural Analysis (FYP1) + Semantic Analysis (FYP2) fused into a real-time graded verdict** — prior work treats these in isolation.
2. A **complementary two-analyzer Semantic Analysis design** (string-level Transformer + LLM behavioural reasoning) with measured coverage complementarity — applying 2025–2026 LLM-reasoning research in a deployed pipeline.
3. A calibrated, explainable **fusion engine** replacing binary OR fusion with a graded, threshold-tuned risk policy.
4. **QRGuard**, a working real-time application demonstrating interactive-latency deployment, plus the QRGuard-Mix test set methodology.

> **中文解释：** 四点贡献：① 完整实现 proposal 的 dual-branch 愿景；② Semantic Analysis 的互补双 analyzer 设计（把 2025–2026 的 LLM reasoning 研究落地）；③ 可解释的 fusion engine；④ QRGuard 应用 + QRGuard-Mix 测试集方法论。写报告用 "to the author's knowledge" 的谦逊表述。

---

## 15. FYP2 Development Timeline (13 weeks)

| Week | Milestone |
|---|---|
| 1 | Environment setup; datasets download; FYP1 model inventory; architecture freeze |
| 2–4 | **T1** Method 1 fine-tuning (DomURLs_BERT on PhiUSIIL) + calibration + ONNX export |
| 3–4 | A4 payload router, A6 redirect expansion, A8 rule engine |
| 4–6 | **T2** Method 2 prompt design + LLM evaluation subset + evaluation; **T3** Structural Analysis calibration/quantization |
| 6–7 | FastAPI backend assembly; `/scan` end-to-end with stub fusion |
| 6–8 | **T4** QRGuard-Mix construction; fusion meta-classifier + thresholds |
| 7–9 | Flutter app (scanner, analyzing, 3 verdict screens); API integration; week-7 Flutter checkpoint |
| 9–10 | Explainability wiring (Grad-CAM, feature deviations, LLM reason cards) |
| 10–12 | **T5** full evaluation: ablation, complementarity, latency, usability |
| 8–13 | Report writing in parallel; condensed FYP1 support section; poster; demo video; submission |

Buffer: Method 2 is prompt-based (no training) — if LLM integration slips, Method 1 + rule engine still completes the Semantic branch, and Method 2 becomes a documented enhancement.

> **中文解释：** 13 周。关键路径：Method 1 训练（周 2–4）→ backend（周 6–7）→ fusion（周 6–8）→ app（周 7–9）→ 评估（周 10–12）。保险丝：Method 2 不用训练，如果 LLM 集成延误，Method 1 + rule engine 也能独立跑通 Semantic branch。

---

## 16. Risks, Limitations, Mitigations

| Risk | Mitigation |
|---|---|
| Quantization degrades FYP1 models | Accept ≤ 2 pp drop, else FP16 fallback; report both |
| Public URL datasets age; live performance gap | Cross-dataset testing; honest temporal limitation; rules + Method 2 catch fresh threats |
| LLM API availability / cost / variance | Trigger rules limit calls to <20% of scans; temperature 0 + fixed version + logged prompts; offline fallback = Method 1 + rules ("partial analysis") |
| Redirect expansion blocked or times out | 3 s timeout; "unexpandable shortener" treated as a risk feature itself |
| Flutter learning curve | Week-7 checkpoint; React PWA fallback pre-scoped |
| Small fusion training set | Few meta-features + logistic model (low variance); k-fold CV; confidence intervals |
| Adaptive attacks on the detector itself | Explicitly out of scope; Future Work |
| Non-URL payloads (Wi-Fi, vCard) | Rule-based handling; "partial analysis" label |

> **中文解释：** 八个风险都有对策。最重要的三个：LLM 依赖（触发规则限制调用量 + temperature 0 固定版本保证可复现 + 离线降级）、quantization 掉精度（超 2 个百分点回退 FP16）、Flutter 学习曲线（第 7 周 checkpoint，退路 React PWA）。

---

## 17. FYP2 Report Chapter Structure

- **Ch 1 Introduction** — Problem Statement (proposal verbatim + FYP2 bridging paragraph), Scope (proposal verbatim + revised latency sentence), Objectives (proposal verbatim), **"Relationship to FYP1" subsection**, contributions, organization.
- **Ch 2 Literature Review** — 2.1 QR security & quishing (2025–2026: Kowalewski USENIX'25, Weinz'25, QR"iS'25); 2.2 structural/image-level detection (condensed, points to FYP1); 2.3 semantic URL detection: URL-pretrained Transformers (URLBERT, DomURLs_BERT) and LLM-based detection (PhishLLM, zero/few-shot benchmarks, reasoning methods) — the chapter's core; 2.4 fusion & calibration; 2.5 explainable security UX; 2.6 gap summary.
- **Ch 3 System Design** — architecture, modules, Semantic dual-analyzer design, fusion, UX flow, datasets. **Includes the condensed FYP1 supporting section (a few pages): dual-detector architecture figure + key results table (EfficientNet-B0 96.42%, structural classifier 98.7%) + "Objective 1 achieved" statement.**
- **Ch 4 Implementation** — Method 1 fine-tuning, Method 2 prompting protocol, Structural operationalization, backend, app.
- **Ch 5 Experiments & Evaluation** — per-branch results, complementarity analysis, fusion ablation, two-tier latency, usability; discussion versus the four proposal objectives.
- **Ch 6 Conclusion & Future Work** — objective-by-objective verdict; limitations; future work (GNN methods like URL2Graph++, adaptive-attack robustness, on-device semantic model, full LLM agent).

**Reference strategy (three layers):**
1. **Inherited (~10–15):** QR structure, FGSM/PGD, EfficientNet/MobileNetV2 — selected from FYP1's list.
2. **FYP2 core, 2024–2026 (~15–20):** DomURLs_BERT, URLBERT, PhishLLM, LLM benchmarks/reasoning, URL2Graph++, quishing studies, PhiUSIIL, calibration/fusion.
3. **Application development (~5–8):** quantization/ONNX, explainable security UX, SHAP/Grad-CAM.

Result: 30–40 references, >50% from 2024–2026.

> **中文解释：** 六章结构。Ch 1 里 Problem Statement / Scope / Objectives 全部 proposal 原文 + 一段衔接文字 + "Relationship to FYP1" 小节。Ch 3 里放**FYP1 浓缩支撑材料（几页）**：架构图 + 关键结果表 + "Objective 1 achieved" 声明。References 三层共 30–40 篇，一半以上是 2024–2026 —— 这就是你说的 FYP2 有"自己的 references"来支撑 research 和 application development。

---

## Key New References (verified July 2026)

1. DomURLs_BERT: Pre-trained BERT-based Model for Malicious Domains and URLs Detection and Classification, [arXiv:2409.09143](https://arxiv.org/html/2409.09143v1), 2024.
2. Continuous Multi-Task Pre-training for Malicious URL Detection and Webpage Classification (URLBERT line), *Computer Networks*, 2025; [arXiv:2402.11495](https://arxiv.org/abs/2402.11495).
3. Leveraging Large Language Models for Enhanced URL Phishing Detection (PhishLLM), [Springer, 2026](https://link.springer.com/chapter/10.1007/978-3-032-12983-3_46).
4. Benchmarking Large Language Models for Zero-shot and Few-shot Phishing URL Detection, [arXiv:2602.02641](https://arxiv.org/pdf/2602.02641), 2026.
5. Eliciting Least-to-Most Reasoning for Phishing URL Detection, [arXiv:2601.20270](https://arxiv.org/pdf/2601.20270), 2026.
6. MemoPhishAgent: Memory-Augmented Multi-Modal LLM Agent for Phishing URL Detection, [arXiv:2602.21394](https://arxiv.org/pdf/2602.21394), 2026.
7. URL2Graph++: Unified Semantic-Structural-Character Learning for Malicious URL Detection, [arXiv:2509.10287](https://arxiv.org/pdf/2509.10287), 2025. *(literature review only)*
8. F. Trad & A. Chehab, Detecting Quishing Attacks with Machine Learning Techniques Through QR Code Analysis, [arXiv:2505.03451](https://arxiv.org/abs/2505.03451), 2025. *(related work)*
9. PhiUSIIL Phishing URL Dataset, [UCI ML Repository #967](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset), 2024.
10. Lightweight BERT Variants for Real-Time Phishing URL Detection on Edge Devices, 2025. *(deployment context)*
11. M. Kowalewski et al., Scanned and Scammed, USENIX Security 2025; M. Weinz et al., Quishing vs LLM-generated Phishing, AsiaCCS 2025; QR"iS, [arXiv:2510.17175](https://arxiv.org/pdf/2510.17175), 2025. *(motivation)*
