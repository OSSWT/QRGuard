"""Acquire and freeze the Semantic datasets used by the Colab pipeline.

The script standardises PhiUSIIL, the Kaggle Malicious URLs corpus and a dated
Tranco snapshot, then reserves a registrable-domain-disjoint held-out test set.
It writes provenance, row counts and SHA-256 hashes beside the data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import tldextract


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "data/method1"
EXTRACT = tldextract.TLDExtract(suffix_list_urls=())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_column(frame: pd.DataFrame, names: set[str]) -> str:
    for column in frame.columns:
        if str(column).lower().strip() in names:
            return str(column)
    raise ValueError(
        f"required column {sorted(names)} not found in {list(frame.columns)}"
    )


def _phiusiil() -> pd.DataFrame:
    from ucimlrepo import fetch_ucirepo

    dataset = fetch_ucirepo(id=967)
    raw = pd.concat([dataset.data.features, dataset.data.targets], axis=1)
    url_column = _find_column(raw, {"url"})
    label_column = _find_column(raw, {"label"})
    majority = raw[label_column].value_counts().idxmax()
    return pd.DataFrame(
        {
            "url": raw[url_column].astype(str),
            "label": (raw[label_column] != majority).astype(int),
        }
    )


def _malicious_urls(override: Path | None) -> pd.DataFrame:
    if override is None:
        import kagglehub

        directory = Path(kagglehub.dataset_download("sid321axn/malicious-urls-dataset"))
        candidates = sorted(directory.rglob("*.csv"))
        if not candidates:
            raise FileNotFoundError(f"no CSV found in Kaggle download {directory}")
        source = candidates[0]
    else:
        source = override
    raw = pd.read_csv(source)
    url_column = _find_column(raw, {"url"})
    type_column = _find_column(raw, {"type", "label"})
    values = raw[type_column].astype(str).str.lower().str.strip()
    if set(values.unique()).issubset({"0", "1"}):
        labels = values.astype(int)
    else:
        labels = (values != "benign").astype(int)
    normalised_type = pd.Series(
        ["benign" if label == 0 else "malicious" for label in labels],
        index=raw.index,
    )
    return pd.DataFrame(
        {
            "url": raw[url_column].astype(str),
            "type": normalised_type,
            "label": labels,
        }
    )


def _tranco(override: Path | None, count: int) -> tuple[pd.DataFrame, str]:
    if override is not None:
        raw = pd.read_csv(override, header=None)
        domains = raw.iloc[:, -1].astype(str).tolist()[:count]
        identity = override.name
    else:
        from tranco import Tranco

        current = Tranco(cache=True, cache_dir=str(ROOT / ".tranco_cache")).list()
        domains = current.top(count)
        identity = str(getattr(current, "list_id", "current"))
    clean = [domain.strip().lower() for domain in domains]
    clean = [domain for domain in clean if "." in domain and " " not in domain]
    return (
        pd.DataFrame(
            {
                "rank": range(1, len(clean) + 1),
                "domain": clean,
            }
        ),
        identity,
    )


def _domain(value: str) -> str:
    host = (
        str(value).split("/", 1)[0]
        if "://" not in str(value)
        else str(value).split("/", 3)[2]
    )
    host = host.split("@")[-1].split(":")[0].strip(".[]").lower()
    result = EXTRACT(host)
    return (
        result.top_domain_under_public_suffix
        or host
        or hashlib.sha256(str(value).encode()).hexdigest()
    )


def _heldout(
    phi: pd.DataFrame, malicious: pd.DataFrame, tranco: pd.DataFrame
) -> pd.DataFrame:
    frames = [
        phi.assign(source="phiusiil"),
        malicious[["url", "label"]].assign(source="malicious_phish"),
        pd.DataFrame(
            {
                "url": "https://" + tranco.domain.astype(str) + "/",
                "label": 0,
                "source": "tranco",
            }
        ),
    ]
    combined = pd.concat(frames, ignore_index=True)
    combined["domain"] = combined.url.map(_domain)
    fractions = combined.domain.map(
        lambda domain: (
            int.from_bytes(
                hashlib.sha256(f"qrguard-semantic:42:{domain}".encode()).digest()[:8],
                "big",
            )
            / 2**64
        )
    )
    heldout = combined[fractions >= 0.85].drop_duplicates("url")
    parts = [
        group.sample(min(40_000, len(group)), random_state=42 + int(label))
        for label, group in heldout.groupby("label")
    ]
    result = pd.concat(parts, ignore_index=True).sample(frac=1, random_state=44)
    return result[["url", "label", "source", "domain"]].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--malicious-csv", type=Path)
    parser.add_argument("--tranco-csv", type=Path)
    parser.add_argument("--tranco-count", type=int, default=150_000)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    expected = (
        output / "phiusiil.csv",
        output / "malicious_phish.csv",
        output / "tranco_top150k.csv",
        output / "heldout_test.parquet",
    )
    if all(path.is_file() for path in expected) and not args.force:
        print(f"Semantic data already prepared at {output}; use --force to refresh")
        return

    phi = _phiusiil()
    malicious = _malicious_urls(args.malicious_csv)
    tranco, tranco_identity = _tranco(args.tranco_csv, args.tranco_count)
    phi.to_csv(expected[0], index=False)
    malicious[["url", "type"]].to_csv(expected[1], index=False)
    tranco.to_csv(expected[2], index=False)
    heldout = _heldout(phi, malicious, tranco)
    heldout.to_parquet(expected[3], index=False)
    report = {
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "phiusiil": {
                "official_id": "UCI 967",
                "rows": len(phi),
                "path": expected[0].name,
                "sha256": _sha256(expected[0]),
            },
            "malicious_urls": {
                "official_id": "kaggle/sid321axn/malicious-urls-dataset",
                "rows": len(malicious),
                "path": expected[1].name,
                "sha256": _sha256(expected[1]),
            },
            "tranco": {
                "list_id": tranco_identity,
                "rows": len(tranco),
                "path": expected[2].name,
                "sha256": _sha256(expected[2]),
            },
        },
        "heldout": {
            "rows": len(heldout),
            "domains": int(heldout.domain.nunique()),
            "path": expected[3].name,
            "sha256": _sha256(expected[3]),
        },
    }
    (output / "provenance.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
