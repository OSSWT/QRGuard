"""Tests for the user-initiated deep check (option E).

The LLM is faked, so these run offline and cost nothing. They verify the wiring:
evidence gathering, re-fusion, and graceful degradation when no provider is
configured or the provider fails.
"""

import asyncio
import json

import pytest

from app.pipeline import run_deep_check
from semantic import llm_providers


def fake_llm(payload: dict):
    """Return an llm_call that always answers with `payload` as JSON."""
    return lambda system, user: json.dumps(payload)


PHISHING_ANSWER = {
    "verdict": "phishing",
    "confidence": 0.95,
    "risk_factors": ["Impersonates Maybank", "No HTTPS"],
    "explanation": "This link pretends to be Maybank but is not owned by the bank.",
}
BENIGN_ANSWER = {
    "verdict": "benign",
    "confidence": 0.9,
    "risk_factors": [],
    "explanation": "This is the official Google Maps site.",
}


def run(**kwargs):
    return asyncio.run(run_deep_check(**kwargs))


class TestEvidenceAndVerdict:
    def test_phishing_url_reported_with_explanation(self):
        r = run(payload="http://maybank2u-verify.xyz/login",
                p_structural=0.02, expand_redirects=False,
                llm_call=fake_llm(PHISHING_ANSWER))
        assert r.llm_verdict == "phishing"
        assert r.llm_confidence == 0.95
        assert "Maybank" in r.explanation
        assert r.risk_factors
        assert r.llm_available is True
        assert r.error is None

    def test_explanation_leads_the_reasons_shown_to_the_user(self):
        r = run(payload="http://maybank2u-verify.xyz/login",
                p_structural=0.02, expand_redirects=False,
                llm_call=fake_llm(PHISHING_ANSWER))
        assert r.reasons[0] == PHISHING_ANSWER["explanation"]

    def test_benign_verdict_does_not_raise_the_score(self):
        r = run(payload="https://www.google.com/maps",
                p_structural=0.01, expand_redirects=False,
                llm_call=fake_llm(BENIGN_ANSWER))
        assert r.llm_verdict == "benign"
        assert r.risk_score <= r.previous_risk_score

    def test_previous_score_is_reported_for_comparison(self):
        r = run(payload="http://maybank2u-verify.xyz/login",
                p_structural=0.02, expand_redirects=False,
                llm_call=fake_llm(PHISHING_ANSWER))
        assert 0 <= r.previous_risk_score <= 100
        assert 0 <= r.risk_score <= 100

    def test_structural_score_is_carried_into_the_refusion(self):
        low = run(payload="https://www.google.com/maps", p_structural=0.01,
                  expand_redirects=False, llm_call=fake_llm(BENIGN_ANSWER))
        high = run(payload="https://www.google.com/maps", p_structural=0.99,
                   expand_redirects=False, llm_call=fake_llm(BENIGN_ANSWER))
        assert high.risk_score > low.risk_score

    def test_latency_reported(self):
        r = run(payload="https://www.google.com/maps", expand_redirects=False,
                llm_call=fake_llm(BENIGN_ANSWER))
        assert r.elapsed_ms >= 0


class TestDegradation:
    def test_no_provider_configured_degrades_cleanly(self, monkeypatch):
        monkeypatch.setattr(llm_providers, "is_configured", lambda: False)
        monkeypatch.setattr(llm_providers, "get_default_call", lambda: None)
        r = run(payload="http://maybank2u-verify.xyz/login", expand_redirects=False)
        assert r.llm_available is False
        assert "GEMINI_API_KEY" in (r.error or "")
        # the verdict still stands on the automatic branches
        assert r.verdict in ("safe", "warning", "blocked")
        assert r.risk_score == r.previous_risk_score

    def test_provider_failure_degrades_to_suspicious(self):
        def boom(system, user):
            raise RuntimeError("Gemini HTTP 429: quota exceeded")

        r = run(payload="http://maybank2u-verify.xyz/login",
                expand_redirects=False, llm_call=boom)
        assert r.llm_verdict == "suspicious"
        assert r.llm_available is False
        assert "429" in (r.error or "")

    def test_malformed_llm_output_degrades_to_suspicious(self):
        r = run(payload="http://maybank2u-verify.xyz/login", expand_redirects=False,
                llm_call=lambda s, u: "I think this looks bad, no JSON here")
        assert r.llm_verdict == "suspicious"
        assert r.error == "unparseable LLM output"

    def test_non_url_payload_is_handled(self):
        r = run(payload="WIFI:T:nopass;S:FreeWifi;;", expand_redirects=False,
                llm_call=fake_llm(BENIGN_ANSWER))
        assert r.verdict in ("safe", "warning", "blocked")


class TestProviderConfig:
    def test_key_is_discovered(self):
        # The repo keeps the key in a gitignored file; skip when absent (CI).
        if not llm_providers.is_configured():
            pytest.skip("no GEMINI_API_KEY configured")
        assert llm_providers.load_api_key()

    def test_default_call_present_only_when_configured(self):
        call = llm_providers.get_default_call()
        assert (call is not None) == llm_providers.is_configured()

    def test_missing_key_raises_a_clear_error(self, monkeypatch):
        monkeypatch.setattr(llm_providers, "load_api_key", lambda: None)
        with pytest.raises(llm_providers.LLMUnavailable, match="GEMINI_API_KEY"):
            llm_providers.gemini_llm_call("sys", "user")
