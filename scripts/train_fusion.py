"""Train the Fusion Engine's meta-classifier on QRGuard-Mix.

Pipeline:
  1. Run BOTH branches over every QRGuard-Mix sample (structural CNN on the image,
     Semantic Training + rule engine on the URL) and cache the raw signals.
  2. Build the fixed-order feature vector for each sample.
  3. Split by cell (stratified) so every combination appears in train and test.
  4. Fit a monotonic logistic model to v2's calibrated risk targets. This lets
     a clean open-Wi-Fi payload learn Warning rather than being mislabeled Safe
     or Blocked merely to fit a binary target.
  5. Tune the Safe/Warning/Blocked thresholds against the project targets:
       Blocked-tier precision >= 0.95   (do not cry wolf)
       Safe-tier false-negative rate <= 0.02 (do not let fraud through)
  6. Report the 3-class confusion matrix and the ABLATION that justifies fusion:
     structural-only vs semantic-only vs fused.
  7. Save a candidate, and promote it to fusion_weights.json only when every
     aggregate AND per-cell deployment gate passes.

Method 2 (LLM) note: QRGuard-Mix carries no LLM verdicts (that needs an API key and a
labelled subset), so the `llm_score` / `llm_invoked` slots are absent for every training
row and their learned weight is ~0. The feature positions are reserved by the contract,
so adding an LLM-labelled subset later is a retrain, not a redesign. This is stated in
the saved metadata so nobody mistakes the current weights for LLM-aware ones.

Usage:
    python scripts/train_fusion.py
    python scripts/train_fusion.py --cache-only     # just recompute branch signals
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fusion.engine import HARD_OVERRIDE_FLAGS, RULE_TIER_FLOORS  # noqa: E402
from fusion.features import FEATURE_NAMES, BranchInputs, build_feature_vector  # noqa: E402
from semantic.domain_reputation import domain_unknown  # noqa: E402
from semantic.semantic_service import load_analyzer as load_semantic  # noqa: E402
from semantic.payload_router import route_payload  # noqa: E402
from semantic.rule_engine import check_url  # noqa: E402
from structural.structural_service import load_analyzer as load_structural  # noqa: E402

MIX_DIR = ROOT / "data" / "qrguard_mix_v2"
SIGNALS_PATH = MIX_DIR / "branch_signals.csv"
# Fingerprint of the models that produced the cache. Without it, retraining the
# structural CNN and rerunning this script silently refits fusion on the PREVIOUS
# model's p_structural -- the weights would describe a model no longer installed,
# and p_structural carries the largest weight in the whole vector.
SIGNALS_META_PATH = MIX_DIR / "branch_signals.meta.json"
WEIGHTS_PATH = ROOT / "backend" / "fusion" / "fusion_weights.json"
CANDIDATE_PATH = ROOT / "backend" / "fusion" / "fusion_weights.candidate.json"
DECISION_VERSION = "decision-2026.02"
DECISION_PERFORMANCE_DIR = (
    ROOT / "ml_training" / "decision_layer" / "performance" / DECISION_VERSION
)
DECISION_RUN_DIR = (
    ROOT / "ml_training" / "decision_layer" / "runs" / DECISION_VERSION / "artifacts"
)

TARGET_BLOCKED_PRECISION = 0.95
TARGET_SAFE_FNR = 0.02
SEED = 42
CAMERA_SEMANTIC_ONLY_BLOCK_MIN = 0.70


# ---------------------------------------------------------------------------
# 1. Branch signals
# ---------------------------------------------------------------------------

def model_fingerprint() -> dict:
    """Identify everything the cached signals depend on: the models AND the data.

    Both halves have already gone stale in practice. Retraining the CNN left the
    cache describing a model no longer installed; then rebuilding QRGuard-Mix
    left it describing images no longer on disk, because the first version of
    this check only looked at the models. A signal is a function of both, so both
    are fingerprinted.

    Size plus calibration temperature identifies a model: a retrain always
    recalibrates, and a different export always differs in size. For the dataset,
    the images are content-hashed via the manifest, which records one row per
    image including its URL and label.
    """
    art = ROOT / "training" / "artifacts"
    out = {}
    for name, directory in (("structural", art / "structural"), ("semantic", art / "semantic")):
        temp = directory / "temperature.json"
        onnx = sorted(directory.glob("*.onnx"))
        joblib_models = sorted(directory.glob("*.joblib"))
        metadata = directory / "model_metadata.json"
        out[name] = {
            "temperature": json.loads(temp.read_text())["temperature"] if temp.is_file() else None,
            "onnx_bytes": {p.name: p.stat().st_size for p in onnx},
            "joblib_sha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                for p in joblib_models
            },
            "metadata_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest()[:16]
            if metadata.is_file()
            else None,
        }

    manifest = MIX_DIR / "manifest.csv"
    images = MIX_DIR / "images"
    manifest_frame = pd.read_csv(manifest) if manifest.is_file() else pd.DataFrame()
    named_images = [images / str(name) for name in manifest_frame.get("filename", [])]
    out["dataset"] = {
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()[:16]
        if manifest.is_file() else None,
        # The manifest names the images but not their pixels, and the tampering
        # recipe can change without the manifest moving. Total size over the
        # image directory is a cheap proxy that does move when they are redrawn.
        "image_count": sum(path.is_file() for path in named_images),
        "image_bytes": sum(path.stat().st_size for path in named_images if path.is_file()),
    }
    return out


def load_cached_signals() -> pd.DataFrame | None:
    """Return cached signals only if they were produced by the installed models."""
    if not SIGNALS_PATH.is_file():
        return None
    current = model_fingerprint()
    recorded = (json.loads(SIGNALS_META_PATH.read_text())
                if SIGNALS_META_PATH.is_file() else None)
    if recorded != current:
        print("Cached branch signals were produced by different model artifacts.")
        if recorded is None:
            print("  (no fingerprint recorded - the cache predates this check)")
        else:
            for part in current:
                if recorded.get(part) != current[part]:
                    print(f"  {part} changed:")
                    print(f"    cached {recorded.get(part)}")
                    print(f"    now    {current[part]}")
        print("  Recomputing rather than fitting fusion to a model that is not installed.")
        return None
    return pd.read_csv(SIGNALS_PATH).fillna({"rule_flags": ""})


def compute_signals(manifest: pd.DataFrame) -> pd.DataFrame:
    from PIL import Image

    structural = load_structural()
    semantic = load_semantic()
    rows = []
    for i, r in enumerate(manifest.itertuples(), 1):
        s = structural.predict(Image.open(MIX_DIR / "images" / r.filename))
        evidence_mode = getattr(r, "evidence_mode", f"gallery_{r.image_class}")
        if evidence_mode == "camera_clean_consensus":
            p_structural = 0.0
            structural_type = "clean"
        elif evidence_mode == "camera_uncertain_abstain":
            p_structural = None
            structural_type = "uncertain"
        elif evidence_mode == "camera_tampered_consensus":
            # Effective evidence emitted only after the locked multi-frame
            # camera policy accepts stable physical tampering.
            p_structural = 0.95
            structural_type = "tampered"
        else:
            p_structural = s.p_structural
            structural_type = s.predicted_type
        payload = str(getattr(r, "payload", r.url))
        info = route_payload(payload)
        flags = [f.flag for f in check_url(info)]
        p_url = None
        unknown = None
        if info.is_url and info.scheme not in ("javascript", "data"):
            p_url = semantic.predict(info.normalized_url or payload).p_url
            unknown = domain_unknown(info.registered_domain)
        rows.append(
            {
                "filename": r.filename,
                "p_structural": p_structural,
                "structural_type": structural_type,
                "p_url": p_url,
                "rule_flags": "|".join(flags),
                "domain_unknown": unknown,
                "dangerous": r.dangerous,
                "risk_target": r.risk_target,
                "target_tier": r.target_tier,
                "cell": r.cell,
                "url_label": r.url_label,
                "image_class": r.image_class,
                "payload_kind": r.payload_kind,
                "image_source": r.image_source,
                "evidence_mode": evidence_mode,
            }
        )
        if i % 100 == 0:
            print(f"  scored {i}/{len(manifest)}")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2-4. Features, split, fit
# ---------------------------------------------------------------------------

def to_matrix(signals: pd.DataFrame) -> np.ndarray:
    def optional(value):
        return None if pd.isna(value) else float(value)

    return np.vstack(
        [
            build_feature_vector(
                BranchInputs(
                    p_structural=optional(r.p_structural),
                    p_url=optional(r.p_url),
                    llm_score=None,  # not available in QRGuard-Mix (see module docstring)
                    rule_flags=r.rule_flags.split("|") if r.rule_flags else (),
                    domain_unknown=optional(getattr(r, "domain_unknown", None)),
                )
            )
            for r in signals.itertuples()
        ]
    )


# The three tiers must stay distinct: a Warning band is the whole point of a graded
# score, so each cut-off is searched inside its own range rather than letting the two
# collapse onto the same value.
SAFE_SEARCH = range(10, 46)      # Safe stays conservative
BLOCKED_SEARCH = range(55, 96)   # Blocked stays confident


def tune_thresholds(p_fraud: np.ndarray, y: np.ndarray) -> tuple[int, int]:
    """Pick Safe/Blocked cut-offs meeting both project targets, keeping a Warning band."""
    scores = np.round(100 * p_fraud).astype(int)

    # Blocked cut-off: lowest threshold in range whose precision meets the target.
    blocked_min = BLOCKED_SEARCH.stop - 1
    for t in BLOCKED_SEARCH:
        flagged = scores >= t
        if flagged.sum() and y[flagged].mean() >= TARGET_BLOCKED_PRECISION:
            blocked_min = t
            break

    # Safe cut-off: highest threshold in range whose missed-fraud rate stays in target.
    safe_max = SAFE_SEARCH.start
    for t in reversed(SAFE_SEARCH):
        missed = y[scores < t].sum() / max(y.sum(), 1)
        if missed <= TARGET_SAFE_FNR:
            safe_max = t
            break

    return safe_max, blocked_min


def apply_runtime_policy(
    scores: np.ndarray,
    rows: pd.DataFrame,
    safe_max: int,
    blocked_min: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply the same post-score safety policy used by the serving pipeline.

    The meta-classifier estimates continuous risk. Product invariants such as an
    open network being at least Warning, and an uncertain camera branch failing
    closed for an unknown/flagged destination, are deterministic policy. Evaluating
    raw scores without these rules was train/evaluation-to-serving skew.
    """
    adjusted = np.asarray(scores, dtype=int).copy()
    for position, row in enumerate(rows.itertuples()):
        flags = set(str(row.rule_flags).split("|")) if row.rule_flags else set()
        for flag in HARD_OVERRIDE_FLAGS:
            if flag in flags:
                adjusted[position] = max(adjusted[position], blocked_min)
        for flag, tier in RULE_TIER_FLOORS.items():
            if flag in flags:
                floor = safe_max if tier == "warning" else blocked_min
                adjusted[position] = max(adjusted[position], floor)

        # Mirror app.pipeline.run_scan: camera abstention is not attack evidence,
        # but an unknown, flagged, or non-URL result may not silently become Safe.
        if row.evidence_mode == "camera_uncertain_abstain" and adjusted[position] < safe_max:
            p_url_present = not pd.isna(row.p_url)
            known_domain = not pd.isna(row.domain_unknown) and float(row.domain_unknown) == 0.0
            semantic_url_supports_safe = p_url_present and known_domain and not flags
            if not semantic_url_supports_safe:
                adjusted[position] = safe_max

        # Mirror the partial-evidence upper guard in app.pipeline.run_scan: a
        # moderate Semantic score alone warrants Warning, not a hard Block.
        if (
            row.evidence_mode == "camera_uncertain_abstain"
            and adjusted[position] >= blocked_min
            and not pd.isna(row.p_url)
            and float(row.p_url) < CAMERA_SEMANTIC_ONLY_BLOCK_MIN
            and not (flags & set(HARD_OVERRIDE_FLAGS))
        ):
            adjusted[position] = blocked_min - 1

    tiers = np.where(
        adjusted < safe_max,
        "safe",
        np.where(adjusted < blocked_min, "warning", "blocked"),
    )
    return adjusted, tiers


# Features whose weight must be >= 0: every one is a RISK signal, so its presence can
# only raise the score. Without this constraint the fit picks up dataset artefacts --
# e.g. many benign URLs in the corpus are old http:// sites, which made `non_https`
# learn a NEGATIVE weight, i.e. "no encryption => safer". Indefensible in a security
# system, so risk directions are constrained rather than learned.
def _monotonic_bounds() -> list[tuple[float | None, float | None]]:
    bounds = []
    for name in FEATURE_NAMES:
        risk_signal = name.startswith("rule_") or name in (
            "p_structural", "p_url", "llm_score", "domain_unknown"
        )
        bounds.append((0.0, None) if risk_signal else (None, None))
    return bounds


def fit_constrained(
    X: np.ndarray,
    y: np.ndarray,
    class_weight: bool = True,
    bounds: list | None = None,
    class_labels: np.ndarray | None = None,
):
    """Logistic regression with non-negative weights on risk signals.

    Returns (coef, intercept). Uses L-BFGS-B on the (optionally class-balanced)
    logistic loss, since scikit-learn cannot express per-feature bounds.
    `bounds` must match X's column count; defaults to the full feature contract.
    """
    from scipy.optimize import minimize

    bounds = list(bounds) if bounds is not None else _monotonic_bounds()
    if len(bounds) != X.shape[1]:
        raise ValueError(f"bounds ({len(bounds)}) != n_features ({X.shape[1]})")

    # Pin unidentifiable weights to zero. A column that never varies in training
    # carries no information, so any weight the optimiser assigns it is arbitrary --
    # yet that column DOES vary at run time (llm_score once Method 2 is wired in,
    # *_present when a branch abstains). Leaving an arbitrary weight there would let
    # untrained parameters move real verdicts, so they are fixed at 0 until data
    # exists to identify them.
    constant = np.ptp(X, axis=0) < 1e-12
    bounds = [(0.0, 0.0) if c else b for b, c in zip(bounds, constant)]
    fit_constrained.last_constant_mask = constant

    labels = np.asarray(class_labels) if class_labels is not None else (y >= 0.5)
    w = np.ones(len(y), dtype=float)
    if class_weight:  # same effect as sklearn's class_weight="balanced"
        for cls in (0, 1):
            mask = labels == cls
            if mask.sum():
                w[mask] = len(y) / (2.0 * mask.sum())

    def loss_and_grad(theta):
        coef, b = theta[:-1], theta[-1]
        z = X @ coef + b
        # stable log(1 + exp(z))
        softplus = np.logaddexp(0.0, z)
        loss = float(np.sum(w * (softplus - y * z)))
        p = 1.0 / (1.0 + np.exp(-z))
        resid = w * (p - y)
        return loss, np.concatenate([X.T @ resid, [resid.sum()]])

    res = minimize(
        loss_and_grad,
        x0=np.zeros(X.shape[1] + 1),
        jac=True,
        method="L-BFGS-B",
        bounds=bounds + [(None, None)],  # intercept unconstrained
        options={"maxiter": 5000},
    )
    return res.x[:-1], float(res.x[-1])


def _predict_proba(X: np.ndarray, coef: np.ndarray, intercept: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(X @ coef + intercept)))


def ablation(X: np.ndarray, y: np.ndarray, idx_tr, idx_te) -> dict[str, float]:
    """Fusion vs each branch alone — the core evidence that fusion is needed."""
    from sklearn.metrics import roc_auc_score

    name_idx = {n: i for i, n in enumerate(FEATURE_NAMES)}
    subsets = {
        "structural_only": [name_idx["p_structural"], name_idx["structural_present"]],
        "semantic_only": [name_idx["p_url"], name_idx["semantic_present"],
                          name_idx["domain_unknown"]]
        + [i for n, i in name_idx.items() if n.startswith("rule_")],
        "fused": list(range(len(FEATURE_NAMES))),
    }
    out = {}
    for label, cols in subsets.items():
        sub_bounds = [_monotonic_bounds()[c] for c in cols]
        coef, b = fit_constrained(X[np.ix_(idx_tr, cols)], y[idx_tr],
                                  bounds=sub_bounds)
        p = _predict_proba(X[np.ix_(idx_te, cols)], coef, b)
        out[label] = {
            "roc_auc": float(roc_auc_score(y[idx_te], p)),
            "accuracy": float(((p >= 0.5).astype(int) == y[idx_te]).mean()),
        }
    return out


def write_performance_report(
    *,
    weights_blob: dict,
    per_cell: pd.DataFrame,
    cell_metrics: pd.DataFrame,
    target_tiers: np.ndarray,
    predicted_tiers: np.ndarray,
    scores: np.ndarray,
    gate_failures: list[str],
) -> None:
    """Persist report-ready metrics and plots for the Decision Layer run."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    DECISION_PERFORMANCE_DIR.mkdir(parents=True, exist_ok=True)
    DECISION_RUN_DIR.mkdir(parents=True, exist_ok=True)
    blob = dict(weights_blob)
    blob["metadata"] = dict(blob["metadata"])
    blob["metadata"]["version"] = DECISION_VERSION
    blob["metadata"]["model_fingerprint"] = model_fingerprint()
    blob["metadata"]["deployment_gates_passed"] = not gate_failures
    (DECISION_RUN_DIR / "fusion_weights.json").write_text(
        json.dumps(blob, indent=2), encoding="utf-8"
    )

    labels = ["safe", "warning", "blocked"]
    confusion = pd.crosstab(
        pd.Series(target_tiers, name="target"),
        pd.Series(predicted_tiers, name="predicted"),
    ).reindex(index=labels, columns=labels, fill_value=0)
    exact_accuracy = float((target_tiers == predicted_tiers).mean())
    acceptance_rate = float(per_cell.accepted.mean())
    metrics = {
        "display_name": "Risk Decision Layer",
        "version": DECISION_VERSION,
        "trained_on": "QRGuard-Mix-v2",
        "n_train": weights_blob["metadata"]["n_train"],
        "n_test": weights_blob["metadata"]["n_test"],
        "roc_auc": weights_blob["metadata"]["roc_auc_test"],
        "blocked_precision": weights_blob["metadata"]["blocked_precision"],
        "safe_tier_fnr": weights_blob["metadata"]["safe_fnr"],
        "exact_tier_accuracy": exact_accuracy,
        "policy_acceptance_rate": acceptance_rate,
        "thresholds": {
            "safe_max": weights_blob["safe_max"],
            "blocked_min": weights_blob["blocked_min"],
        },
        "confusion_target_by_predicted": confusion.to_dict(orient="index"),
        "ablation": weights_blob["metadata"]["ablation"],
        "per_cell_gate_policy": weights_blob["metadata"]["per_cell_gate_policy"],
        "gates_passed": not gate_failures,
        "gate_failures": gate_failures,
        "model_fingerprint": model_fingerprint(),
    }
    (DECISION_PERFORMANCE_DIR / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    cell_metrics.to_csv(DECISION_PERFORMANCE_DIR / "per_cell_metrics.csv")

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(6.5, 5.2))
    sns.heatmap(confusion, annot=True, fmt="d", cmap="Oranges", cbar=False, ax=ax)
    ax.set_title("Decision Layer: target tier vs predicted tier")
    fig.tight_layout()
    fig.savefig(DECISION_PERFORMANCE_DIR / "tier_confusion_matrix.png", dpi=180)
    plt.close(fig)

    plot_rows = pd.DataFrame({"score": scores, "target_tier": target_tiers})
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for tier, colour in zip(labels, ["#4caf50", "#f4b942", "#d9534f"], strict=True):
        values = plot_rows.loc[plot_rows.target_tier == tier, "score"]
        ax.hist(values, bins=np.arange(0, 102, 4), alpha=0.55, label=tier, color=colour)
    ax.axvline(weights_blob["safe_max"], color="#8a6d3b", linestyle="--")
    ax.axvline(weights_blob["blocked_min"], color="#8b1a1a", linestyle="--")
    ax.set(xlabel="Risk score", ylabel="Held-out samples", title="Held-out score distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(DECISION_PERFORMANCE_DIR / "score_distribution.png", dpi=180)
    plt.close(fig)

    ablation_frame = pd.DataFrame(weights_blob["metadata"]["ablation"]).T
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ablation_frame[["roc_auc", "accuracy"]].plot.bar(ax=ax, color=["#d58a52", "#7a4b2a"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Ablation: trained Fusion vs individual branches")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(DECISION_PERFORMANCE_DIR / "ablation.png", dpi=180)
    plt.close(fig)

    table_lines = [
        "| Cell | n | Exact tier | Policy acceptance | Safe | Warning | Blocked |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for cell, row in cell_metrics.iterrows():
        table_lines.append(
            f"| {cell} | {int(row.n)} | {row.exact_tier_accuracy:.4f} | "
            f"{row.acceptance_rate:.4f} | {row.safe_rate:.4f} | "
            f"{row.warning_rate:.4f} | {row.blocked_rate:.4f} |"
        )
    status = "PASSED and deployed" if not gate_failures else "REJECTED; not deployed"
    report = f"""# Risk Decision Layer Performance — {DECISION_VERSION}

Status: **{status}**

The model was trained on 1,260 QRGuard-Mix-v2 rows and evaluated on a fixed,
cell-stratified 540-row holdout. The holdout covers six payload types crossed with
six gallery/live-camera evidence modes (36 cells). Runtime policy is applied during
evaluation, so open Wi-Fi floors and camera-abstention handling are not omitted.

## Main results

- ROC-AUC: {metrics['roc_auc']:.4f}
- Blocked-tier precision: {metrics['blocked_precision']:.4f}
- Safe-tier false-negative rate: {metrics['safe_tier_fnr']:.4f}
- Exact three-tier accuracy: {exact_accuracy:.4f}
- Security-impact policy acceptance: {acceptance_rate:.4f}
- Thresholds: Safe < {weights_blob['safe_max']}; Warning < {weights_blob['blocked_min']}; Blocked >= {weights_blob['blocked_min']}

Exact tier and policy acceptance are both reported. For a dangerous URL, Warning is
counted as cautious (not Safe) but its Blocked recall is gated separately. For benign
content, Warning is reported as an exact-tier miss while only a false Block is treated
as a security-impact failure. Deterministic open-Wi-Fi, executable, and manipulation
cells retain exact-tier gates.

## Per-cell results

{chr(10).join(table_lines)}

## Reproducibility

The deployed weights, model fingerprints, thresholds, branch-cache fingerprints,
and complete metrics are stored beside this report. Generated charts are
`tier_confusion_matrix.png`, `score_distribution.png`, and `ablation.png`.
"""
    (DECISION_PERFORMANCE_DIR / "DECISION_LAYER_PERFORMANCE.md").write_text(
        report, encoding="utf-8"
    )


def main(cache_only: bool) -> None:
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    manifest_path = MIX_DIR / "manifest.csv"
    if not manifest_path.is_file():
        sys.exit("QRGuard-Mix not found. Run: python scripts/build_qrguard_mix.py")
    manifest = pd.read_csv(manifest_path)

    signals = load_cached_signals()
    if signals is not None:
        print(f"Loaded cached branch signals ({len(signals)} rows)")
    else:
        print(f"Scoring {len(manifest)} samples through both branches...")
        signals = compute_signals(manifest)
        signals.to_csv(SIGNALS_PATH, index=False)
        SIGNALS_META_PATH.write_text(json.dumps(model_fingerprint(), indent=2))
        signals = signals.fillna({"rule_flags": ""})
        print(f"Signals cached -> {SIGNALS_PATH}")
    if cache_only:
        return

    required = {
        "risk_target",
        "target_tier",
        "payload_kind",
        "image_source",
        "evidence_mode",
    }
    missing = required - set(signals.columns)
    if missing:
        sys.exit(
            "QRGuard-Mix is the old URL-only version. Rebuild v2 first; missing "
            + ", ".join(sorted(missing))
        )

    X = to_matrix(signals)
    y = signals["dangerous"].to_numpy(dtype=int)
    risk_target = signals["risk_target"].to_numpy(dtype=float)

    idx = np.arange(len(y))
    idx_tr, idx_te = train_test_split(
        idx, test_size=0.30, stratify=signals["cell"], random_state=SEED
    )

    # Fit the requested severity, not only a binary fraud label. In particular,
    # clean open Wi-Fi carries target 0.40 so its learned rule lands in Warning.
    # Class balancing still follows the binary Blocked truth to avoid the many
    # manipulated cells overwhelming ordinary Safe/Warning scans.
    coef, intercept = fit_constrained(
        X[idx_tr],
        risk_target[idx_tr],
        class_labels=y[idx_tr],
    )
    constant_mask = fit_constrained.last_constant_mask
    p_te = _predict_proba(X[idx_te], coef, intercept)

    safe_max, blocked_min = tune_thresholds(
        _predict_proba(X[idx_tr], coef, intercept), y[idx_tr])
    raw_scores_te = np.round(100 * p_te).astype(int)
    held_out = signals.iloc[idx_te].reset_index(drop=True)
    scores_te, tiers = apply_runtime_policy(
        raw_scores_te, held_out, safe_max, blocked_min
    )

    blocked = tiers == "blocked"
    safe = tiers == "safe"
    blocked_prec = float(y[idx_te][blocked].mean()) if blocked.sum() else float("nan")
    safe_fnr = float(y[idx_te][safe].sum() / max(y[idx_te].sum(), 1))

    print("\n=== Held-out evaluation ===")
    print(f"n_train={len(idx_tr)}  n_test={len(idx_te)}")
    print(f"ROC-AUC              : {roc_auc_score(y[idx_te], p_te):.4f}")
    print(
        f"Thresholds           : safe<{safe_max}  "
        f"warning<{blocked_min}  blocked>={blocked_min}"
    )
    print(f"Blocked precision    : {blocked_prec:.4f}   (target >= {TARGET_BLOCKED_PRECISION})")
    print(f"Safe-tier FNR        : {safe_fnr:.4f}   (target <= {TARGET_SAFE_FNR})")

    print("\n=== Tier x truth ===")
    print(pd.crosstab(pd.Series(tiers, name="verdict"),
                      pd.Series(np.where(y[idx_te] == 1, "dangerous", "safe"),
                                name="truth")).to_string())

    target_tiers = held_out["target_tier"].to_numpy()
    print("\n=== Per-cell deployment gates ===")
    per_cell = pd.DataFrame(
        {
            "cell": held_out["cell"].to_numpy(),
            "payload_kind": held_out["payload_kind"].to_numpy(),
            "evidence_mode": held_out["evidence_mode"].to_numpy(),
            "score": scores_te,
            "predicted_tier": tiers,
            "target_tier": target_tiers,
        }
    )
    per_cell["exact_tier"] = per_cell.predicted_tier == per_cell.target_tier

    # Exact tier accuracy is reported, but the deployment gate follows security
    # impact. A dangerous URL that lands in Warning is a cautious miss suitable for
    # Deep Check, not the same failure as returning Safe. Conversely, a benign URL
    # in Warning is less harmful than a false Block. Deterministic cells (open Wi-Fi,
    # manipulated images, executable payloads) still require their exact tier.
    manipulated = per_cell.evidence_mode.isin(
        ["gallery_tampered", "gallery_adversarial", "camera_tampered_consensus"]
    )
    dangerous_url = per_cell.payload_kind == "phishing_url"
    safe_payload = per_cell.target_tier == "safe"
    per_cell["accepted"] = per_cell.exact_tier
    per_cell.loc[dangerous_url & ~manipulated, "accepted"] = (
        per_cell.loc[dangerous_url & ~manipulated, "predicted_tier"] != "safe"
    )
    per_cell.loc[safe_payload, "accepted"] = (
        per_cell.loc[safe_payload, "predicted_tier"] != "blocked"
    )
    per_cell["is_safe"] = per_cell.predicted_tier == "safe"
    per_cell["is_warning"] = per_cell.predicted_tier == "warning"
    per_cell["is_blocked"] = per_cell.predicted_tier == "blocked"
    cell_metrics = (
        per_cell.groupby("cell")
        .agg(
            mean_score=("score", "mean"),
            n=("score", "size"),
            exact_tier_accuracy=("exact_tier", "mean"),
            acceptance_rate=("accepted", "mean"),
            safe_rate=("is_safe", "mean"),
            warning_rate=("is_warning", "mean"),
            blocked_rate=("is_blocked", "mean"),
        )
        .round(4)
    )
    print(cell_metrics.to_string())

    abl = ablation(X, y, idx_tr, idx_te)
    print("\n=== ABLATION (why fusion is needed) ===")
    for name, m in abl.items():
        print(f"  {name:<16} ROC-AUC {m['roc_auc']:.4f}   accuracy {m['accuracy']:.4f}")

    gate_failures = []
    if not np.isfinite(blocked_prec) or blocked_prec < TARGET_BLOCKED_PRECISION:
        gate_failures.append(
            f"Blocked precision {blocked_prec:.4f} < {TARGET_BLOCKED_PRECISION}"
        )
    if safe_fnr > TARGET_SAFE_FNR:
        gate_failures.append(f"Safe-tier FNR {safe_fnr:.4f} > {TARGET_SAFE_FNR}")
    for cell, row in cell_metrics.iterrows():
        if cell.endswith("_phishing_url") and not cell.startswith(
            ("gallery_tampered_", "gallery_adversarial_", "camera_tampered_consensus_")
        ):
            minimum = 0.80
        elif cell.endswith("_wifi_open") and cell.startswith(
            ("gallery_clean_", "camera_clean_consensus_", "camera_uncertain_abstain_")
        ):
            minimum = 0.90
        elif cell.startswith(
            ("gallery_tampered_", "gallery_adversarial_", "camera_tampered_consensus_")
        ) or cell.endswith("_executable_uri"):
            minimum = 0.85
        else:
            minimum = 0.90
        if float(row.acceptance_rate) < minimum:
            gate_failures.append(
                f"{cell} acceptance {row.acceptance_rate:.4f} < {minimum:.2f}"
            )
        if cell.endswith("_phishing_url") and not cell.startswith(
            ("gallery_tampered_", "gallery_adversarial_", "camera_tampered_consensus_")
        ) and float(row.blocked_rate) < 0.65:
            gate_failures.append(
                f"{cell} Blocked recall {row.blocked_rate:.4f} < 0.65"
            )

    weights_blob = {
        "feature_names": list(FEATURE_NAMES),
        "coef": coef.tolist(),
        "intercept": intercept,
        "safe_max": int(safe_max),
        "blocked_min": int(blocked_min),
        "metadata": {
            "version": DECISION_VERSION,
            "trained_on": "QRGuard-Mix-v2",
            "model_fingerprint": model_fingerprint(),
            "n_train": int(len(idx_tr)),
            "n_test": int(len(idx_te)),
            "roc_auc_test": float(roc_auc_score(y[idx_te], p_te)),
            "blocked_precision": blocked_prec,
            "safe_fnr": safe_fnr,
            "per_cell": json.loads(cell_metrics.to_json(orient="index")),
            "per_cell_gate_policy": {
                "dangerous_url": "not-Safe >= 0.80 and Blocked recall >= 0.65",
                "open_wifi_clean_or_abstain": "exact Warning >= 0.90",
                "manipulated_or_executable": "exact Blocked >= 0.85",
                "other_benign": "not-Blocked >= 0.90; exact tier also reported",
            },
            "deployment_gates_passed": not gate_failures,
            "deployment_gate_failures": gate_failures,
            "ablation": abl,
            "class_weight": "balanced",
            "monotonic_risk_constraint": True,
            # Two different reasons a weight can end up at 0 -- keep them apart:
            "zero_unidentifiable": [n for n, k in zip(FEATURE_NAMES, constant_mask) if k],
            "zero_clamped_by_constraint": [
                n for n, c, k in zip(FEATURE_NAMES, coef, constant_mask)
                if abs(c) < 1e-9 and not k
            ],
            "llm_features_trained": False,
            "note": "llm_score/llm_invoked absent from QRGuard-Mix; their weights are "
                    "untrained. Retrain after adding an LLM-labelled subset.",
            "leakage_risk": sorted(
                set(manifest.get("leakage_risk", pd.Series(["unknown"])).astype(str))
            ),
        },
    }
    write_performance_report(
        weights_blob=weights_blob,
        per_cell=per_cell,
        cell_metrics=cell_metrics,
        target_tiers=target_tiers,
        predicted_tiers=tiers,
        scores=scores_te,
        gate_failures=gate_failures,
    )
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_PATH.write_text(json.dumps(weights_blob, indent=2))
    print(f"\nCandidate saved -> {CANDIDATE_PATH}")
    if gate_failures:
        print("Deployment NOT promoted; the current known-good weights are unchanged:")
        for failure in gate_failures:
            print("  -", failure)
        raise SystemExit(2)
    WEIGHTS_PATH.write_text(json.dumps(weights_blob, indent=2))
    print(f"All gates passed; deployed weights -> {WEIGHTS_PATH}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-only", action="store_true",
                    help="compute and cache branch signals, then stop")
    main(ap.parse_args().cache_only)
