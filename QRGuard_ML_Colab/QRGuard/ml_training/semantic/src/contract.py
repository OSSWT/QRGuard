"""Data cleaning, hard examples, and deployment gates for Semantic Training.

RUN 3 has strong aggregate AUC but only 65% accuracy on the small real-world
sanity list. This module makes that failure mode a first-class contract:

* URL conflicts are removed using a canonical scheme/host key, not raw strings.
* Official brand domains receive hard-negative path/query variants.
* A larger, slice-labelled acceptance set is kept separate from aggregate test
  metrics and must pass before ONNX artifacts are copied into the backend.

The URLs are synthetic classification examples. They are never fetched.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.parse import SplitResult, urlsplit, urlunsplit

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AcceptanceCase:
    url: str
    label: int
    slice: str


def canonical_url_key(raw: str) -> str:
    """Canonicalise enough to find duplicate label conflicts without changing paths."""
    text = str(raw).strip()
    candidate = text if "://" in text else "http://" + text
    try:
        parts = urlsplit(candidate)
        host = (parts.hostname or "").lower().rstrip(".")
        if not host:
            return text.casefold()
        port = parts.port
        if port and not (
            (parts.scheme.lower() == "http" and port == 80)
            or (parts.scheme.lower() == "https" and port == 443)
        ):
            host = f"{host}:{port}"
        path = parts.path or "/"
        canonical = SplitResult(parts.scheme.lower() or "http", host, path, parts.query, "")
        return urlunsplit(canonical)
    except (TypeError, ValueError):
        return text.casefold()


def clean_label_conflicts(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Remove empty/malformed labels, cross-source conflicts, and duplicate URLs."""
    required = {"url", "label", "source"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing Semantic Training columns: {sorted(missing)}")

    data = frame[["url", "label", "source"]].copy()
    before = len(data)
    data["url"] = data["url"].astype(str).str.strip()
    data["label"] = pd.to_numeric(data["label"], errors="coerce")
    data = data[data["url"].str.len().between(4, 4096)]
    data = data[data["label"].isin([0, 1])]
    data["label"] = data["label"].astype(int)
    after_shape = len(data)

    data["_url_key"] = data["url"].map(canonical_url_key)
    conflicts = data.groupby("_url_key")["label"].nunique()
    conflict_keys = set(conflicts[conflicts > 1].index)
    conflict_rows = int(data["_url_key"].isin(conflict_keys).sum())
    data = data[~data["_url_key"].isin(conflict_keys)]
    duplicate_rows = int(data.duplicated("_url_key").sum())
    data = data.drop_duplicates("_url_key", keep="first")
    data = data.drop(columns="_url_key").reset_index(drop=True)
    return data, {
        "input_rows": before,
        "invalid_rows": before - after_shape,
        "conflict_keys": len(conflict_keys),
        "conflict_rows": conflict_rows,
        "duplicate_rows": duplicate_rows,
        "output_rows": len(data),
    }


def hard_training_examples() -> pd.DataFrame:
    """Balanced lexical hard cases; call before the registered-domain split."""
    official_domains = [
        "google.com",
        "microsoft.com",
        "apple.com",
        "paypal.com",
        "maybank2u.com.my",
        "cimb.com.my",
        "publicbank.com.my",
        "shopee.com.my",
        "lazada.com.my",
        "wikipedia.org",
        "utar.edu.my",
    ]
    benign_paths = [
        "/",
        "/login",
        "/signin",
        "/account/security",
        "/help/password-reset",
        "/search?q=verify+account",
    ]
    benign = [f"https://www.{domain}{path}" for domain in official_domains for path in benign_paths]

    brands = ["paypal", "maybank2u", "cimb", "shopee", "microsoft", "appleid"]
    traps = [
        "{brand}-secure-check.test/login",
        "account-{brand}.verify-session.test/update",
        "{brand}.com.user-auth.test/confirm",
        "secure.test@{brand}-billing.test/signin",
    ]
    phishing = [f"http://{pattern.format(brand=brand)}" for brand in brands for pattern in traps]
    return pd.DataFrame(
        [
            *(
                {"url": url, "label": 0, "source": "semantic_hard_benign"}
                for url in benign
            ),
            *(
                {"url": url, "label": 1, "source": "semantic_hard_phish"}
                for url in phishing
            ),
        ]
    )


def add_hard_training_examples(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    combined = pd.concat([frame, hard_training_examples()], ignore_index=True)
    return clean_label_conflicts(combined)


def acceptance_cases() -> list[AcceptanceCase]:
    """Fixed behavioural test; these cases must not be inserted as training rows."""
    cases: list[AcceptanceCase] = []

    official = {
        "google.com": ["/maps", "/accounts", "/search?q=secure+login"],
        "paypal.com": ["/", "/signin", "/myaccount/security"],
        "maybank2u.com.my": ["/", "/home/m2u/common/login.do", "/help/reset-password"],
        "microsoft.com": ["/", "/en-my/security", "/account/signin"],
        "apple.com": ["/my/", "/support/apple-id", "/shop/account/home"],
    }
    for domain, paths in official.items():
        cases.extend(
            AcceptanceCase(f"https://www.{domain}{path}", 0, "official_brand_benign")
            for path in paths
        )

    unseen_benign = [
        "https://www.cloudflare.com/learning/security/what-is-phishing/",
        "https://www.amazon.com/gp/help/customer/account-security",
        "https://www.netflix.com/login",
        "https://www.dropbox.com/account/security",
        "https://www.adobe.com/my_en/account.html",
        "https://stripe.com/docs/security",
        "https://www.python.org/accounts/login/",
        "https://docs.github.com/en/authentication",
        "https://www.mozilla.org/en-US/privacy/",
        "https://www.booking.com/signin.html",
    ]
    cases.extend(AcceptanceCase(url, 0, "unseen_benign") for url in unseen_benign)

    lookalikes = [
        "http://paypal-secure-verify.test/login/update.php",
        "http://maybank2u-verify.test/login",
        "http://microsoft-support-alert.test/warning",
        "http://appleid-billing-check.test/confirm",
        "http://shopee-wallet-reward.test/claim",
        "http://cimb-account-unlock.test/session",
        "http://google-drive-share.test/auth",
        "http://netflix-payment-update.test/login",
        "http://amazon-order-refund.test/verify",
        "http://dropbox-document-share.test/signin",
    ]
    cases.extend(AcceptanceCase(url, 1, "brand_lookalike_phish") for url in lookalikes)

    technical = [
        "http://203.0.113.7/account/confirm",
        "http://198.51.100.22:8080/bank/login",
        "http://paypal.com@account-check.test/signin",
        "http://google.com@secure-share.test/auth",
        "http://xn--pypal-4ve.test/login",
        "http://login.bank.security.verify.session.test/update",
        "http://192.0.2.44/reset?account=maybank",
        "http://user:pass@billing-check.test/paypal",
        "http://secure-account.test/%70%61%79%70%61%6c/login",
        "http://verify.test//https://www.apple.com/account",
    ]
    cases.extend(AcceptanceCase(url, 1, "technical_phish") for url in technical)
    return cases


def evaluate_acceptance(
    probabilities: Iterable[float], cases: list[AcceptanceCase] | None = None
) -> dict:
    selected = cases or acceptance_cases()
    probs = np.asarray(list(probabilities), dtype=float)
    if probs.shape != (len(selected),) or not np.isfinite(probs).all():
        raise ValueError(f"expected {len(selected)} finite probabilities")
    labels = np.asarray([case.label for case in selected], dtype=int)
    predictions = (probs >= 0.5).astype(int)

    slices = {}
    for name in sorted({case.slice for case in selected}):
        mask = np.asarray([case.slice == name for case in selected])
        y, p, pred = labels[mask], probs[mask], predictions[mask]
        slices[name] = {
            "n": int(mask.sum()),
            "accuracy": float((pred == y).mean()),
            "false_positive_rate": float((pred[y == 0] == 1).mean()) if (y == 0).any() else None,
            "recall": float((pred[y == 1] == 1).mean()) if (y == 1).any() else None,
            "maximum_benign_score": float(p[y == 0].max()) if (y == 0).any() else None,
            "minimum_phishing_score": float(p[y == 1].min()) if (y == 1).any() else None,
        }

    benign = labels == 0
    phishing = labels == 1
    failures = []
    benign_fpr = float((predictions[benign] == 1).mean())
    phishing_recall = float((predictions[phishing] == 1).mean())
    official_max = slices["official_brand_benign"]["maximum_benign_score"]
    if benign_fpr > 0.05:
        failures.append(f"behavioural benign FPR {benign_fpr:.3f} > 0.05")
    if phishing_recall < 0.90:
        failures.append(f"behavioural phishing recall {phishing_recall:.3f} < 0.90")
    if official_max is not None and official_max > 0.35:
        failures.append(f"official-brand maximum p_url {official_max:.3f} > 0.35")
    return {
        "n": len(selected),
        "benign_false_positive_rate": benign_fpr,
        "phishing_recall": phishing_recall,
        "slices": slices,
        "passed": not failures,
        "failures": failures,
        "cases": [
            {**asdict(case), "p_url": float(probability), "correct": bool(prediction == case.label)}
            for case, probability, prediction in zip(selected, probs, predictions, strict=True)
        ],
    }
