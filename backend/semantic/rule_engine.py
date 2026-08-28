"""Rule Engine — Semantic Analysis module 2.

Deterministic checks on a routed payload. Every check is a fact, not a
prediction, which gives this layer near-100% precision at zero cost. Each
flag carries an ``evidence`` string reused verbatim as a UI reason line.

FLAG_VOCABULARY defines the fixed, ordered list of flag names. The fusion
feature extractor builds fixed-position binary features from this order —
changing the order or removing an entry is a BREAKING CHANGE for any
trained fusion model and requires retraining it.

Shortener / TLD / brand lists are configuration, not code: they load from
an optional JSON file so they can be maintained without code changes.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from semantic.payload_router import PayloadInfo

# ---------------------------------------------------------------------------
# Fixed flag vocabulary — order is part of the fusion contract (see above).
# ---------------------------------------------------------------------------
FLAG_VOCABULARY: list[str] = [
    "js_or_data_uri",
    "ip_literal_host",
    "punycode_host",
    "non_https",
    "shortened_url",
    "suspicious_tld",
    "excessive_subdomains",
    "userinfo_in_url",
    "long_url",
    "brand_in_subdomain",
    "open_wifi_network",
]

LONG_URL_THRESHOLD = 120
MAX_SUBDOMAIN_LABELS = 3

DEFAULT_CONFIG: dict[str, list[str]] = {
    "shorteners": [
        "bit.ly", "tinyurl.com", "t.co", "goo.gl", "s.id", "rebrand.ly",
        "cutt.ly", "is.gd", "buff.ly", "rb.gy", "ow.ly", "shorturl.at",
        "tiny.cc", "bl.ink", "lnkd.in", "t.ly", "v.gd", "qr.ae", "rotf.lol",
        "short.io", "bitly.com", "han.gl", "me2.do", "u.to", "clck.ru",
        "surl.li", "linktr.ee", "s.ee", "kutt.it", "spoo.me",
    ],
    "suspicious_tlds": [
        "xyz", "top", "tk", "ml", "ga", "cf", "gq", "icu", "cam", "rest", "zip",
    ],
    "brands": [
        "maybank", "cimb", "publicbank", "touchngo", "paypal", "google",
        "apple", "microsoft", "shopee", "lazada",
    ],
}


@dataclass
class RuleFlag:
    flag: str
    evidence: str


def load_config(path: str | Path | None = None) -> dict[str, list[str]]:
    """Load list configuration from JSON, falling back to embedded defaults.

    Unknown keys are ignored; missing keys keep their defaults, so a partial
    config file is valid.
    """
    config = {k: list(v) for k, v in DEFAULT_CONFIG.items()}
    if path is not None:
        try:
            loaded = json.loads(Path(path).read_text(encoding="utf-8"))
            for key in config:
                if isinstance(loaded.get(key), list):
                    config[key] = [str(x).lower() for x in loaded[key]]
        except (OSError, json.JSONDecodeError):
            # A broken config must not take the scanner down — defaults win.
            pass
    return config


def check_url(
    info: PayloadInfo, config: dict[str, list[str]] | None = None
) -> list[RuleFlag]:
    """Run every deterministic check applicable to the routed payload.

    Returns flags in FLAG_VOCABULARY order so downstream output is stable.
    """
    cfg = config if config is not None else DEFAULT_CONFIG
    flags: dict[str, RuleFlag] = {}

    if info.payload_type == "wifi":
        _check_wifi(info, flags)
    elif info.is_url:
        _check_url_flags(info, cfg, flags)

    return [flags[name] for name in FLAG_VOCABULARY if name in flags]


# ---------------------------------------------------------------------------
# URL checks
# ---------------------------------------------------------------------------

def _check_url_flags(
    info: PayloadInfo, cfg: dict[str, list[str]], flags: dict[str, RuleFlag]
) -> None:
    url = info.normalized_url or info.raw

    if info.scheme in ("javascript", "data"):
        flags["js_or_data_uri"] = RuleFlag(
            "js_or_data_uri",
            f"Payload uses executable '{info.scheme}:' scheme instead of a web address",
        )
        return  # No host-based checks are meaningful for these schemes.

    host = info.host or ""

    if _is_ip_literal(host):
        flags["ip_literal_host"] = RuleFlag(
            "ip_literal_host", f"Host is a raw IP address ({host})"
        )

    if any(label.startswith("xn--") for label in host.split(".")):
        flags["punycode_host"] = RuleFlag(
            "punycode_host",
            f"Host uses punycode ({host}) — may imitate another domain's look",
        )

    if info.scheme == "http":
        flags["non_https"] = RuleFlag(
            "non_https", "Destination does not use HTTPS encryption"
        )

    registered = (info.registered_domain or "").lower()
    if registered in cfg["shorteners"]:
        flags["shortened_url"] = RuleFlag(
            "shortened_url", f"Link uses URL shortener ({registered})"
        )

    tld = registered.rsplit(".", 1)[-1] if registered else ""
    if tld in cfg["suspicious_tlds"]:
        flags["suspicious_tld"] = RuleFlag(
            "suspicious_tld", f"Domain uses frequently-abused TLD (.{tld})"
        )

    subdomain = info.subdomain or ""
    if subdomain and len(subdomain.split(".")) > MAX_SUBDOMAIN_LABELS:
        flags["excessive_subdomains"] = RuleFlag(
            "excessive_subdomains",
            f"Unusually deep subdomain nesting ({subdomain}.{registered})",
        )

    try:
        netloc = urlsplit(url).netloc
    except ValueError:
        netloc = ""
    if "@" in netloc:
        flags["userinfo_in_url"] = RuleFlag(
            "userinfo_in_url",
            "URL contains '@' before the host — the part before it is a decoy",
        )

    if len(url) > LONG_URL_THRESHOLD:
        flags["long_url"] = RuleFlag(
            "long_url", f"Unusually long URL ({len(url)} characters)"
        )

    _check_brand_mismatch(info, cfg, flags)


def _check_brand_mismatch(
    info: PayloadInfo, cfg: dict[str, list[str]], flags: dict[str, RuleFlag]
) -> None:
    """Brand keyword in subdomain/path but NOT in the registered domain —
    the classic impersonation pattern (login.maybank.evil.xyz/...). This is
    the cheap string-level version; world-knowledge impersonation detection
    is Method 2's job."""
    registered = (info.registered_domain or "").lower()
    subdomain = (info.subdomain or "").lower()
    try:
        path = urlsplit(info.normalized_url or "").path.lower()
    except ValueError:
        path = ""

    for brand in cfg["brands"]:
        if brand in registered:
            continue  # brand present in the real domain — not a mismatch
        if brand in subdomain or brand in path:
            location = "subdomain" if brand in subdomain else "URL path"
            flags["brand_in_subdomain"] = RuleFlag(
                "brand_in_subdomain",
                f"'{brand}' appears in the {location} but the actual domain is "
                f"{registered or 'unknown'}",
            )
            return


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Non-URL payload checks
# ---------------------------------------------------------------------------

_WIFI_SECURITY = re.compile(r"(?:^|;)T:([^;]*)", re.IGNORECASE)


def _check_wifi(info: PayloadInfo, flags: dict[str, RuleFlag]) -> None:
    body = info.raw[len("WIFI:"):] if info.raw.lower().startswith("wifi:") else info.raw
    match = _WIFI_SECURITY.search(body)
    security = (match.group(1).strip().lower() if match else "nopass") or "nopass"
    if security in ("nopass", "wep"):
        label = "no password" if security == "nopass" else "obsolete WEP encryption"
        flags["open_wifi_network"] = RuleFlag(
            "open_wifi_network", f"Wi-Fi network uses {label} — traffic can be intercepted"
        )
