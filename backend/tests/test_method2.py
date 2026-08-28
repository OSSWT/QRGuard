"""Unit tests for semantic.method2 (Method 2 LLM analyzer).

The LLM is faked via an injected callable — no API key, no network.
"""

import json

from semantic.method2 import (
    SemanticLLMResult, analyze, build_input, load_system_prompt, should_invoke,
)
from semantic.payload_router import route_payload
from semantic.rule_engine import check_url


def fake_llm(response: str):
    return lambda system, user: response


class TestParsing:
    def test_clean_json_phishing(self):
        r = analyze({}, fake_llm(json.dumps({
            "verdict": "phishing", "confidence": 0.92,
            "risk_factors": ["Impersonates Maybank"],
            "explanation": "Fake Maybank site."})))
        assert r.verdict == "phishing" and r.confidence == 0.92
        assert r.risk_factors == ["Impersonates Maybank"]
        assert r.error is None

    def test_benign(self):
        r = analyze({}, fake_llm('{"verdict":"benign","confidence":0.8,'
                                 '"risk_factors":[],"explanation":"Official site."}'))
        assert r.verdict == "benign"

    def test_code_fenced_json(self):
        r = analyze({}, fake_llm('```json\n{"verdict":"suspicious",'
                                 '"confidence":0.5,"explanation":"x"}\n```'))
        assert r.verdict == "suspicious"

    def test_json_with_surrounding_prose(self):
        r = analyze({}, fake_llm('Here is my analysis:\n'
                                 '{"verdict":"phishing","confidence":0.7}\nDone.'))
        assert r.verdict == "phishing" and r.confidence == 0.7

    def test_unparseable_falls_back_to_suspicious(self):
        r = analyze({}, fake_llm("I think this looks dangerous, no JSON here."))
        assert r.verdict == "suspicious"
        assert r.error == "unparseable LLM output"

    def test_invalid_verdict_coerced(self):
        r = analyze({}, fake_llm('{"verdict":"evil","confidence":0.9}'))
        assert r.verdict == "suspicious"

    def test_confidence_clamped(self):
        assert analyze({}, fake_llm('{"verdict":"phishing","confidence":5}')).confidence == 1.0
        assert analyze({}, fake_llm('{"verdict":"benign","confidence":-1}')).confidence == 0.0

    def test_missing_confidence_defaults(self):
        assert analyze({}, fake_llm('{"verdict":"benign"}')).confidence == 0.5

    def test_risk_factors_capped_at_five(self):
        r = analyze({}, fake_llm(json.dumps({
            "verdict": "phishing", "confidence": 0.9,
            "risk_factors": [f"f{i}" for i in range(10)]})))
        assert len(r.risk_factors) == 5

    def test_llm_exception_contained(self):
        def boom(system, user):
            raise RuntimeError("API down")
        r = analyze({}, boom)
        assert r.verdict == "suspicious"
        assert "API down" in (r.error or "")


class TestLLMScoreMapping:
    def test_phishing_maps_to_confidence(self):
        assert SemanticLLMResult("phishing", 0.9).to_llm_score() == 0.9

    def test_benign_maps_to_inverse(self):
        assert abs(SemanticLLMResult("benign", 0.8).to_llm_score() - 0.2) < 1e-9

    def test_suspicious_near_half(self):
        s = SemanticLLMResult("suspicious", 0.0).to_llm_score()
        assert s == 0.5
        assert 0.5 < SemanticLLMResult("suspicious", 1.0).to_llm_score() <= 0.65


class TestTrigger:
    def test_uncertain_band_triggers(self):
        assert should_invoke(0.5, [], is_shortened_or_redirected=False,
                             is_unseen_domain=False)

    def test_confident_benign_no_trigger(self):
        assert not should_invoke(0.05, [], is_shortened_or_redirected=False,
                                 is_unseen_domain=False)

    def test_confident_phishing_no_trigger(self):
        assert not should_invoke(0.98, [], is_shortened_or_redirected=False,
                                 is_unseen_domain=False)

    def test_shortener_triggers_even_when_confident(self):
        assert should_invoke(0.05, [], is_shortened_or_redirected=True,
                             is_unseen_domain=False)

    def test_unseen_domain_triggers(self):
        assert should_invoke(0.9, [], is_shortened_or_redirected=False,
                             is_unseen_domain=True)


class TestBuildInputAndPrompt:
    def test_build_input_shape(self):
        info = route_payload("http://maybank2u-verify.xyz/login")
        flags = check_url(info)
        mi = build_input(info, flags, 0.55,
                         final_url="http://maybank2u-verify.xyz/login",
                         redirect_chain=["https://bit.ly/x",
                                         "http://maybank2u-verify.xyz/login"])
        assert mi["original_url"] == "http://maybank2u-verify.xyz/login"
        assert mi["classifier_score"] == 0.55
        assert "non_https" in mi["rule_flags"]
        assert len(mi["redirect_chain"]) == 2

    def test_build_input_no_redirect_defaults(self):
        info = route_payload("https://example.com/")
        mi = build_input(info, [], 0.1)
        assert mi["redirect_chain"] == []
        assert mi["final_url"] == "https://example.com/"

    def test_system_prompt_loads(self):
        p = load_system_prompt()
        assert "URL security analyst" in p
        assert "verdict" in p

    def test_end_to_end_with_fake_llm(self):
        info = route_payload("https://bit.ly/3xYzAb")
        flags = check_url(info)
        mi = build_input(info, flags, 0.55)
        result = analyze(mi, fake_llm(json.dumps({
            "verdict": "phishing", "confidence": 0.9,
            "risk_factors": ["Shortened link hides destination"],
            "explanation": "This short link hides where it really goes."})))
        assert result.verdict == "phishing"
        assert result.to_llm_score() == 0.9
