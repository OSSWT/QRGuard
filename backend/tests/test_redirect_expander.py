"""Unit tests for semantic.redirect_expander (Semantic module 4).

All HTTP traffic is mocked with respx; DNS resolution is replaced by a fake
resolver so tests never touch the real network.
"""

import asyncio

import httpx
import pytest
import respx

from semantic import redirect_expander
from semantic.redirect_expander import MAX_HOPS, expand


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """Resolve every test hostname to a public IP unless it contains
    'internal', which resolves to a private address (for the SSRF test)."""

    async def _fake_resolve(host: str) -> list[str]:
        if "internal" in host:
            return ["192.168.1.1"]
        return ["93.184.216.34"]

    monkeypatch.setattr(redirect_expander, "_resolve_host", _fake_resolve)


def run(url: str):
    return asyncio.run(expand(url))


@respx.mock
def test_no_redirect():
    respx.head("https://example.com/page").mock(return_value=httpx.Response(200))
    result = run("https://example.com/page")
    assert result.final_url == "https://example.com/page"
    assert result.chain == ["https://example.com/page"]
    assert result.hops == 0
    assert not (result.blocked or result.timed_out or result.error)


@respx.mock
def test_two_hop_chain():
    respx.head("https://sho.rt/a").mock(
        return_value=httpx.Response(301, headers={"location": "https://mid.example/b"})
    )
    respx.head("https://mid.example/b").mock(
        return_value=httpx.Response(302, headers={"location": "https://final.example/c"})
    )
    respx.head("https://final.example/c").mock(return_value=httpx.Response(200))
    result = run("https://sho.rt/a")
    assert result.final_url == "https://final.example/c"
    assert result.hops == 2
    assert len(result.chain) == 3


@respx.mock
def test_six_hop_chain_stops_at_max():
    for i in range(10):
        respx.head(f"https://hop{i}.example/").mock(
            return_value=httpx.Response(
                301, headers={"location": f"https://hop{i + 1}.example/"}
            )
        )
    result = run("https://hop0.example/")
    assert result.hops == MAX_HOPS
    assert result.final_url == f"https://hop{MAX_HOPS}.example/"
    assert len(result.chain) == MAX_HOPS + 1


@respx.mock
def test_head_405_falls_back_to_get_without_body():
    respx.head("https://strict.example/x").mock(return_value=httpx.Response(405))
    respx.get("https://strict.example/x").mock(
        return_value=httpx.Response(
            302, headers={"location": "https://dest.example/"}
        )
    )
    respx.head("https://dest.example/").mock(return_value=httpx.Response(200))
    result = run("https://strict.example/x")
    assert result.final_url == "https://dest.example/"
    assert result.hops == 1


@respx.mock
def test_redirect_to_private_ip_blocked():
    respx.head("https://sho.rt/a").mock(
        return_value=httpx.Response(
            301, headers={"location": "https://internal.example/admin"}
        )
    )
    result = run("https://sho.rt/a")
    assert result.blocked
    assert "private" in (result.blocked_reason or "")
    assert result.final_url == "https://internal.example/admin"  # recorded, not contacted


def test_direct_private_ip_literal_blocked():
    result = run("http://192.168.1.1/admin")
    assert result.blocked
    assert "private" in (result.blocked_reason or "")


def test_metadata_address_blocked():
    result = run("http://169.254.169.254/latest/meta-data/")
    assert result.blocked
    assert "metadata" in (result.blocked_reason or "")


@respx.mock
def test_redirect_to_non_http_scheme_blocked():
    respx.head("https://sho.rt/f").mock(
        return_value=httpx.Response(301, headers={"location": "file:///etc/passwd"})
    )
    result = run("https://sho.rt/f")
    assert result.blocked
    assert "non-http" in (result.blocked_reason or "")


@respx.mock
def test_network_timeout_reported():
    respx.head("https://slow.example/").mock(
        side_effect=httpx.ReadTimeout("too slow")
    )
    result = run("https://slow.example/")
    assert result.timed_out
    assert result.final_url == "https://slow.example/"


@respx.mock
def test_budget_exhaustion(monkeypatch):
    monkeypatch.setattr(redirect_expander, "TOTAL_BUDGET_S", 0.0)
    respx.head("https://example.com/").mock(return_value=httpx.Response(200))
    result = run("https://example.com/")
    assert result.timed_out


@respx.mock
def test_connection_error_reported_not_raised():
    respx.head("https://down.example/").mock(
        side_effect=httpx.ConnectError("refused")
    )
    result = run("https://down.example/")
    assert result.error is not None
    assert not result.blocked


@respx.mock
def test_relative_location_resolved():
    respx.head("https://example.com/a").mock(
        return_value=httpx.Response(302, headers={"location": "/b"})
    )
    respx.head("https://example.com/b").mock(return_value=httpx.Response(200))
    result = run("https://example.com/a")
    assert result.final_url == "https://example.com/b"
