"""Redirect Expansion Service — Semantic Analysis module 4.

Safely resolves the redirect chain of a URL (typically a shortened link) so
Method 2 can reason over the real destination. This is the only Semantic
module that touches the network, and it follows untrusted links — so every
safety rule here is a hard requirement, not an optimisation:

- HEAD-only requests; bodies are never read (we observe WHERE a link goes,
  never download WHAT is there).
- Every hop's host is resolved and classified BEFORE it is contacted; hops
  into loopback/private/link-local space (incl. the 169.254.169.254 cloud
  metadata address) are refused — otherwise a malicious QR could use this
  backend as a proxy into internal networks (SSRF).
- Hard budget: at most 5 hops within 3 seconds total; on exhaustion the
  chain collected so far is returned with ``timed_out=True``. An
  unexpandable shortener is itself a risk signal downstream, so partial
  results are still useful.

Network failures never raise to the caller — they come back in ``error``.
"""

from __future__ import annotations

import asyncio
import ipaddress
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlsplit

import httpx

MAX_HOPS = 5
TOTAL_BUDGET_S = 3.0
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"
)


@dataclass
class ExpansionResult:
    final_url: str
    chain: list[str] = field(default_factory=list)
    hops: int = 0
    timed_out: bool = False
    blocked: bool = False
    blocked_reason: Optional[str] = None
    error: Optional[str] = None


async def expand(url: str) -> ExpansionResult:
    """Follow the redirect chain of ``url`` under the safety rules above."""
    chain = [url]
    current = url
    hops = 0
    deadline = time.monotonic() + TOTAL_BUDGET_S

    async with httpx.AsyncClient(
        follow_redirects=False,  # every hop is inspected before it is followed
        headers={"User-Agent": USER_AGENT},
        cookies=None,
    ) as client:
        while True:
            reason = await _refusal_reason(current)
            if reason is not None:
                return ExpansionResult(
                    final_url=current, chain=chain, hops=hops,
                    blocked=True, blocked_reason=reason,
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return ExpansionResult(
                    final_url=current, chain=chain, hops=hops, timed_out=True
                )

            try:
                status, headers = await _probe(client, current, remaining)
            except httpx.TimeoutException:
                return ExpansionResult(
                    final_url=current, chain=chain, hops=hops, timed_out=True
                )
            except httpx.HTTPError as exc:
                return ExpansionResult(
                    final_url=current, chain=chain, hops=hops,
                    error=f"{type(exc).__name__}: {exc}",
                )

            location = headers.get("location")
            if 300 <= status < 400 and location:
                current = urljoin(current, location)
                hops += 1
                chain.append(current)
                if hops >= MAX_HOPS:
                    # Stop without contacting the final target; 5+ hops is
                    # already an unusual chain worth reporting as-is.
                    return ExpansionResult(final_url=current, chain=chain, hops=hops)
                continue

            # Non-redirect response (2xx/4xx/5xx, or 3xx without Location):
            # this is the destination. Bodies are never read — even for the
            # HTML pages some shorteners serve (meta-refresh), we stop here.
            return ExpansionResult(final_url=current, chain=chain, hops=hops)


async def _probe(
    client: httpx.AsyncClient, url: str, timeout: float
) -> tuple[int, httpx.Headers]:
    """HEAD the URL; on 405/501 fall back to GET without reading the body."""
    resp = await client.head(url, timeout=timeout)
    if resp.status_code not in (405, 501):
        return resp.status_code, resp.headers
    async with client.stream("GET", url, timeout=timeout) as resp2:
        # Leaving the ``stream`` context closes the connection with the body
        # unread — the fallback still never downloads content.
        return resp2.status_code, resp2.headers


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------

async def _refusal_reason(url: str) -> Optional[str]:
    """Return why this URL must not be contacted, or None if it is safe."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "unparseable URL"

    if parts.scheme not in ("http", "https"):
        return f"redirect to non-http scheme '{parts.scheme}:'"

    host = parts.hostname
    if not host:
        return "missing host"

    try:
        addresses = [str(ipaddress.ip_address(host.strip("[]")))]
    except ValueError:
        try:
            addresses = await _resolve_host(host)
        except OSError:
            # Unresolvable hosts cannot be contacted anyway; let the request
            # attempt surface the error rather than mislabelling it blocked.
            return None

    for addr in addresses:
        label = _forbidden_address_label(addr)
        if label is not None:
            return f"host resolves to {label} ({addr})"
    return None


async def _resolve_host(host: str) -> list[str]:
    """DNS-resolve ``host`` to every address it may connect to.

    Kept as a module-level function so tests can substitute a fake resolver
    (unit tests must not depend on real DNS).
    """
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None)
    return sorted({info[4][0] for info in infos})


def _forbidden_address_label(address: str) -> Optional[str]:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return "unparseable address"
    if str(ip) == "169.254.169.254":
        return "cloud metadata address"
    if ip.is_loopback:
        return "loopback address"
    if ip.is_private:
        return "private network address"
    if ip.is_link_local:
        return "link-local address"
    return None
