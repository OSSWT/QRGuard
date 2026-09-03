"""Payload Router & URL Normalizer — Semantic Analysis module 1.

First stage of the Semantic Analysis branch. Classifies the decoded QR
payload into a type and, for URLs, produces the canonical form that the
active Semantic URL classifier will classify. Normalization matters because the
model is trained on canonical URLs: feeding it a different surface
form at runtime (uppercase host, default port, fragment) would create a
train-serve skew that silently costs accuracy.

Deliberate decision: ``javascript:`` and ``data:`` payloads are routed as
``payload_type="url"`` so the Rule Engine can flag them — sanitizing them
away here would hide them from downstream checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import urlsplit, urlunsplit

import tldextract

from semantic.duitnow_qr import MALAYSIA_AID, parse_duitnow

PayloadType = Literal[
    "url",
    "wifi",
    "vcard",
    "email",
    "phone",
    "sms",
    "geo",
    "payment",
    "attendance",
    "text",
]

# Payloads longer than this are truncated before analysis. QR codes rarely
# exceed ~3 KB of data; anything larger is suspicious in itself but must not
# crash the pipeline.
MAX_PAYLOAD_LENGTH = 4096

# Offline extractor: use the public-suffix snapshot bundled with tldextract
# instead of fetching it over the network at import time (the backend must
# not depend on outbound connectivity to start).
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())

# A scheme-less string is treated as a URL only if it looks like a
# registrable host optionally followed by :port, /path, ?query or #fragment
# (e.g. "example.com/login"). Bare words like "hello world" must not match.
_DOMAIN_LIKE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+"
    r"([:/?#].*)?$",
    re.IGNORECASE,
)

# UTAR's official hi-hive attendance codes carry an opaque signed-looking token
# rather than a URL. Recognising the narrow envelope lets the client hand the user
# to the official app without pretending QRGuard can validate or redeem the token.
# The body is deliberately strict so ordinary text beginning with ``Q01`` is never
# relabelled as attendance data.
_HIHIVE_ATTENDANCE = re.compile(r"^Q01:\*:[A-Za-z0-9+/_-]{32,}={0,2}$")

# Prefix table checked in order. javascript:/data: are intentionally routed
# as "url" (see module docstring).
_PREFIXES: list[tuple[str, PayloadType]] = [
    ("http://", "url"),
    ("https://", "url"),
    ("javascript:", "url"),
    ("data:", "url"),
    ("wifi:", "wifi"),
    ("begin:vcard", "vcard"),
    ("mecard:", "vcard"),
    ("mailto:", "email"),
    ("tel:", "phone"),
    ("smsto:", "sms"),
    ("sms:", "sms"),
    ("geo:", "geo"),
    ("upi://", "payment"),
    ("alipays://", "payment"),
    ("weixin://", "payment"),
    ("duitnow://", "payment"),
]


@dataclass
class PayloadInfo:
    """Routing result consumed by the Rule Engine and Method 1."""

    payload_type: PayloadType
    raw: str
    normalized_url: Optional[str] = None
    host: Optional[str] = None
    registered_domain: Optional[str] = None
    subdomain: Optional[str] = None
    scheme: Optional[str] = None
    is_url: bool = False
    assumed_scheme: bool = False
    truncated: bool = False


def route_payload(payload: str) -> PayloadInfo:
    """Classify a decoded QR payload and normalize it if it is a URL.

    Never raises on malformed input: anything unparseable falls back to
    ``payload_type="text"`` so the pipeline degrades instead of failing.
    """
    if not isinstance(payload, str):
        return PayloadInfo(payload_type="text", raw="", is_url=False)

    raw = payload.strip()
    truncated = False
    if len(raw) > MAX_PAYLOAD_LENGTH:
        raw = raw[:MAX_PAYLOAD_LENGTH]
        truncated = True

    if not raw:
        return PayloadInfo(payload_type="text", raw=raw, truncated=truncated)

    lowered = raw.lower()

    if _HIHIVE_ATTENDANCE.fullmatch(raw):
        return PayloadInfo(payload_type="attendance", raw=raw, truncated=truncated)

    # Merchant-presented DuitNow uses the EMV TLV format rather than a
    # ``duitnow://`` prefix. Recognise it only after CRC, country, currency and
    # AID validation so arbitrary numeric text is never mislabeled as payment.
    if parse_duitnow(raw) is not None:
        return PayloadInfo(payload_type="payment", raw=raw, truncated=truncated)
    if raw.startswith("00") and MALAYSIA_AID in raw:
        # A DuitNow-looking payload with an invalid CRC is data, not a hostname.
        # A later payment-policy layer may warn about it, but it must never be
        # sent to the URL model merely because its digits resemble dotted labels.
        return PayloadInfo(payload_type="text", raw=raw, truncated=truncated)

    payload_type: PayloadType = "text"
    for prefix, ptype in _PREFIXES:
        if lowered.startswith(prefix):
            payload_type = ptype
            break
    else:
        if _DOMAIN_LIKE.match(raw):
            # Scheme-less domain-like string: assume http so it can be
            # analyzed; the assumption itself is recorded for the caller.
            return _route_url("http://" + raw, raw, truncated, assumed=True)

    if payload_type == "url":
        return _route_url(raw, raw, truncated, assumed=False)

    return PayloadInfo(payload_type=payload_type, raw=raw, truncated=truncated)


def _route_url(url: str, raw: str, truncated: bool, assumed: bool) -> PayloadInfo:
    """Normalize a URL payload. Falls back to text on parser failure."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return PayloadInfo(payload_type="text", raw=raw, truncated=truncated)

    scheme = parts.scheme.lower()

    if scheme in ("javascript", "data"):
        # No host to normalize; keep the payload intact as evidence for the
        # Rule Engine ("js_or_data_uri" flag).
        return PayloadInfo(
            payload_type="url",
            raw=raw,
            normalized_url=raw,
            scheme=scheme,
            is_url=True,
            truncated=truncated,
        )

    host = (parts.hostname or "").lower()
    if not host:
        return PayloadInfo(payload_type="text", raw=raw, truncated=truncated)

    # Strip default ports only; a non-default port is a real signal and must
    # survive normalization.
    port = parts.port
    default_port = (scheme == "http" and port == 80) or (
        scheme == "https" and port == 443
    )
    netloc = host if (port is None or default_port) else f"{host}:{port}"
    if parts.username:
        # Preserve userinfo ("user@host" trick) so the Rule Engine can flag
        # it; hidden here would mean invisible downstream.
        userinfo = parts.username + (f":{parts.password}" if parts.password else "")
        netloc = f"{userinfo}@{netloc}"

    # Fragment is dropped (never sent to the server, no security signal for
    # the destination); path and query are kept byte-for-byte — phishing
    # signals live there and percent-decoding them could change semantics.
    normalized = urlunsplit((scheme, netloc, parts.path, parts.query, ""))

    ext = _EXTRACT(host)
    registered = ext.top_domain_under_public_suffix or None
    subdomain = ext.subdomain or None

    return PayloadInfo(
        payload_type="url",
        raw=raw,
        normalized_url=normalized,
        host=host,
        registered_domain=registered,
        subdomain=subdomain,
        scheme=scheme,
        is_url=True,
        assumed_scheme=assumed,
        truncated=truncated,
    )
