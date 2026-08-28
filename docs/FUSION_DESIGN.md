# Fusion Engine — Formal Design and Justification

The formula, what it is called in the literature, and the references that support each
design decision. Written to be quoted in the FYP2 report.
融合引擎的数学定义、学术名称、以及支撑每个设计决策的文献。可直接用于 FYP2 报告。

---

## 1. The formula 公式

For one scan, let **x** be the fixed-order feature vector assembled from both branches:

```
x = [ p_structural, structural_present,
      p_url,        semantic_present,
      llm_score,    llm_invoked,
      domain_unknown,
      rule_1, rule_2, ..., rule_11 ]                        (18 features)
```

The fused fraud probability is a **logistic (sigmoid) function of a weighted sum**:

```
        z        = Σ  wᵢ · xᵢ  +  b
                   i

        p_fraud  = σ(z) = 1 / (1 + e^(−z))

        risk     = round(100 · p_fraud)

        verdict  = Safe     if risk < τ_safe        (τ_safe = 38)
                   Warning  if τ_safe ≤ risk < τ_blocked
                   Blocked  if risk ≥ τ_blocked     (τ_blocked = 55)
```

subject to a **monotonicity constraint** on every risk-bearing feature:

```
        wᵢ ≥ 0   for all i ∈ {p_structural, p_url, llm_score,
                              domain_unknown, rule_1 … rule_11}
```

The weights **w** and bias *b* are **learned** from QRGuard-Mix (900 labelled scans),
not chosen by hand. Thresholds τ are tuned on the training split against two operating
targets: Blocked-tier precision ≥ 0.95 and Safe-tier false-negative rate ≤ 0.02.

### Worked example (the fake-Maybank scan)

| feature | value | weight | contribution |
|---|---|---|---|
| p_structural | 0.0001 | 54.284 | 0.003 |
| p_url | 0.9913 | 6.699 | 6.640 |
| domain_unknown | 1.0 | 0.218 | 0.218 |
| rule_suspicious_tld | 1.0 | 30.667 | 30.667 |
| intercept | — | −7.132 | −7.132 |
| **z** | | | **30.395** |

`p_fraud = σ(30.395) ≈ 1.000` → `risk = 100` → **Blocked**.
The image branch contributed 0.003; the verdict rests on the semantic branch.

---

## 2. What this is called, and why it is justified

### 2.1 Score-level fusion with a *trained* rule 分数层融合(可训练规则)

Combining several detectors' output **scores** — rather than their raw features or
their final labels — is **score-level fusion**, the standard formulation in multimodal
biometrics. That literature divides fusion rules into:

- **fixed rules** — AND, OR, sum, product, min, max
- **trained rules** — weighted sum, logistic regression, SVM, Bayesian classifiers

QRGuard uses a **trained rule**. Reviews of multimodal biometric fusion report that
trained rules (weighted sum / logistic regression) outperform fixed sum or product
rules, and that score-level fusion offers the best trade-off between information
content and ease of combination.

> Ross, A. and Jain, A. K., "Information fusion in biometrics", *Pattern Recognition
> Letters*, 24(13), 2003.
> Nandakumar, K. et al., "Likelihood ratio-based biometric score fusion", *IEEE TPAMI*,
> 30(2), 2008.
> Singh, M. et al., "Fusion in multimodal biometric system: a review",
> *Indian Journal of Science and Technology*, 2017.

**Relation to FYP1.** FYP1 combined its two detectors with an **OR rule** — a fixed
rule. Three limitations motivated the change: an OR rule cannot express "two weak
signals together indicate fraud", it produces only a binary output (no graded score for
a Warning tier), and its false-positive rate grows as detectors are added.

### 2.2 Stacked generalization (stacking) 堆叠泛化

Training a second-level model on the outputs of first-level models is **stacked
generalization**, introduced by Wolpert. The base learners (structural CNN, Method 1,
rule engine) produce *level-0* predictions; the meta-learner is trained on those
predictions as *level-1* data.

> D. H. Wolpert, "Stacked generalization", *Neural Networks*, 5(2), pp. 241–259, 1992.

Logistic regression is the conventional choice of meta-learner: it is low-variance
(important here, where the level-1 training set is only 900 rows), and its weights are
directly interpretable.

**Leakage control.** Stacking is vulnerable to the meta-learner seeing base-learner
predictions made on their own training data. QRGuard-Mix avoids this by drawing its
URLs from Method 1's **held-out test split**, so `p_url` is measured out-of-sample.

### 2.3 Probability calibration 概率校准

A weighted sum of probabilities is only meaningful if those probabilities mean the same
thing. Modern neural networks are systematically **over-confident**, so each branch's
output is calibrated by **temperature scaling** before fusion: `p = softmax(logits / T)`,
with a single scalar *T* fitted on a validation split.

> C. Guo, G. Pleiss, Y. Sun and K. Q. Weinberger, "On calibration of modern neural
> networks", *Proc. 34th ICML*, PMLR 70, 2017. (arXiv:1706.04599)
> J. Platt, "Probabilistic outputs for support vector machines...", *Advances in Large
> Margin Classifiers*, 1999. — the single-parameter method temperature scaling derives from.

Fitted values: structural CNN *T* = 1.392 (ECE 0.0008 → 0.0002); Method 1 *T* = 2.203
(ECE 0.0202 → 0.0052). Calibration quality is reported as **Expected Calibration
Error**, the standard metric in the same paper.

### 2.4 Monotonicity constraints on risk features 单调性约束

Every risk signal is constrained to a **non-negative weight**, so its presence can only
raise the score. This is standard practice in regulated risk scoring (credit scoring in
particular), where model behaviour must agree with domain knowledge and remain
explainable.

> Provenir, "Constraining machine learning credit decision models" (industry practice).
> Chen, C. et al., "An interpretable model for credit risk performance",
> Duke–FICO Explainable ML Challenge, 2018.
> Literature on monotonic GAMs / monotonic neural additive models for credit scoring.

**Why it was necessary here, empirically.** Without the constraint, the fit gave
`rule_non_https` a weight of **−0.466** — i.e. "no encryption ⇒ safer". The cause was a
corpus artefact: many benign URLs in the training data are older `http://` sites. A
security system in which a risk indicator lowers risk is indefensible, so the direction
of each risk signal is constrained rather than learned. Because scikit-learn cannot
express per-feature bounds, the model is fitted with **L-BFGS-B** on the class-balanced
logistic loss.

> R. H. Byrd, P. Lu, J. Nocedal and C. Zhu, "A limited memory algorithm for bound
> constrained optimization", *SIAM J. Scientific Computing*, 16(5), 1995. — L-BFGS-B.

### 2.5 Class weighting 类别加权

QRGuard-Mix is a *diagnostic grid*: five of its six cells are dangerous (750:150). Real
scans are overwhelmingly benign, so fitting on the raw ratio biases the model toward
alarming. Class weights `n / (2·n_c)` (scikit-learn's `class_weight="balanced"`) remove
that artefact. Measured effect: falsely blocked clean/benign QRs dropped from 11/45 to
3/45.

### 2.6 Deterministic override rules 确定性覆盖规则

After the model score, a small set of rules can only *raise* risk:

- a confirmed blocklist hit forces Blocked;
- an executable payload (`javascript:` / `data:` URI) forces Blocked;
- a rule that fired but whose weight is untrained floors the score into Warning.

These encode **facts, not predictions** (the scheme *is* `javascript:`), so overriding a
probabilistic score is justified. This hybrid of a learned model with a deterministic
safety layer is the usual architecture in deployed fraud and abuse detection.

### 2.7 Explicit abstention 明确弃权

An absent branch contributes **0**, and its `*_present` indicator is set to 0, so
"no evidence" is representable and distinguishable from "evidence of no risk".
The API also states why the branch is absent: `not_applicable` is a normal complete
outcome (for example, a URL model on Wi-Fi/text/payment data), while `unavailable`
marks `partial_analysis`. Camera and Gallery use the same one-image continuous-score
contract and the same Fusion model, with acquisition-domain Structural artifacts;
the camera source never suppresses or threshold-replaces a completed score.
Missing-indicator encoding is standard practice for informative missingness.

> Little, R. J. A. and Rubin, D. B., *Statistical Analysis with Missing Data*, Wiley.

---

## 2.8 Recent literature (2024–2026) 最新文献

The foundational papers above establish that the method is *sound*; the papers below
establish that it is *current*. Cite them in pairs — the origin and the 2024–2026 work
that still uses or extends it.

### The single most important reference for this project

> **A systematic literature review on deep learning approaches for QR code-based
> phishing (quishing) detection: emerging attack vectors, multimodal feature fusion and
> open research challenges.** *Journal of Cyber Security Technology*, Vol. 10, No. 1,
> **2026**. DOI: [10.1080/23742917.2026.2696261](https://www.tandfonline.com/doi/full/10.1080/23742917.2026.2696261)

A 2026 systematic review of **41 papers (2021–2026)** whose title names **multimodal
feature fusion** as a core theme in quishing detection, and which surveys exactly the
model families QRGuard uses (CNN, ViT, LSTM, BERT, GAN, GNN). Its stated future
direction — CNNs and vision transformers to capture spatial patterns *within* QR codes —
is what the structural branch does. Use it to establish that fusing image-level and
payload-level evidence is a recognised research direction rather than an ad-hoc choice,
and position QRGuard against the open challenges it lists.

### Fusion architectures that mirror QRGuard's

> **A Hybrid, Multi-Layered Pipeline for Phishing and Threat Classification:
> Independently Validated URL and NLP Engines with a Calibrated Multi-Channel Fusion
> Stage.** [arXiv:2606.21690](https://arxiv.org/html/2606.21690v2), 2026.

Architecturally the closest contemporary work: independently validated per-modality
engines feeding a **calibrated** fusion stage. Confirms that "validate each branch
separately, then fuse calibrated scores" is current practice, not an invention of this
project. (It fuses with a calibrated probabilistic-OR; QRGuard learns the rule instead,
which is a defensible point of difference to discuss.)

> **AntiPhishStack: LSTM-based Stacked Generalization Model for Optimized Phishing URL
> Detection.** [arXiv:2401.08947](https://arxiv.org/pdf/2401.08947), 2024.

Direct evidence that **Wolpert's stacked generalization is still the chosen framework**
for phishing URL detection in 2024 — the strongest single citation for keeping a
1992 method.

> **PhishGuard: A Multi-Layered Ensemble Model for Optimal Phishing Website Detection.**
> [arXiv:2409.19825](https://arxiv.org/pdf/2409.19825), 2024.
> **Hybrid Stacking Ensemble Model for Phishing URL Detection Using PCA and Machine
> Learning**, 2025 — 97.64% accuracy with a stacking ensemble.
> **Enhanced Phishing Website Detection Using Optimized Stacking Ensembles**,
> *IJACSA*, Vol. 16 No. 8, 2025 — 97.16–98.58% across three datasets.

Three more 2024–2025 papers where stacking ensembles are the state of the art for
phishing detection.

### Multimodal fusion with modern encoders

> **Yuan, X., Wang, J., Yan, T., Qi, F. "LLM-Based Multimodal Feature Extraction and
> Hierarchical Fusion for Phishing Email Detection" (SAHF-PD).** *Electronics* (MDPI),
> 15(2):368, [2026](https://www.mdpi.com/2079-9292/15/2/368). **[VERIFIED — full text read]**

Four modalities per email, each processed by an LLM **constrained to a standardised
output schema** because raw generative output is "unstructured and stochastic" — the same
reason QRGuard forces Method 2 to emit fixed JSON. Fusion is **feature-level**: features
are ranked by mutual information into Core/Auxiliary/Weak layers, PCA-compressed, then
concatenated for one classifier (XGBoost, AUC 0.99927). QRGuard differs by fusing at the
**score level**, which keeps each branch independently validatable and each contribution
readable in the final score. Their stated limitation — external services and page
rendering break sub-second latency — is the same finding that made QRGuard's LLM stage
user-initiated rather than automatic. See docs/REFERENCE_VERIFICATION.md for details.
> **Multimodal and Temporal Graph Fusion Framework for Advanced Phishing Website
> Detection (MMTHF-Net)**, 2025 — F1 0.97 on PhishTank/URLNet, 0.96 on OpenPhish.

Contemporary systems that combine LLM-derived semantics with other modalities through a
fusion stage — the same shape as QRGuard's Method 1 + Method 2 + structural design.

### Calibration is still active research

> **Calibration in Deep Learning: A Survey of the State-of-the-Art.**
> [arXiv:2308.01222](https://arxiv.org/html/2308.01222v4) (maintained survey).
> **GETS: Ensemble Temperature Scaling.** *ICLR* **2025**.

Temperature scaling is not a settled 2017 footnote: ICLR 2025 published an ensemble
extension of it, and the survey confirms post-hoc calibration remains the standard
pre-fusion step for risk-sensitive decisions. This supports calibrating **before**
fusing rather than feeding raw softmax outputs into the meta-learner.

### QR-specific baselines to position against

> F. Trad and A. Chehab, **Detecting Quishing Attacks with Machine Learning Techniques
> Through QR Code Analysis**, [arXiv:2505.03451](https://arxiv.org/abs/2505.03451), 2025
> — XGBoost on QR pixel structure alone, AUC 0.9106, no payload analysis.
> **QR"iS**, [arXiv:2510.17175](https://arxiv.org/pdf/2510.17175), 2025 — structural
> features only, pre-decode.
> M. Sarkhi and S. Mishra, **Detection of QR Code-based Cyberattacks using a Lightweight
> Deep Learning Model**, [*ETASR* 14(4)](https://etasr.com/index.php/ETASR/article/view/7777),
> 2024.

These are the closest QR-specific systems and they are **single-modality**: structure
only, or payload only. QRGuard's contribution is stated against them — the fused system
reaches ROC-AUC 0.966 where its structural branch alone reaches 0.892 and its semantic
branch alone 0.725.

---

## 3. Design decisions summarised 设计决策总表

Each row pairs the **origin** of the technique with **recent work still using it**, so
the report shows both soundness and currency.

| Decision | Technique | Origin | Still current (2024–2026) |
|---|---|---|---|
| Combine branch scores, not features or labels | Score-level fusion | Ross & Jain (2003) | Quishing SLR (*J. Cyber Security Technology*, 2026) |
| Learn the combination instead of an OR rule | Trained fusion rule | biometric fusion reviews | Calibrated multi-channel fusion, arXiv:2606.21690 (2026) |
| Meta-learner over base-learner outputs | Stacked generalization | Wolpert (1992) | AntiPhishStack, arXiv:2401.08947 (2024) |
| Logistic regression as meta-learner | Low variance, interpretable | stacking practice | Stacking ensembles for phishing, IJACSA 16(8) (2025) |
| Make probabilities comparable | Temperature scaling; ECE | Guo et al. (ICML 2017) | GETS: Ensemble Temperature Scaling (ICLR 2025) |
| Risk signals cannot lower risk | Monotonicity constraints | credit-scoring practice | monotonic GAMs / neural additive models |
| Fit under bounds | L-BFGS-B | Byrd et al. (1995) | — (numerical method, unchanged) |
| Correct the diagnostic grid's imbalance | Balanced class weights | standard practice | — |
| Facts override predictions | Deterministic override layer | fraud-detection practice | hybrid learned + rule pipelines, arXiv:2606.21690 |
| Represent a missing branch | Missing indicators | Little & Rubin | — |
| Image + payload evidence together | Multimodal fusion | — | Quishing SLR (2026); MMTHF-Net (2025); SAHF-PD (2026) |

---

## 4. What to write in the report 报告怎么写

> The fusion stage is formulated as **score-level fusion using a trained rule**
> (Ross & Jain, 2003), implemented as **stacked generalization** (Wolpert, 1992) with a
> logistic-regression meta-learner over the calibrated outputs of the structural CNN,
> the semantic URL model, the domain-reliability signal, and the deterministic rule
> engine. Each branch is calibrated by **temperature scaling** (Guo et al., 2017) so the
> combined probabilities are commensurable, and every risk-bearing coefficient is
> constrained to be non-negative, following monotonic-scorecard practice in regulated
> risk modelling; the constrained fit uses L-BFGS-B (Byrd et al., 1995). Weights are
> learned from the QRGuard-Mix ground-truth set, whose URLs are drawn from the semantic
> model's held-out test split to prevent leakage into the meta-learner. Decision
> thresholds are tuned on the training split to satisfy a Blocked-tier precision target
> of 0.95 and a Safe-tier false-negative target of 0.02.

**Ablation to report** (fusion is not decorative):

| model | ROC-AUC |
|---|---|
| structural only | 0.8917 |
| semantic only | 0.7245 |
| **fused** | **0.9658** |

### Positioning against the 2026 quishing SLR 与 2026 综述的定位

The systematic review (*J. Cyber Security Technology*, 10(1), 2026) names **multimodal
feature fusion** as a theme and lists open challenges. QRGuard can be positioned as:

1. **Both modalities, one decision.** The closest QR-specific systems are
   single-modality — Trad & Chehab (2025) analyse QR structure only (AUC 0.9106);
   QR"iS (2025) is structural and pre-decode. QRGuard fuses image-level and
   payload-level evidence and reports the ablation that separates their contributions.
2. **Calibrated fusion, not a fixed rule.** Both branches are temperature-calibrated
   before a *learned* meta-rule combines them, where the field's QR work typically uses
   a single model or a fixed combination.
3. **Monotonic, explainable weights.** Risk directions are constrained, so every score
   decomposes into named, user-facing reasons — addressing the explainability concern
   the review raises for deep quishing detectors.
4. **Measured deployment cost.** Latency and quantisation effects are reported per
   branch (structural 16 ms FP32; Method 1 15 ms INT8), which QR-security papers rarely
   quantify.

Honest scoping to state alongside those claims: the tampered class is synthetically
generated, the URL corpora age, and the LLM stage is user-initiated rather than
always-on — each with the measurement that motivated it.
