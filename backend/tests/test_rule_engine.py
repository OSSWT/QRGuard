"""Unit tests for semantic.rule_engine (Semantic module 2)."""

import json

from semantic.payload_router import route_payload
from semantic.rule_engine import FLAG_VOCABULARY, check_url, load_config


def flags_of(payload: str) -> list[str]:
    return [f.flag for f in check_url(route_payload(payload))]


class TestIndividualFlags:
    def test_js_uri(self):
        assert flags_of("javascript:alert(1)") == ["js_or_data_uri"]

    def test_data_uri(self):
        assert flags_of("data:text/html;base64,x") == ["js_or_data_uri"]

    def test_https_normal_url_no_flags(self):
        assert flags_of("https://www.google.com/maps") == []

    def test_ip_literal_positive(self):
        assert "ip_literal_host" in flags_of("http://203.0.113.7/login")

    def test_ip_literal_negative(self):
        assert "ip_literal_host" not in flags_of("https://example.com/")

    def test_punycode_positive(self):
        assert "punycode_host" in flags_of("https://xn--pypal-4ve.com/x")

    def test_punycode_negative(self):
        assert "punycode_host" not in flags_of("https://paypal.com/x")

    def test_non_https_positive(self):
        assert "non_https" in flags_of("http://example.com/")

    def test_non_https_negative(self):
        assert "non_https" not in flags_of("https://example.com/")

    def test_shortener_positive(self):
        assert "shortened_url" in flags_of("https://bit.ly/3xYzAb")

    def test_shortener_negative(self):
        assert "shortened_url" not in flags_of("https://example.com/short")

    def test_suspicious_tld_positive(self):
        assert "suspicious_tld" in flags_of("https://promo-site.xyz/")

    def test_suspicious_tld_negative(self):
        assert "suspicious_tld" not in flags_of("https://example.com/")

    def test_excessive_subdomains_positive(self):
        assert "excessive_subdomains" in flags_of("https://a.b.c.d.example.com/")

    def test_excessive_subdomains_negative(self):
        assert "excessive_subdomains" not in flags_of("https://login.example.com/")

    def test_userinfo_positive(self):
        assert "userinfo_in_url" in flags_of("http://paypal.com@evil.com/")

    def test_userinfo_negative(self):
        assert "userinfo_in_url" not in flags_of("https://example.com/a@b")

    def test_long_url_positive(self):
        assert "long_url" in flags_of("https://example.com/" + "a" * 150)

    def test_long_url_negative(self):
        assert "long_url" not in flags_of("https://example.com/short")

    def test_brand_in_subdomain_positive(self):
        assert "brand_in_subdomain" in flags_of("https://maybank.secure-check.xyz/login")

    def test_brand_in_path_positive(self):
        assert "brand_in_subdomain" in flags_of("https://evil.com/paypal/verify")

    def test_brand_in_registered_domain_negative(self):
        # Brand inside the real registered domain is legitimate.
        assert "brand_in_subdomain" not in flags_of("https://www.paypal.com/signin")

    def test_open_wifi_nopass(self):
        assert flags_of("WIFI:T:nopass;S:FreeWifi;;") == ["open_wifi_network"]

    def test_open_wifi_wep(self):
        assert flags_of("WIFI:T:WEP;S:OldNet;P:123;;") == ["open_wifi_network"]

    def test_wpa_wifi_no_flag(self):
        assert flags_of("WIFI:T:WPA;S:HomeNet;P:secret;;") == []


class TestCombinedAndContract:
    def test_combined_shortener_case(self):
        # http + shortener registered under a normal TLD
        found = flags_of("http://bit.ly/x")
        assert "shortened_url" in found and "non_https" in found

    def test_triple_combination(self):
        found = flags_of("http://maybank2u-verify.xyz/login")
        assert "non_https" in found and "suspicious_tld" in found

    def test_flags_returned_in_vocabulary_order(self):
        found = flags_of("http://bit.ly/" + "a" * 150)
        assert found == [f for f in FLAG_VOCABULARY if f in found]

    def test_every_flag_name_in_vocabulary(self):
        for payload in [
            "javascript:alert(1)", "http://203.0.113.7/", "https://bit.ly/x",
            "WIFI:T:nopass;S:x;;", "https://maybank.evil.xyz/" + "a" * 150,
        ]:
            for f in check_url(route_payload(payload)):
                assert f.flag in FLAG_VOCABULARY

    def test_text_payload_returns_no_flags(self):
        assert flags_of("hello world") == []


class TestConfig:
    def test_default_config_when_no_path(self):
        cfg = load_config(None)
        assert "bit.ly" in cfg["shorteners"]

    def test_partial_config_file(self, tmp_path):
        p = tmp_path / "rules.json"
        p.write_text(json.dumps({"shorteners": ["my.short"]}), encoding="utf-8")
        cfg = load_config(p)
        assert cfg["shorteners"] == ["my.short"]
        assert "xyz" in cfg["suspicious_tlds"]  # untouched default

    def test_broken_config_falls_back(self, tmp_path):
        p = tmp_path / "broken.json"
        p.write_text("{not valid json", encoding="utf-8")
        cfg = load_config(p)
        assert "bit.ly" in cfg["shorteners"]

    def test_custom_config_used_by_check(self):
        cfg = load_config(None)
        cfg["shorteners"].append("example.com")
        found = [f.flag for f in check_url(route_payload("https://example.com/x"), cfg)]
        assert "shortened_url" in found
