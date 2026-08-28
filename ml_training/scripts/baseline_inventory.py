"""Record the deployed baseline under the canonical Structural/Semantic names."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = ROOT / "ml_training"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_record(directory: Path) -> dict:
    choice = _read_json(directory / "deploy_choice.json")
    model = directory / choice["deploy_model"]
    temperature = _read_json(directory / "temperature.json")
    return {
        "path": str(model.relative_to(ROOT)).replace("\\", "/"),
        "filename": model.name,
        "bytes": model.stat().st_size,
        "sha256": _sha256(model),
        "temperature": temperature["temperature"],
        "calibration": temperature,
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _write_metrics_csv(path: Path, rows: list[tuple[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)


def _bar_chart(path: Path, title: str, rows: list[tuple[str, float]]) -> None:
    width, height = 1000, 120 + 72 * len(rows)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((35, 25), title, fill="#161616", font=font)
    x0, bar_width = 280, 620
    for index, (label, value) in enumerate(rows):
        y = 80 + index * 72
        bounded = max(0.0, min(1.0, float(value)))
        colour = "#2e7d32" if bounded >= 0.9 else "#ef6c00" if bounded >= 0.8 else "#c62828"
        draw.text((35, y + 8), label, fill="#222222", font=font)
        draw.rectangle((x0, y, x0 + bar_width, y + 28), fill="#eeeeee")
        draw.rectangle((x0, y, x0 + int(bar_width * bounded), y + 28), fill=colour)
        draw.text((x0 + bar_width + 15, y + 8), f"{value:.4f}", fill="#222222", font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main() -> None:
    structural_source = ROOT / "training" / "artifacts" / "structural"
    semantic_source = ROOT / "training" / "artifacts" / "method1"
    structural_summary = _read_json(structural_source / "metrics_summary.json")
    semantic_summary = _read_json(semantic_source / "metrics_summary.json")
    fusion = _read_json(ROOT / "backend" / "fusion" / "fusion_weights.json")

    structural_metrics = structural_summary["test_metrics"]
    structural_rows = [
        ("accuracy", structural_metrics["accuracy"]),
        ("macro_f1", structural_metrics["macro avg"]["f1-score"]),
        ("clean_recall", structural_metrics["clean"]["recall"]),
        ("adversarial_recall", structural_metrics["adversarial"]["recall"]),
        ("tampered_recall", structural_metrics["tampered"]["recall"]),
        ("camera_simulated_accuracy", structural_metrics["slices"]["camera_simulated"]["accuracy"]),
    ]
    structural_failures = []
    clean_fpr = structural_metrics["slices"]["clean_photographed_false_positive_rate"]
    if clean_fpr > 0.05:
        structural_failures.append(f"camera clean FPR {clean_fpr:.4f} > 0.0500")
    adversarial_recall = structural_metrics["adversarial"]["recall"]
    if adversarial_recall < 0.80:
        structural_failures.append(f"adversarial recall {adversarial_recall:.4f} < 0.8000")
    if structural_summary["calibration"]["ece_after"] > 0.05:
        structural_failures.append("calibrated ECE exceeds 0.05")

    semantic_overall = semantic_summary["test_metrics"]["overall"]
    sanity = semantic_summary["sanity"]["results"]
    benign = [row for row in sanity if row["label"] == 0]
    phishing = [row for row in sanity if row["label"] == 1]
    behavioural_benign_fpr = sum(row["p_url"] >= 0.5 for row in benign) / len(benign)
    behavioural_phishing_recall = sum(row["p_url"] >= 0.5 for row in phishing) / len(phishing)
    official_max = max(row["p_url"] for row in benign)
    semantic_rows = [
        ("accuracy", semantic_overall["accuracy"]),
        ("f1", semantic_overall["f1"]),
        ("roc_auc", semantic_overall["roc_auc"]),
        ("behavioural_accuracy", semantic_summary["sanity"]["sanity_accuracy"]),
        ("behavioural_phishing_recall", behavioural_phishing_recall),
        ("behavioural_benign_specificity", 1.0 - behavioural_benign_fpr),
    ]
    semantic_failures = []
    if behavioural_benign_fpr > 0.05:
        semantic_failures.append(
            f"behavioural benign FPR {behavioural_benign_fpr:.4f} > 0.0500"
        )
    if behavioural_phishing_recall < 0.90:
        semantic_failures.append(
            f"behavioural phishing recall {behavioural_phishing_recall:.4f} < 0.9000"
        )
    if official_max > 0.35:
        semantic_failures.append(f"official benign max p_url {official_max:.4f} > 0.3500")

    structural_out = ML_ROOT / "structural" / "performance" / "baseline"
    semantic_out = ML_ROOT / "semantic" / "performance" / "baseline"
    decision_out = ML_ROOT / "decision_layer" / "performance" / "baseline"
    _write_json(structural_out / "metrics.json", structural_summary)
    _write_metrics_csv(structural_out / "metrics.csv", structural_rows)
    _bar_chart(structural_out / "performance_overview.png", "Structural baseline", structural_rows)
    _write_json(semantic_out / "metrics.json", semantic_summary)
    _write_metrics_csv(semantic_out / "metrics.csv", semantic_rows)
    _bar_chart(semantic_out / "performance_overview.png", "Semantic baseline", semantic_rows)

    structural_report = f"""# Structural Training baseline performance

Status: **REJECTED as a replacement baseline**. The currently installed model is
retained only for rollback and comparison.

| Metric | Value |
|---|---:|
| Test accuracy | {structural_metrics['accuracy']:.4f} |
| Macro F1 | {structural_metrics['macro avg']['f1-score']:.4f} |
| Camera-simulated accuracy | {structural_metrics['slices']['camera_simulated']['accuracy']:.4f} |
| Camera-simulated clean false-positive rate | {clean_fpr:.4f} |
| Adversarial recall | {adversarial_recall:.4f} |
| Tampered recall | {structural_metrics['tampered']['recall']:.4f} |
| Calibrated ECE | {structural_summary['calibration']['ece_after']:.4f} |
| FP32 latency median / P95 | {structural_summary['latency_ms']['onnx_fp32'][0]:.1f} / {structural_summary['latency_ms']['onnx_fp32'][1]:.1f} ms |

Gate failures:
""" + "".join(f"\n- {failure}" for failure in structural_failures) + "\n"
    (structural_out / "STRUCTURAL_PERFORMANCE.md").write_text(
        structural_report, encoding="utf-8"
    )

    semantic_report = f"""# Semantic Training baseline performance

Status: **REJECTED as a replacement baseline**. Aggregate corpus performance is
high, but the behavioural benign gate fails.

| Metric | Value |
|---|---:|
| Test accuracy | {semantic_overall['accuracy']:.4f} |
| Test F1 | {semantic_overall['f1']:.4f} |
| Test ROC-AUC | {semantic_overall['roc_auc']:.4f} |
| Behavioural accuracy | {semantic_summary['sanity']['sanity_accuracy']:.4f} |
| Behavioural benign FPR | {behavioural_benign_fpr:.4f} |
| Behavioural phishing recall | {behavioural_phishing_recall:.4f} |
| Maximum benign p_url | {official_max:.4f} |
| Calibrated ECE | {semantic_summary['calibration']['ece_after']:.4f} |
| INT8 latency median / P95 | {semantic_summary['latency_ms_median_p95']['onnx_int8'][0]:.1f} / {semantic_summary['latency_ms_median_p95']['onnx_int8'][1]:.1f} ms |

Gate failures:
""" + "".join(f"\n- {failure}" for failure in semantic_failures) + "\n"
    (semantic_out / "SEMANTIC_PERFORMANCE.md").write_text(
        semantic_report, encoding="utf-8"
    )

    fusion_meta = fusion["metadata"]
    decision_failures = []
    if fusion_meta["safe_fnr"] > 0.02:
        decision_failures.append(f"Safe-tier FNR {fusion_meta['safe_fnr']:.4f} > 0.0200")
    if fusion_meta.get("trained_on") != "QRGuard-Mix-v2":
        decision_failures.append("trained on legacy QRGuard-Mix without the v2 payload/camera cells")
    decision_report = {
        "status": "rejected_for_new_deployment",
        "metrics": fusion_meta,
        "gate_failures": decision_failures,
    }
    _write_json(decision_out / "metrics.json", decision_report)
    (decision_out / "DECISION_LAYER_PERFORMANCE.md").write_text(
        "# Risk Decision Layer baseline performance\n\n"
        f"ROC-AUC: {fusion_meta['roc_auc_test']:.4f}  \n"
        f"Blocked precision: {fusion_meta['blocked_precision']:.4f}  \n"
        f"Safe-tier FNR: {fusion_meta['safe_fnr']:.4f}\n\n"
        "Gate failures:\n" + "".join(f"\n- {failure}" for failure in decision_failures) + "\n",
        encoding="utf-8",
    )

    registry_path = ML_ROOT / "deployment" / "model_registry.json"
    registry = _read_json(registry_path)
    registry.update(
        {
            "status": "baseline_recorded_candidates_pending",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "deployed": {
                "structural": {
                    "display_name": "Structural Training baseline",
                    "artifact": _artifact_record(structural_source),
                    "gates_passed": False,
                    "gate_failures": structural_failures,
                },
                "semantic": {
                    "display_name": "Semantic Training baseline",
                    "legacy_internal_name": "Method 1 RUN 3",
                    "artifact": _artifact_record(semantic_source),
                    "gates_passed": False,
                    "gate_failures": semantic_failures,
                },
                "decision_layer": {
                    "display_name": "Risk Decision Layer baseline",
                    "path": "backend/fusion/fusion_weights.json",
                    "sha256": _sha256(ROOT / "backend" / "fusion" / "fusion_weights.json"),
                    "gates_passed": False,
                    "gate_failures": decision_failures,
                },
            },
        }
    )
    _write_json(registry_path, registry)
    print("Baseline inventory and performance reports written.")


if __name__ == "__main__":
    main()
