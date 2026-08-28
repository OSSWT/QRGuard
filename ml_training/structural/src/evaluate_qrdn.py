"""Evaluate a Structural artifact on QR-DN's identity-disjoint clean holdout."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "ml_training/.matplotlib_cache"))
sys.path.insert(0, str(ROOT / "backend"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from structural.structural_service import StructuralAnalyzer  # noqa: E402


MANIFEST = ROOT / "ml_training/datasets/structural/processed/qrdn/manifest.csv"
DEFAULT_ARTIFACTS = ROOT / "training/artifacts/structural"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--tag", default="deployed_baseline")
    args = parser.parse_args()
    performance = ROOT / "ml_training/structural/performance" / args.tag / "qrdn"
    performance.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(MANIFEST)
    test = manifest[manifest.split == "external_holdout_test"].copy()
    if len(test) != 2250 or test.group_id.nunique() != 25:
        raise ValueError(
            f"expected 2,250 images / 25 test QR identities, got "
            f"{len(test):,} / {test.group_id.nunique()}"
        )
    analyzer = StructuralAnalyzer(args.artifacts)
    rows = []
    started_all = time.perf_counter()
    for index, row in enumerate(test.itertuples(), 1):
        started = time.perf_counter()
        result = analyzer.predict(ROOT / row.path)
        rows.append(
            {
                "path": row.path,
                "group_id": row.group_id,
                "extraction_method": row.extraction_method,
                "p_structural": result.p_structural,
                "predicted_type": result.predicted_type,
                "p_clean": result.probs["clean"],
                "p_adversarial": result.probs["adversarial"],
                "p_tampered": result.probs["tampered"],
                "latency_ms": (time.perf_counter() - started) * 1000,
            }
        )
        if index % 250 == 0:
            print(f"scored {index}/{len(test)}")
    scores = pd.DataFrame(rows)
    scores.to_csv(performance / "predictions.csv", index=False)
    scores[scores.p_structural >= 0.5].sort_values(
        "p_structural", ascending=False
    ).to_csv(performance / "false_positives.csv", index=False)

    def block(frame: pd.DataFrame) -> dict:
        values = frame.p_structural.to_numpy()
        return {
            "n": int(len(frame)),
            "false_positive_rate_at_0_5": float((values >= 0.5).mean()),
            "nonclean_class_rate": float((frame.predicted_type != "clean").mean()),
            "mean_p_structural": float(values.mean()),
            "median_p_structural": float(np.median(values)),
            "p95_p_structural": float(np.percentile(values, 95)),
            "maximum_p_structural": float(values.max()),
        }

    overall = block(scores)
    per_method = {
        method: block(frame)
        for method, frame in scores.groupby("extraction_method")
    }
    latency_values = scores.latency_ms.to_numpy()
    metrics = {
        "display_name": "Structural Training",
        "evaluation": "QR-DN1.0 external clean holdout",
        "artifact": analyzer.model_path.name,
        "artifact_path": str(args.artifacts),
        "independent_qr_identities": int(test.group_id.nunique()),
        "overall": overall,
        "per_extraction_method": per_method,
        "latency": {
            "median_ms": float(np.median(latency_values)),
            "p95_ms": float(np.percentile(latency_values, 95)),
            "wall_seconds": time.perf_counter() - started_all,
        },
        "gate": {
            "target": "external clean FPR <= 0.05",
            "passed": overall["false_positive_rate_at_0_5"] <= 0.05,
        },
        "scope_note": (
            "QR-DN is genuine screen/camera acquisition data but uses watermark "
            "extraction rather than QRGuard's mobile_scanner crop pipeline. It is "
            "external evidence, not a substitute for exact app-crop deployment gates."
        ),
    }
    (performance / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].hist(scores.p_structural, bins=40, color="#d98247", alpha=0.85)
    axes[0].axvline(0.5, color="black", linestyle="--", label="risk threshold")
    axes[0].set(
        title="QR-DN clean score distribution",
        xlabel="p_structural",
        ylabel="Images",
    )
    axes[0].legend()
    method_names = list(per_method)
    axes[1].bar(
        method_names,
        [per_method[name]["false_positive_rate_at_0_5"] for name in method_names],
        color="#d98247",
    )
    axes[1].axhline(0.05, color="black", linestyle="--", label="5% gate")
    axes[1].set(title="False-positive rate by extraction", ylabel="FPR", ylim=(0, 1))
    axes[1].legend()
    figure.suptitle(f"Structural Training — {args.tag} on QR-DN1.0")
    figure.tight_layout()
    figure.savefig(performance / "qrdn_external_clean.png", dpi=180)
    plt.close(figure)

    report = f"""# Structural Training — QR-DN external clean holdout

Artifact: `{analyzer.model_path.name}`
Images: {len(scores):,} across {test.group_id.nunique()} identity-disjoint test QR codes
Real acquisition type: screen/camera capture followed by watermark extraction

| Metric | Result |
|---|---:|
| Clean false-positive rate (`p_structural >= 0.5`) | {overall['false_positive_rate_at_0_5']:.4f} |
| Non-clean predicted-class rate | {overall['nonclean_class_rate']:.4f} |
| Median `p_structural` | {overall['median_p_structural']:.4f} |
| P95 `p_structural` | {overall['p95_p_structural']:.4f} |
| Maximum `p_structural` | {overall['maximum_p_structural']:.4f} |
| Inference P95 | {metrics['latency']['p95_ms']:.2f} ms |

External clean gate: **{'PASSED' if metrics['gate']['passed'] else 'FAILED'}**

This is genuine camera-derived evidence, but it is not an exact QRGuard app crop and
does not replace the strict live-app deployment gate.
"""
    (performance / "QRDN_EXTERNAL_CLEAN.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
