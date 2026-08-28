"""Tests for semantic.domain_reputation (the "domain reliability" fusion signal)."""

import pytest

from semantic.domain_reputation import domain_unknown, is_well_known, list_size
from semantic.payload_router import route_payload


class TestList:
    def test_list_loaded(self):
        assert list_size() > 100_000, "well-known domain list missing or truncated"


class TestWellKnown:
    @pytest.mark.parametrize("domain", ["google.com", "youtube.com", "cloudflare.com"])
    def test_famous_domains_recognised(self, domain):
        assert is_well_known(domain)

    def test_case_and_whitespace_insensitive(self):
        assert is_well_known("  GOOGLE.COM  ")

    @pytest.mark.parametrize(
        "domain",
        ["maybank2u-verify.xyz", "paypal-secure-verify.top", "definitely-not-real-9z8x.tk"],
    )
    def test_lookalike_domains_not_recognised(self, domain):
        assert not is_well_known(domain)

    def test_empty_and_none(self):
        assert not is_well_known(None)
        assert not is_well_known("")


class TestFeatureValue:
    def test_famous_domain_adds_no_risk(self):
        assert domain_unknown("google.com") == 0.0

    def test_unknown_domain_is_a_risk_signal(self):
        assert domain_unknown("maybank2u-verify.xyz") == 1.0

    def test_missing_domain_counts_as_unknown(self):
        assert domain_unknown(None) == 1.0

    def test_works_end_to_end_with_router(self):
        famous = route_payload("https://www.google.com/maps")
        fake = route_payload("http://maybank2u-verify.xyz/login")
        assert domain_unknown(famous.registered_domain) == 0.0
        assert domain_unknown(fake.registered_domain) == 1.0

    def test_subdomain_of_famous_site_still_famous(self):
        # reliability is judged on the REGISTERED domain, not the full host
        info = route_payload("https://mail.google.com/inbox")
        assert domain_unknown(info.registered_domain) == 0.0
