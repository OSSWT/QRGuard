# Training Prompt — Semantic Analysis Method 1 (DomURLs_BERT Fine-Tuning)

**用法 How to use:** 把下面代码块里的整段 prompt 复制，贴给任何 AI coding assistant 或 Colab 内置 AI，它就会生成完整的、可以直接在 Google Colab 跑的 training notebook。所有 specification 已按 FYP2 Development Plan v2 锁定，不需要再补充信息。

---

```text
You are an expert ML engineer. Generate a complete, runnable Google Colab notebook
(Python, PyTorch + HuggingFace) that fine-tunes a URL-pretrained Transformer for
binary phishing URL classification. This is "Method 1 — String-Level Semantic
Analyzer" of a QR-code fraud detection system (QRGuard, a university FYP2 project).
Follow every specification below exactly. Where a spec is impossible, implement the
stated fallback instead of inventing your own.

========================================
1. ENVIRONMENT AND GENERAL REQUIREMENTS
========================================
- Target runtime: Google Colab with a single NVIDIA T4 GPU (16 GB), free tier.
- Libraries: torch, transformers, datasets, scikit-learn, pandas, numpy,
  tldextract, matplotlib, onnx, onnxruntime, optimum[onnxruntime]. Install with pip
  in the first cell (quiet mode).
- Google Drive is mounted and used as persistent storage. Base folder:
  /content/drive/MyDrive/FYP2/method1/
- The notebook MUST be organised in phases (Phase 0 to Phase 7). Each phase begins
  by checking whether its output artifacts already exist on Drive; if they do, it
  prints "Phase N already completed -- skipping" and loads the artifacts instead of
  recomputing. This checkpoint-resumable style is mandatory (Colab sessions die).
- Reproducibility: set seed 42 everywhere (python, numpy, torch, transformers
  set_seed). No test-set information may influence any training or model-selection
  decision.
- Every phase ends with a short printed summary of what was produced.

========================================
2. MODEL
========================================
- Primary model: "amahdaouy/DomURLs_BERT" from the HuggingFace Hub, loaded with
  AutoTokenizer and AutoModelForSequenceClassification (num_labels=2).
- At load time, verify the checkpoint exists and loads correctly. If it fails
  (renamed/removed), fall back to "bert-base-uncased" and print a prominent
  warning cell explaining the fallback — do not silently substitute.
- Max sequence length: 128 tokens, truncation on, padding handled by a
  DataCollatorWithPadding (dynamic padding).

========================================
3. DATASET AND PREPROCESSING (Phase 1-2)
========================================
- Primary dataset: PhiUSIIL Phishing URL Dataset (UCI ML Repository id 967).
  Load it with the ucimlrepo package (pip install ucimlrepo; fetch_ucirepo(id=967)).
  If ucimlrepo fails, fall back to reading a user-uploaded CSV from
  /content/drive/MyDrive/FYP2/data/PhiUSIIL_Phishing_URL_Dataset.csv and print
  download instructions.
- Use ONLY two columns: the raw URL string and the binary label. Explicitly DROP
  all 50+ handcrafted feature columns — this model must learn from the URL string
  alone (that is the point of Method 1).
- Label convention: 1 = phishing/malicious, 0 = legitimate. Verify and remap the
  dataset's own convention if needed; print the class balance.
- Cleaning: strip whitespace; drop rows with empty/NaN URLs; drop exact duplicate
  URLs (keep first); print how many were removed.
- LEAKAGE CONTROL (critical, must be implemented exactly): extract the registered
  domain of every URL with tldextract (domain + suffix). Split at the
  REGISTERED-DOMAIN level, not the URL level: group URLs by registered domain,
  then assign entire domain groups to train/val/test with a 70/15/15 split,
  stratified by the domain's majority label. No registered domain may appear in
  more than one split. Print the resulting URL counts and class balance per split,
  and an assertion that the three domain sets are disjoint.

========================================
4. TRAINING (Phase 3)
========================================
- HuggingFace Trainer API with:
  - epochs: 3, with EarlyStoppingCallback (patience 1) monitoring validation F1
  - learning rate: 2e-5, linear schedule, warmup_ratio 0.1
  - per_device_train_batch_size: 32 (halve to 16 with gradient_accumulation_steps=2
    if OOM), eval batch size 64
  - weight_decay 0.01, fp16=True, seed 42
  - evaluation and checkpoint save every epoch; load_best_model_at_end=True with
    metric_for_best_model="f1"
- compute_metrics returns accuracy, precision, recall, F1 (binary, positive class
  = phishing), and ROC-AUC from logits.
- Save the best model + tokenizer to Drive: .../method1/best_model/

========================================
5. EVALUATION (Phase 4)
========================================
- Evaluate the best model on the held-out test split. Report accuracy, precision,
  recall, F1, ROC-AUC. Plot and save: confusion matrix, ROC curve, PR curve
  (PNG files to Drive).
- Show 10 example false negatives and 10 false positives (URL + probability) in a
  table, to support error analysis in the report.

========================================
6. PROBABILITY CALIBRATION (Phase 5)
========================================
- Implement temperature scaling: a single scalar temperature T optimised with
  LBFGS on the VALIDATION split logits (never the test split), minimising NLL.
- Report Expected Calibration Error (ECE, 10 equal-width bins) on the TEST split
  before and after calibration, plus reliability diagrams (saved as PNG).
- Save the fitted temperature value to Drive as JSON: {"temperature": <float>}.

========================================
7. CROSS-DATASET GENERALISATION TEST (Phase 6)
========================================
- Secondary dataset: Kaggle "malicious_phish" (malicious URLs dataset,
  ~651k URLs, classes: benign / defacement / phishing / malware). Load from
  /content/drive/MyDrive/FYP2/data/malicious_phish.csv (print Kaggle download
  instructions if missing).
- Before testing, remove any URL whose registered domain appeared in the PhiUSIIL
  training or validation splits (leakage control), and report how many were removed.
- Evaluate the calibrated model twice and report both:
  (a) benign vs phishing subset only;
  (b) benign vs all-malicious (defacement+phishing+malware mapped to 1).
- Report the same metrics as Phase 4. A performance drop versus Phase 4 is
  expected; print both side by side in a comparison table.

========================================
8. ONNX EXPORT + INT8 QUANTIZATION + LATENCY (Phase 7)
========================================
- Export the fine-tuned model to ONNX with optimum (ORTModelForSequenceClassification
  or optimum.exporters.onnx), opset >= 14.
- Apply dynamic INT8 quantization with onnxruntime.quantization.quantize_dynamic.
- Accuracy check: re-evaluate FP32-ONNX and INT8-ONNX on a fixed random sample of
  2,000 test URLs; assert the INT8 F1 drop versus the PyTorch model is <= 2
  percentage points; if the assertion fails, keep FP32 ONNX as the deployment
  artifact and print a warning (this fallback is project policy).
- Latency benchmark on CPU (Colab CPU, single thread): median and P95 per-URL
  inference time (batch size 1, 200 warm+measured runs) for PyTorch-CPU, ONNX-FP32,
  ONNX-INT8, printed as a table. Target context: total inference budget for the
  whole system is 500 ms; this model should be well under 150 ms per URL on CPU.
- Save final deployment artifacts to Drive: model.onnx (quantized), tokenizer
  files, temperature.json, and a metrics_summary.json containing all headline
  numbers from Phases 4-7.
- Final cell: define and demo a function predict_url(url: str) -> float that loads
  the INT8 ONNX model + tokenizer + temperature and returns the calibrated
  phishing probability p_url. Demo it on 5 hardcoded example URLs (mix of
  obviously benign, obviously phishing-looking, and a shortened URL).

========================================
9. STYLE
========================================
- Concise markdown cell before each phase explaining in 2-3 sentences what the
  phase does and why (audience: a final-year CS student writing a report).
- No placeholder/pseudo code — every cell must run as written.
- Keep total training time within ~1-2 hours on a T4 (subsample the training set
  to at most 200k URLs if needed, stating so clearly).
```

---

## 这个 prompt 里已经锁定的关键决策（对照 Development Plan v2）

| Prompt 里的 spec | 来自计划的哪条决策 |
|---|---|
| DomURLs_BERT，只用 URL string，丢弃 54 个手工特征 | Method 1 = string-level analyzer，非 traditional ML |
| Registered-domain 级别的 70/15/15 split（tldextract） | Dataset plan 的 leakage control |
| Temperature scaling 在 validation 上拟合 + ECE 报告 | Fusion Stage 1 需要 calibrated probability |
| Cross-dataset test（malicious_phish，去重后） | Evaluation plan 的 generalisation 证据 |
| ONNX INT8 + "掉分 ≤2pp 否则回退 FP32" assertion | Risk mitigation：quantization 政策 |
| CPU latency 基准（目标 <150ms/URL） | 两级 latency 指标（inference ≤500ms） |
| Phase 0–7 checkpoint-resumable 结构 | 沿用你 FYP1 notebook 的成熟工作方式 |
| `predict_url(url) → p_url` 最终函数 | 就是 backend `/scan` 里 Method 1 要调用的接口 |

## 使用注意

1. 贴给 AI 时**整段贴**，不要删 FALLBACK 和 assertion 的部分 —— 那些是防坑的。
2. 生成 notebook 后先跑 Phase 0–2，验证数据下载和 domain-level split 没问题，再开始训练。
3. 需要准备的数据文件（Phase 1/6 的 fallback 路径）：
   - PhiUSIIL: `MyDrive/FYP2/data/PhiUSIIL_Phishing_URL_Dataset.csv`（ucimlrepo 正常的话不需要）
   - malicious_phish: `MyDrive/FYP2/data/malicious_phish.csv`（从 Kaggle 下载）
