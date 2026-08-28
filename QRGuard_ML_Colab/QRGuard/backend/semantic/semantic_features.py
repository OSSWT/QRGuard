"""Deterministic URL representation shared by Semantic training and inference."""

from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from sklearn.feature_extraction.text import HashingVectorizer


FEATURE_CONFIG = {
    "analyzer": "char",
    "ngram_range": (3, 5),
    "n_features": 2**18,
    "alternate_sign": False,
    "norm": "l2",
    "lowercase": True,
}


@lru_cache(maxsize=1)
def _extractor():
    import tldextract

    return tldextract.TLDExtract(suffix_list_urls=())


def registered_domain(host: str) -> str:
    host = host.lower().rstrip(".")
    if not host:
        return ""
    extracted = _extractor()(host)
    return extracted.top_domain_under_public_suffix or host


def enrich_url(raw: str) -> str:
    """Canonicalise the serving surface and append stable structural tokens.

    In particular, scheme-less dataset rows and the router's explicit ``http://``
    form must produce identical n-grams.  The previous contract appended tokens
    from the assumed form but retained the raw surface, causing severe train-serve
    skew on scheme-less benign URLs.
    """
    text = str(raw).strip()[:4096]
    candidate = text if "://" in text else "http://" + text
    try:
        parts = urlsplit(candidate)
        host = (parts.hostname or "").lower().rstrip(".")
        scheme = (parts.scheme or "unknown").lower()
        canonical_host = f"[{host}]" if ":" in host else host
        port = parts.port
        default_port = (scheme == "http" and port == 80) or (
            scheme == "https" and port == 443
        )
        netloc = canonical_host
        if port is not None and not default_port:
            netloc = f"{netloc}:{port}"
        if parts.username:
            userinfo = parts.username
            if parts.password:
                userinfo += f":{parts.password}"
            netloc = f"{userinfo}@{netloc}"
        canonical = urlunsplit((scheme, netloc, parts.path, parts.query, ""))
    except (TypeError, ValueError):
        host, scheme, canonical = "", "invalid", text
    domain = registered_domain(host)
    try:
        ip_literal = bool(host and ipaddress.ip_address(host))
    except ValueError:
        ip_literal = False
    subdomains = max(0, host.count(".") - domain.count(".")) if domain else 0
    length_bin = min(len(canonical) // 25, 20)
    tokens = (
        f" __scheme_{scheme}"
        f" __host_{host or 'missing'}"
        f" __registered_{domain or 'missing'}"
        f" __at_{int('@' in canonical)}"
        f" __ip_{int(ip_literal)}"
        f" __punycode_{int('xn--' in host)}"
        f" __subdomains_{min(subdomains, 8)}"
        f" __length_{length_bin}"
        f" __percent_{int(bool(re.search(r'%[0-9a-fA-F]{{2}}', canonical)))}"
    )
    return canonical.lower() + tokens


def make_vectorizer() -> HashingVectorizer:
    return HashingVectorizer(**FEATURE_CONFIG)
