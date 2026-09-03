"""Train and evaluate the CPU-friendly QRGuard Semantic candidate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "ml_training/.matplotlib_cache"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402, I001
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.optimize import minimize
from semantic.semantic_features import (  # noqa: E402
    FEATURE_CONFIG,
    enrich_url,
    make_vectorizer,
)
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)

from ml_training.semantic.src.contract import (  # noqa: E402
    acceptance_cases,
    add_hard_training_examples,
    canonical_url_key,
    clean_label_conflicts,
    evaluate_acceptance,
)


SEED = 42
VERSION = os.getenv("QRGUARD_SEMANTIC_VERSION", "semantic-2026.02").strip()
if not re.fullmatch(r"semantic-[A-Za-z0-9._-]+", VERSION):
    raise ValueError(
        "QRGUARD_SEMANTIC_VERSION must start with 'semantic-' and contain only "
        "letters, numbers, dots, underscores, or hyphens"
    )
DATA_DIR = ROOT / "data" / "method1"
PROCESSED = ROOT / "ml_training" / "datasets" / "semantic" / "processed" / VERSION
RUN_DIR = ROOT / "ml_training" / "semantic" / "runs" / VERSION
ARTIFACTS = RUN_DIR / "artifacts"
PERFORMANCE = ROOT / "ml_training" / "semantic" / "performance" / VERSION
MAX_TRAIN = 240_000
MAX_VALIDATION = 60_000
MAX_TEST = 80_000
BATCH_SIZE = 20_000
EPOCHS = 4


def _registered_domain(url: str) -> str:
    from urllib.parse import urlsplit

    from semantic.semantic_features import registered_domain

    candidate = str(url) if "://" in str(url) else "http://" + str(url)
    try:
        return registered_domain(
            urlsplit(candidate).hostname or ""
        ) or canonical_url_key(url)
    except (TypeError, ValueError):
        return canonical_url_key(url)


def _split_for_domain(domain: str) -> str:
    value = (
        int.from_bytes(
            hashlib.sha256(f"qrguard-semantic:{SEED}:{domain}".encode()).digest()[:8],
            "big",
        )
        / 2**64
    )
    return "train" if value < 0.70 else "validation" if value < 0.85 else "test"


def _load_data() -> tuple[pd.DataFrame, dict]:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    combined_path = PROCESSED / "combined_clean.parquet"
    report_path = PROCESSED / "cleaning_report.json"
    if combined_path.is_file() and report_path.is_file():
        return pd.read_parquet(combined_path), json.loads(report_path.read_text())

    phi = pd.read_csv(DATA_DIR / "phiusiil.csv", usecols=["url", "label"])
    phi["source"] = "phiusiil"
    malicious = pd.read_csv(DATA_DIR / "malicious_phish.csv", usecols=["url", "type"])
    malicious["label"] = (malicious["type"].str.lower() != "benign").astype(int)
    malicious["source"] = "malicious_urls"
    malicious = malicious[["url", "label", "source"]]

    tranco = pd.read_csv(DATA_DIR / "tranco_top150k.csv", usecols=["rank", "domain"])
    safe_paths = [
        "/",
        "/login",
        "/signin",
        "/account/security",
        "/help/reset-password",
        "/search?q=verify+account",
        "/support/billing",
    ]
    tranco_urls = [
        f"https://{domain}{safe_paths[(int(rank) - 1) % len(safe_paths)]}"
        for rank, domain in tranco.itertuples(index=False)
        if isinstance(domain, str) and "." in domain and " " not in domain
    ]
    tranco_frame = pd.DataFrame({"url": tranco_urls, "label": 0, "source": "tranco"})
    combined, cleaning = add_hard_training_examples(
        pd.concat([phi, malicious, tranco_frame], ignore_index=True)
    )
    acceptance_keys = {canonical_url_key(case.url) for case in acceptance_cases()}
    combined = combined[
        ~combined.url.map(canonical_url_key).isin(acceptance_keys)
    ].reset_index(drop=True)
    cleaning["acceptance_exact_rows_removed"] = int(
        cleaning["output_rows"] - len(combined)
    )
    cleaning["output_rows_after_acceptance_reservation"] = len(combined)
    combined.to_parquet(combined_path, index=False)
    report_path.write_text(json.dumps(cleaning, indent=2), encoding="utf-8")
    return combined, cleaning


def _balanced_sample(frame: pd.DataFrame, maximum: int, seed: int) -> pd.DataFrame:
    if len(frame) <= maximum:
        return frame.sample(frac=1, random_state=seed).reset_index(drop=True)
    per_label = maximum // 2
    parts = []
    selected_indices: set[int] = set()
    for label in (0, 1):
        selected = frame[frame.label == label]
        sampled = selected.sample(
            min(per_label, len(selected)), random_state=seed + label
        )
        parts.append(sampled)
        selected_indices.update(int(index) for index in sampled.index)
    result = pd.concat(parts)
    if len(result) < maximum:
        remaining = frame.drop(index=selected_indices, errors="ignore")
        result = pd.concat(
            [
                result,
                remaining.sample(
                    min(maximum - len(result), len(remaining)), random_state=seed + 10
                ),
            ],
        )
    return result.sample(frac=1, random_state=seed).reset_index(drop=True)


def _build_splits(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    paths = {
        name: PROCESSED / f"{name}.parquet" for name in ("train", "validation", "test")
    }
    if all(path.is_file() for path in paths.values()):
        return {name: pd.read_parquet(path) for name, path in paths.items()}

    data = frame.copy()
    data["domain"] = data.url.map(_registered_domain)
    frozen_test, _ = clean_label_conflicts(
        pd.read_parquet(DATA_DIR / "heldout_test.parquet")
    )
    acceptance_keys = {canonical_url_key(case.url) for case in acceptance_cases()}
    frozen_test = frozen_test[
        ~frozen_test.url.map(canonical_url_key).isin(acceptance_keys)
    ].reset_index(drop=True)
    frozen_test["domain"] = frozen_test.url.map(_registered_domain)
    frozen_test_domains = set(frozen_test.domain)
    data = data[~data.domain.isin(frozen_test_domains)].reset_index(drop=True)
    reserved_domains = {
        _registered_domain(case.url)
        for case in acceptance_cases()
        if case.slice == "unseen_benign"
    }
    data = data[~data.domain.isin(reserved_domains)].reset_index(drop=True)
    hard_domains = set(data[data.source.str.startswith("semantic_hard")].domain)
    data["split"] = data.domain.map(
        lambda domain: (
            "train" if _split_for_domain(domain) in {"train", "test"} else "validation"
        )
    )
    data.loc[data.domain.isin(hard_domains), "split"] = "train"

    groups = {
        "train": set(data.loc[data.split == "train", "domain"]),
        "validation": set(data.loc[data.split == "validation", "domain"]),
        "test": frozen_test_domains,
    }
    assert not groups["train"] & groups["validation"]
    assert not groups["train"] & groups["test"]
    assert not groups["validation"] & groups["test"]

    train = _balanced_sample(data[data.split == "train"], MAX_TRAIN, SEED)
    hard = data[data.source.str.startswith("semantic_hard")]
    missing_hard = hard[~hard.url.isin(set(train.url))]
    if not missing_hard.empty:
        train = pd.concat([train, missing_hard], ignore_index=True)
    splits = {
        "train": train.sample(frac=1, random_state=SEED).reset_index(drop=True),
        "validation": _balanced_sample(
            data[data.split == "validation"], MAX_VALIDATION, SEED + 1
        ),
        "test": _balanced_sample(frozen_test, MAX_TEST, SEED + 2),
    }
    for name, part in splits.items():
        part[["url", "label", "source", "domain"]].to_parquet(paths[name], index=False)
    return splits


def _predict_decision(model, frame: pd.DataFrame, vectorizer) -> np.ndarray:
    results = []
    for start in range(0, len(frame), BATCH_SIZE):
        urls = frame.url.iloc[start : start + BATCH_SIZE]
        features = vectorizer.transform([enrich_url(url) for url in urls])
        results.append(model.decision_function(features))
    return np.concatenate(results)


def _fit_calibration(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    def objective(parameters):
        scale, intercept = parameters
        logits = np.clip(scores * scale + intercept, -50, 50)
        return float(np.mean(np.logaddexp(0, logits) - labels * logits))

    result = minimize(
        objective,
        x0=np.asarray([1.0, 0.0]),
        method="L-BFGS-B",
        bounds=[(0.01, 20.0), (-20.0, 20.0)],
    )
    return float(result.x[0]), float(result.x[1])


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -50, 50)))


def _ece(labels: np.ndarray, probabilities: np.ndarray, bins: int = 15) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    predictions = (probabilities >= 0.5).astype(int)
    confidences = np.maximum(probabilities, 1 - probabilities)
    for lower, upper in zip(edges[:-1], edges[1:], strict=True):
        mask = (confidences >= lower) & (
            (confidences <= upper) if upper == 1.0 else (confidences < upper)
        )
        if mask.any():
            accuracy = (predictions[mask] == labels[mask]).mean()
            total += mask.mean() * abs(accuracy - confidences[mask].mean())
    return float(total)


def _metric_block(labels: np.ndarray, probabilities: np.ndarray) -> dict:
    predictions = (probabilities >= 0.5).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="binary", zero_division=0
    )
    return {
        "n": int(len(labels)),
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "roc_auc": float(roc_auc_score(labels, probabilities))
        if len(np.unique(labels)) > 1
        else None,
        "pr_auc": float(average_precision_score(labels, probabilities))
        if len(np.unique(labels)) > 1
        else None,
        "brier": float(brier_score_loss(labels, probabilities)),
        "ece": _ece(labels, probabilities),
    }


def _write_figures(
    labels: np.ndarray, probabilities: np.ndarray, epoch_loss: list[float]
) -> None:
    PERFORMANCE.mkdir(parents=True, exist_ok=True)
    predictions = (probabilities >= 0.5).astype(int)
    cm = confusion_matrix(labels, predictions)
    plt.figure(figsize=(5.8, 4.8))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=["benign", "dangerous"],
        yticklabels=["benign", "dangerous"],
    )
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("Semantic Training — test confusion matrix")
    plt.tight_layout()
    plt.savefig(PERFORMANCE / "confusion_matrix.png", dpi=180)
    plt.close()

    fpr, tpr, _ = roc_curve(labels, probabilities)
    precision, recall, _ = precision_recall_curve(labels, probabilities)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].plot(fpr, tpr)
    axes[0].plot([0, 1], [0, 1], "--", color="grey")
    axes[0].set(title="ROC", xlabel="False-positive rate", ylabel="True-positive rate")
    axes[1].plot(recall, precision)
    axes[1].set(title="Precision–Recall", xlabel="Recall", ylabel="Precision")
    figure.suptitle("Semantic Training — held-out test curves")
    figure.tight_layout()
    figure.savefig(PERFORMANCE / "roc_pr_curves.png", dpi=180)
    plt.close(figure)

    plt.figure(figsize=(6, 4))
    plt.plot(range(1, len(epoch_loss) + 1), epoch_loss, marker="o")
    plt.xlabel("Epoch")
    plt.ylabel("Validation log loss")
    plt.title("Semantic Training — convergence")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(PERFORMANCE / "training_curves.png", dpi=180)
    plt.close()

    bins = np.linspace(0, 1, 11)
    predicted, observed = [], []
    for lower, upper in zip(bins[:-1], bins[1:], strict=True):
        mask = (probabilities >= lower) & (
            (probabilities <= upper) if upper == 1 else (probabilities < upper)
        )
        if mask.any():
            predicted.append(float(probabilities[mask].mean()))
            observed.append(float(labels[mask].mean()))
    plt.figure(figsize=(5, 5))
    plt.plot([0, 1], [0, 1], "--", color="grey")
    plt.plot(predicted, observed, marker="o")
    plt.xlabel("Mean predicted probability")
    plt.ylabel("Observed dangerous fraction")
    plt.title("Semantic Training — calibration")
    plt.tight_layout()
    plt.savefig(PERFORMANCE / "calibration_curve.png", dpi=180)
    plt.close()


def _write_threshold_analysis(labels: np.ndarray, probabilities: np.ndarray) -> None:
    """Write a complete test sweep without tuning the deployed operating point."""
    rows = []
    for threshold in np.linspace(0.05, 0.95, 37):
        predictions = (probabilities >= threshold).astype(int)
        true_positive = int(((predictions == 1) & (labels == 1)).sum())
        false_positive = int(((predictions == 1) & (labels == 0)).sum())
        true_negative = int(((predictions == 0) & (labels == 0)).sum())
        false_negative = int(((predictions == 0) & (labels == 1)).sum())
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels,
            predictions,
            average="binary",
            zero_division=0,
        )
        rows.append(
            {
                "threshold": float(threshold),
                "is_runtime_reference": bool(abs(threshold - 0.5) < 1e-9),
                "accuracy": float(accuracy_score(labels, predictions)),
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
                "false_positive_rate": false_positive
                / max(false_positive + true_negative, 1),
                "false_negative_rate": false_negative
                / max(false_negative + true_positive, 1),
                "true_positive": true_positive,
                "false_positive": false_positive,
                "true_negative": true_negative,
                "false_negative": false_negative,
            }
        )
    pd.DataFrame(rows).to_csv(PERFORMANCE / "threshold_analysis.csv", index=False)


def report_thresholds_only() -> None:
    """Regenerate the missing threshold table without fitting or changing a model."""
    data, _ = _load_data()
    test = _build_splits(data)["test"]
    from semantic.semantic_service import SemanticAnalyzer

    analyzer = SemanticAnalyzer(ARTIFACTS)
    probabilities = np.asarray(
        [result.p_url for result in analyzer.predict_batch(test.url.tolist())]
    )
    _write_threshold_analysis(test.label.to_numpy(dtype=int), probabilities)
    output = PERFORMANCE / "threshold_analysis.csv"
    print(f"Frozen Semantic threshold report -> {output}")


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    for directory in (PROCESSED, ARTIFACTS, PERFORMANCE):
        directory.mkdir(parents=True, exist_ok=True)
    data, cleaning = _load_data()
    splits = _build_splits(data)
    composition = []
    for split_name, frame in splits.items():
        for (source, label), count in frame.groupby(["source", "label"]).size().items():
            composition.append(
                {
                    "split": split_name,
                    "source": source,
                    "label": int(label),
                    "rows": int(count),
                }
            )
    pd.DataFrame(composition).to_csv(
        PERFORMANCE / "dataset_composition.csv", index=False
    )

    vectorizer = make_vectorizer()
    classifier = SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=1e-6,
        learning_rate="optimal",
        average=True,
        random_state=SEED,
    )
    train = splits["train"]
    counts = train.label.value_counts()
    class_weights = {label: len(train) / (2 * int(counts[label])) for label in (0, 1)}
    validation = splits["validation"]
    validation_labels = validation.label.to_numpy(dtype=int)
    epoch_loss = []
    first_batch = True
    for epoch in range(EPOCHS):
        shuffled = train.sample(frac=1, random_state=SEED + epoch).reset_index(
            drop=True
        )
        for start in range(0, len(shuffled), BATCH_SIZE):
            batch = shuffled.iloc[start : start + BATCH_SIZE]
            features = vectorizer.transform([enrich_url(url) for url in batch.url])
            weights = batch.label.map(class_weights).to_numpy(dtype=float, copy=True)
            weights = weights * np.where(
                batch.source.str.startswith("semantic_hard"), 30.0, 1.0
            )
            classifier.partial_fit(
                features,
                batch.label.to_numpy(dtype=int),
                classes=np.asarray([0, 1]) if first_batch else None,
                sample_weight=weights,
            )
            first_batch = False
        scores = _predict_decision(classifier, validation, vectorizer)
        loss = float(np.mean(np.logaddexp(0, scores) - validation_labels * scores))
        epoch_loss.append(loss)
        print(f"epoch {epoch + 1}/{EPOCHS}: validation log loss={loss:.6f}")

    validation_scores = _predict_decision(classifier, validation, vectorizer)
    scale, intercept = _fit_calibration(validation_scores, validation_labels)
    validation_raw = _sigmoid(validation_scores)
    validation_calibrated = _sigmoid(validation_scores * scale + intercept)

    test = splits["test"]
    test_labels = test.label.to_numpy(dtype=int)
    test_scores = _predict_decision(classifier, test, vectorizer)
    test_probabilities = _sigmoid(test_scores * scale + intercept)
    overall = _metric_block(test_labels, test_probabilities)
    per_source = {}
    per_source_rows = []
    for source in sorted(test.source.unique()):
        mask = (test.source == source).to_numpy()
        block = _metric_block(test_labels[mask], test_probabilities[mask])
        per_source[source] = block
        per_source_rows.append({"source": source, **block})
    pd.DataFrame(per_source_rows).to_csv(
        PERFORMANCE / "per_source_results.csv", index=False
    )

    cases = acceptance_cases()
    acceptance_frame = pd.DataFrame([asdict(case) for case in cases])
    acceptance_features = vectorizer.transform(
        [enrich_url(url) for url in acceptance_frame.url]
    )
    acceptance_scores = classifier.decision_function(acceptance_features)
    acceptance_probabilities = _sigmoid(acceptance_scores * scale + intercept)
    acceptance = evaluate_acceptance(acceptance_probabilities, cases)
    pd.DataFrame(acceptance["cases"]).to_csv(
        PERFORMANCE / "behavioural_acceptance.csv", index=False
    )
    pd.DataFrame([row for row in acceptance["cases"] if row["label"] == 0]).to_csv(
        PERFORMANCE / "hard_benign_results.csv", index=False
    )

    gate_failures = list(acceptance["failures"])
    for source, block in per_source.items():
        if block["roc_auc"] is not None and block["roc_auc"] < 0.90:
            gate_failures.append(f"{source} ROC-AUC {block['roc_auc']:.4f} < 0.9000")
    if overall["ece"] > 0.03:
        gate_failures.append(f"test ECE {overall['ece']:.4f} > 0.0300")

    model_blob = {
        "classifier": classifier,
        "calibration_scale": scale,
        "calibration_intercept": intercept,
        "metadata": {
            "display_name": "Semantic Training",
            "version": VERSION,
            "architecture": "hashed character 3-5 gram averaged SGD logistic classifier",
            "feature_config": {
                **FEATURE_CONFIG,
                "ngram_range": list(FEATURE_CONFIG["ngram_range"]),
            },
            "seed": SEED,
        },
    }
    candidate_path = ARTIFACTS / "semantic_model.joblib"
    joblib.dump(model_blob, candidate_path, compress=3)
    metadata = {
        **model_blob["metadata"],
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "artifact_bytes": candidate_path.stat().st_size,
        "artifact_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "calibration_scale": scale,
        "calibration_intercept": intercept,
        "gates_passed": not gate_failures,
        "gate_failures": gate_failures,
    }
    (ARTIFACTS / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    sys.path.insert(0, str(ROOT / "backend"))
    from semantic.semantic_service import SemanticAnalyzer

    deployed_shape = ARTIFACTS
    analyzer = SemanticAnalyzer(deployed_shape)
    parity_urls = test.url.iloc[:1000].tolist()
    service_probabilities = np.asarray(
        [result.p_url for result in analyzer.predict_batch(parity_urls)]
    )
    direct_probabilities = test_probabilities[: len(parity_urls)]
    parity_max = float(np.max(np.abs(service_probabilities - direct_probabilities)))
    if parity_max > 1e-9:
        gate_failures.append(f"export parity max error {parity_max:.3g} > 1e-9")

    latency_url = "https://www.utar.edu.my/"
    for _ in range(20):
        analyzer.predict(latency_url)
    timings = []
    for _ in range(200):
        started = time.perf_counter()
        analyzer.predict(latency_url)
        timings.append((time.perf_counter() - started) * 1000)
    latency = {
        "median_ms": float(np.median(timings)),
        "p95_ms": float(np.percentile(timings, 95)),
    }
    if latency["p95_ms"] > 150:
        gate_failures.append(f"latency P95 {latency['p95_ms']:.2f} ms > 150 ms")

    metrics = {
        "display_name": "Semantic Training",
        "version": VERSION,
        "architecture": metadata["architecture"],
        "cleaning": cleaning,
        "split_rows": {name: int(len(frame)) for name, frame in splits.items()},
        "overall": overall,
        "classification_report": classification_report(
            test_labels,
            (test_probabilities >= 0.5).astype(int),
            target_names=["benign", "dangerous"],
            output_dict=True,
            zero_division=0,
        ),
        "per_source": per_source,
        "calibration": {
            "scale": scale,
            "intercept": intercept,
            "validation_ece_before": _ece(validation_labels, validation_raw),
            "validation_ece_after": _ece(validation_labels, validation_calibrated),
        },
        "behavioural_acceptance": acceptance,
        "export_parity_max_abs_error": parity_max,
        "latency": latency,
        "gates_passed": not gate_failures,
        "gate_failures": gate_failures,
    }
    (PERFORMANCE / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    with (PERFORMANCE / "metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for name, value in overall.items():
            writer.writerow([name, value])
        writer.writerow(
            ["behavioural_benign_fpr", acceptance["benign_false_positive_rate"]]
        )
        writer.writerow(["behavioural_phishing_recall", acceptance["phishing_recall"]])
        writer.writerow(["export_parity_max_abs_error", parity_max])
        writer.writerow(["latency_p95_ms", latency["p95_ms"]])
    _write_figures(test_labels, test_probabilities, epoch_loss)
    _write_threshold_analysis(test_labels, test_probabilities)

    report = f"""# Semantic Training performance

Architecture: calibrated hashed character 3–5 gram linear classifier
Training rows: {len(train):,}
Validation rows: {len(validation):,}
Independent domain-grouped test rows: {len(test):,}

| Metric | Result |
|---|---:|
| Accuracy | {overall["accuracy"]:.4f} |
| Precision | {overall["precision"]:.4f} |
| Recall | {overall["recall"]:.4f} |
| F1 | {overall["f1"]:.4f} |
| ROC-AUC | {overall["roc_auc"]:.4f} |
| PR-AUC | {overall["pr_auc"]:.4f} |
| ECE | {overall["ece"]:.4f} |
| Behavioural benign FPR | {acceptance["benign_false_positive_rate"]:.4f} |
| Behavioural phishing recall | {acceptance["phishing_recall"]:.4f} |
| Inference P95 | {latency["p95_ms"]:.2f} ms |

Deployment status: **{"PASSED" if not gate_failures else "REJECTED"}**
"""
    if gate_failures:
        report += (
            "\nGate failures:\n"
            + "".join(f"\n- {failure}" for failure in gate_failures)
            + "\n"
        )
        (ARTIFACTS / "DEPLOYMENT_REJECTED.json").write_text(
            json.dumps({"failures": gate_failures}, indent=2), encoding="utf-8"
        )
    else:
        (ARTIFACTS / "deploy_choice.json").write_text(
            json.dumps({"deploy_model": candidate_path.name}, indent=2),
            encoding="utf-8",
        )
    (PERFORMANCE / "SEMANTIC_PERFORMANCE.md").write_text(report, encoding="utf-8")
    print(report)
    if gate_failures:
        raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-thresholds-only",
        action="store_true",
        help="regenerate threshold_analysis.csv from frozen artifacts; do not train",
    )
    options = parser.parse_args()
    if options.report_thresholds_only:
        report_thresholds_only()
    else:
        main()
