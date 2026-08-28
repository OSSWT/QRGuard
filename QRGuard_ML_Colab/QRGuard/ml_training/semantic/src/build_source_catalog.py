"""Create a source-labelled inspection catalog for Semantic Training data."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / "ml_training/datasets/semantic/processed/semantic-2026.02/combined_clean.parquet"
OUTPUT = ROOT / "ml_training/datasets/semantic/processed/semantic-2026.02/by_source"

SOURCE_INFO = {
    "phiusiil": (
        "PHIUSIIL_UCI",
        "https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset",
        "UCI labelled phishing/benign source",
    ),
    "malicious_urls": (
        "MALICIOUS_URLS_KAGGLE",
        "https://www.kaggle.com/datasets/sid321axn/malicious-urls-dataset",
        "Kaggle multi-class URL source",
    ),
    "tranco": (
        "TRANCO_BENIGN",
        "https://tranco-list.eu/",
        "research top-site benign augmentation",
    ),
    "semantic_hard_benign": (
        "QRGuard_DERIVED_HARD_BENIGN",
        "local://QRGuard/semantic_hard_benign",
        "QRGuard-derived behavioural hard-benign probes",
    ),
    "semantic_hard_phish": (
        "QRGuard_DERIVED_HARD_PHISH",
        "local://QRGuard/semantic_hard_phish",
        "QRGuard-derived behavioural hard-phishing probes",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    frame = pd.read_parquet(INPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for source, source_frame in frame.groupby("source", sort=True):
        folder, official_url, role = SOURCE_INFO.get(
            source,
            (f"SOURCE_{source.upper()}", f"local://QRGuard/{source}", "unregistered source"),
        )
        target_dir = OUTPUT / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{folder}_semantic_rows.parquet"
        source_frame.to_parquet(target, index=False)
        rows.append(
            {
                "source": source,
                "folder": folder,
                "file": target.relative_to(ROOT).as_posix(),
                "official_url": official_url,
                "role": role,
                "rows": len(source_frame),
                "sha256": _sha256(target),
            }
        )
    pd.DataFrame(rows).sort_values("source").to_csv(
        OUTPUT / "source_catalog_manifest.csv", index=False
    )
    print(f"wrote {len(rows)} source files and {len(frame)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
