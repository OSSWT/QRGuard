# Reference Verification Log 文献核实记录

Only cite what is marked **VERIFIED**. For anything else, obtain the full text first.
只引用标记为 VERIFIED 的文献;其余的先拿到全文再说。

**How to get a reference verified 如何让文献通过核实:** download the PDF (UTAR library,
publisher site, or arXiv) into `Downloads` and tell me the filename. I can read local
PDFs directly and will record the real title, authors, venue, claims, and — importantly —
whether it actually supports the point you want it to support.

---

## VERIFIED — full text read

### [V1] SAHF-PD — LLM-based multimodal fusion for phishing email detection

**Yuan, X., Wang, J., Yan, T., Qi, F.** "LLM-Based Multimodal Feature Extraction and
Hierarchical Fusion for Phishing Email Detection." *Electronics* (MDPI), 15(2):368, 2026.
Received 4 Dec 2025 · Accepted 13 Jan 2026 · Published **14 January 2026**.
Institute of High Energy Physics, Chinese Academy of Sciences. Open access (CC BY).

**What it actually does** (read from the PDF, not a search snippet):
- Four modalities per email: body text, OSINT from the embedded URL, a screenshot of the
  landing page, and the HTML/JavaScript source.
- Each modality is processed by a **modality-specialised LLM driven by a domain-specific
  prompt and constrained to a standardised output schema** (`UnifiedPhishingFeatures`).
  Their stated reason: this "mitigates the unstructured and stochastic nature of raw
  generative outputs, yielding consistent, interpretable, and machine-readable features."
- **SAHF fusion:** features are ranked by **mutual information** with the phishing label
  and split into three layers — Core (≥ 90th percentile), Auxiliary (70th–90th), and
  Weakly-Associated (< 70th, discarded) — then intra-modal PCA compression and weighted
  training. The authors position this explicitly "beyond blind concatenation or
  black-box fusion."
- Results: XGBoost + SAHF reaches **AUC 0.99927, F1 0.98728**; the feature space is cut
  from 228 to 56 dimensions (−75.4%) and average training time by 43.7%.
- Releases **PhishMMF**, 11,672 human-verified samples.
- **Ablation studies confirm the unique contribution of each modality.**
- Stated limitation: dependence on external services (e.g. VirusTotal) and page rendering
  introduces latency "incompatible with the sub-second response requirements" of
  real-time filtering.

**How to use it in your report — three separate, honest jobs:**

1. **Justify constraining the LLM to a JSON schema.** This is the strongest use. Your
   `analyzer_v1.txt` forces Method 2 to emit a fixed JSON object for exactly the reason
   [V1] states — raw generative output is unstructured and stochastic, and a schema makes
   it machine-readable. Near-identical design decision, independently arrived at, in a
   2026 journal paper.

2. **Justify per-modality ablation.** [V1] confirms each modality's contribution by
   ablation; your ablation (structural 0.892 / semantic 0.725 / fused 0.966) is the same
   methodology, so cite it as established practice rather than something you invented.

3. **Contrast the fusion level — this is where you differ, and it favours you.**
   [V1] performs **feature-level** fusion: LLM-extracted features are ranked, compressed
   and concatenated before a single classifier. QRGuard performs **score-level** fusion:
   each branch produces a calibrated probability and a meta-learner combines those. State
   the difference plainly and give your reason — score-level fusion lets each branch be
   validated independently and keeps per-branch contributions readable in the final score,
   which is what produces your user-facing reasons.

4. **Use their limitation to motivate your design.** [V1] reports that external services
   and page rendering break sub-second latency. QRGuard reaches the same conclusion from
   its own measurement and responds differently: the LLM stage is **user-initiated**, not
   in the automatic path, so the default scan stays fast. That is a direct, citable
   contrast — same problem, different engineering answer.

**Do NOT claim:** that [V1] is about QR codes (it is phishing *email*), or that it uses
score-level fusion or calibration (it does not).

---

### [V2] Hybrid multi-layered pipeline with a calibrated fusion stage — the closest architectural match

**Ismail, S. M., Ibrahim, A. O., Mahmoud, O. A.** "A Hybrid, Multi-Layered Pipeline for
Phishing and Threat Classification: Independently Validated URL and NLP Engines with a
Calibrated Multi-Channel Fusion Stage." arXiv:2606.21690v2, 2026. Zewail City of Science
and Technology, Egypt. 10 pages.

**What it actually does:**
- Opens with "**Phishing is a multi-modal threat**" and argues most detectors still
  reason over one modality at a time: "A URL classifier cannot read intent from prose; a
  text classifier cannot judge a freshly registered domain."
- Three engines, each **independently benchmarked** before fusion: a four-stage URL stack,
  a generalization-hardened DistilBERT NLP classifier, and a threat-intelligence
  synchronizer.
- **Decision-level fusion** over URL, header and phishing-probability channels using a
  **calibrated probabilistic-OR**; F1 = 0.914 on a 10,677-email whole-system benchmark.
- Their DistilBERT's held-out real-phishing recall rises **from 0.8% to 87.3%** after
  generalization hardening.
- The authors are candid that their benchmark uses proxy channels and "an operating point
  still needing recalibration", presenting it as a preliminary integrated result.

**The single most useful sentence in this paper for your report:**

> *"For deployable detection, the limiting factor is how well a model generalizes, not
> how accurately it scores data drawn from its own training distribution."*

**How to use it — this is your strongest methodological citation:**

1. **It validates your RUN 1 → RUN 2 → RUN 3 narrative.** Your Method 1 scored F1 0.999
   in-domain but ROC-AUC 0.53 cross-dataset, which forced two retrains. [V2] states that
   exact principle as its conclusion and shows the same phenomenon (recall 0.8% → 87.3%
   on held-out real phishing). Cite it so your iteration reads as engaging with a known,
   published problem rather than as a mistake you made.
2. **It justifies validating each branch independently before fusing** — the structure of
   your Chapter 5.
3. **It justifies the multi-modal premise** in one quotable line.
4. **Point of difference:** [V2] fuses with a *calibrated probabilistic-OR* — a fixed rule
   applied to calibrated scores. QRGuard learns the fusion rule from labelled data. Both
   calibrate first; you go one step further, and you have the ablation to justify it.

### [V3] AntiPhishStack — stacked generalization is current practice

**Aslam, S., Aslam, H., Manzoor, A., Hui, C., Rasool, A.** "AntiPhishStack: LSTM-based
Stacked Generalization Model for Optimized Phishing URL Detection." arXiv:2401.08947v2,
2024. Shenzhen Institute of Advanced Technology, Chinese Academy of Sciences. 26 pages.

**What it actually does:**
- A **two-phase stacked generalization** model. Phase I trains base ML classifiers on URL
  and character-level TF-IDF features using **K-fold cross-validation for robust mean
  prediction**. Phase II uses a two-layered stacked LSTM with five adaptive optimizers.
- Predictions from both phases are integrated to train a **meta-XGBoost classifier** for
  the final prediction.
- Explicitly designed to operate "without prior phishing-specific feature knowledge".
- Validated on two benchmark datasets.

**How to use it:**
1. **The proof that Wolpert (1992) is still the framework of choice in 2024** — this is
   its main job. Cite as: "stacked generalization [Wolpert 1992] remains the framework of
   choice for phishing URL detection [AntiPhishStack 2024]".
2. **It justifies your leakage control.** They generate level-1 data via K-fold
   cross-validation so the meta-learner never sees base-learner predictions made on their
   own training data. QRGuard achieves the same guarantee differently — QRGuard-Mix draws
   its URLs from Method 1's held-out test split. Same principle, and you can say so.
3. **Difference to note honestly:** their base learners are all URL-based (one modality,
   different algorithms). Yours are different *modalities* (image vs text). Stacking is
   the shared mechanism, not the architecture.

### [V4] PhishGuard — ensemble optimisation (weaker match, use narrowly)

**Ovi, M. S. I., Rahman, M. H., Hossain, M. A.** "PhishGuard: A Multi-Layered Ensemble
Model for Optimal Phishing Website Detection." arXiv:2409.19825v1, 2024. George Mason
University and Green University of Bangladesh. 6 pages. Submitted to IEEE.

**What it actually does:** combines Random Forest, Gradient Boosting, CatBoost and
XGBoost; feature selection via SelectKBest and RFECV; hyperparameter tuning and data
balancing (SMOTE); 99.05% accuracy on one of four public datasets.

**How to use it — and how not to.** This is a **homogeneous ensemble over one tabular
feature set**, not multi-modal fusion. Use it only to support two narrow points:
(a) ensemble learning plus optimisation is the current baseline standard in phishing
detection, and (b) **class balancing is standard practice** — they use SMOTE, you use
balanced class weights for the same reason. Do **not** cite it as evidence for
multi-modal or score-level fusion; it is neither.

---

## UNVERIFIED — do not cite until you have the full text

| Ref | What we believe it is | How to get it |
|---|---|---|
| Quishing SLR, *J. Cyber Security Technology* 10(1), 2026, DOI 10.1080/23742917.2026.2696261 | Systematic review of 41 quishing papers (2021–2026); title names *multimodal feature fusion* and open challenges | **UTAR library / Taylor & Francis** — the publisher blocked direct access. This is your highest-value reference; get it first. |
| GETS: Ensemble Temperature Scaling, ICLR 2025 | Ensemble extension of temperature scaling | Free on ICLR proceedings |
| IJACSA 16(8), 2025 — optimized stacking ensembles | 97.16–98.58% across three datasets | Free on thesai.org |
| MMTHF-Net (2025) — multimodal temporal graph fusion | F1 0.97 PhishTank/URLNet | ResearchGate |

## Classics — standard citations, still confirm page numbers

| Ref | Use |
|---|---|
| Wolpert, D. H. "Stacked generalization." *Neural Networks* 5(2):241–259, 1992 | The meta-learner framework |
| Guo, C. et al. "On calibration of modern neural networks." *ICML* 2017 (arXiv:1706.04599) | Temperature scaling, ECE |
| Ross, A. & Jain, A. K. "Information fusion in biometrics." *Pattern Recognition Letters* 24(13), 2003 | Fixed vs trained fusion rules |
| Byrd, R. H. et al. "A limited memory algorithm for bound constrained optimization." *SIAM J. Sci. Comput.* 16(5), 1995 | L-BFGS-B |

---

## Checklist before adding any reference 加入前的检查清单

1. Do I have the full text (or at least the real abstract from the publisher)?
2. Does it actually say what I claim? Quote the sentence in your notes.
3. Which job does it do — establish the problem, define a method, prove the method is
   current, or contrast with related work? If none, drop it.
4. Could I answer "what does this paper do?" in a viva without notes?
