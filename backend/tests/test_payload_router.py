"""Unit tests for semantic.payload_router (Semantic module 1)."""

from semantic.payload_router import MAX_PAYLOAD_LENGTH, route_payload


class TestPayloadTypeDetection:
    def test_http_url(self):
        info = route_payload("http://example.com/path")
        assert info.payload_type == "url"
        assert info.is_url

    def test_https_url(self):
        info = route_payload("https://example.com")
        assert info.payload_type == "url"

    def test_wifi(self):
        info = route_payload("WIFI:T:WPA;S:MyNetwork;P:secret;;")
        assert info.payload_type == "wifi"
        assert not info.is_url

    def test_vcard(self):
        assert route_payload("BEGIN:VCARD\nFN:Alice\nEND:VCARD").payload_type == "vcard"

    def test_mecard(self):
        assert route_payload("MECARD:N:Alice;;").payload_type == "vcard"

    def test_email(self):
        assert route_payload("mailto:a@example.com").payload_type == "email"

    def test_phone(self):
        assert route_payload("tel:+60123456789").payload_type == "phone"

    def test_sms(self):
        assert route_payload("smsto:+60123456789:hello").payload_type == "sms"

    def test_geo(self):
        assert route_payload("geo:4.33,101.14").payload_type == "geo"

    def test_payment(self):
        assert route_payload("upi://pay?pa=x@bank").payload_type == "payment"

    def test_crc_valid_duitnow_emv_payload(self):
        payload = (
            "00020201021126410014A000000615000101065016640209123456789"
            "520400005303458540510.005802MY5909AUSERNAME6005BANGI63043A23"
        )
        info = route_payload(payload)
        assert info.payload_type == "payment"
        assert not info.is_url

    def test_invalid_duitnow_crc_stays_plain_text(self):
        payload = (
            "00020201021126410014A000000615000101065016640209123456789"
            "520400005303458540510.005802MY5909AUSERNAME6005BANGI63043A24"
        )
        assert route_payload(payload).payload_type == "text"

    def test_plain_text(self):
        info = route_payload("just some text")
        assert info.payload_type == "text"
        assert not info.is_url

    def test_javascript_uri_routed_as_url(self):
        info = route_payload("javascript:alert(1)")
        assert info.payload_type == "url"
        assert info.scheme == "javascript"
        assert info.normalized_url == "javascript:alert(1)"

    def test_data_uri_routed_as_url(self):
        info = route_payload("data:text/html;base64,PGh0bWw+")
        assert info.payload_type == "url"
        assert info.scheme == "data"


class TestSchemelessUrls:
    def test_domain_like_gets_http(self):
        info = route_payload("example.com/login")
        assert info.payload_type == "url"
        assert info.assumed_scheme
        assert info.normalized_url == "http://example.com/login"

    def test_bare_words_are_text(self):
        assert route_payload("hello world").payload_type == "text"

    def test_single_word_is_text(self):
        assert route_payload("hello").payload_type == "text"


class TestNormalization:
    def test_uppercase_scheme_and_host(self):
        info = route_payload("HTTP://EXAMPLE.COM/Path?Q=1")
        assert info.normalized_url == "http://example.com/Path?Q=1"
        assert info.scheme == "http"
        assert info.host == "example.com"

    def test_default_port_removed(self):
        assert route_payload("http://example.com:80/x").normalized_url == (
            "http://example.com/x"
        )
        assert route_payload("https://example.com:443/x").normalized_url == (
            "https://example.com/x"
        )

    def test_nondefault_port_kept(self):
        assert route_payload("http://example.com:8080/x").normalized_url == (
            "http://example.com:8080/x"
        )

    def test_fragment_removed_query_kept(self):
        info = route_payload("https://example.com/p?a=1#frag")
        assert info.normalized_url == "https://example.com/p?a=1"

    def test_registered_domain_and_subdomain(self):
        info = route_payload("https://login.secure.maybank2u.com.my/auth")
        assert info.registered_domain == "maybank2u.com.my"
        assert info.subdomain == "login.secure"

    def test_punycode_host_kept_as_punycode(self):
        info = route_payload("http://xn--pypal-4ve.com/login")
        assert info.host == "xn--pypal-4ve.com"
        assert "xn--" in info.normalized_url

    def test_userinfo_preserved(self):
        info = route_payload("http://user@evil.com/")
        assert "@" in info.normalized_url


class TestRobustness:
    def test_malformed_garbage_never_raises(self):
        for garbage in ["http://", "://///", "\x00\x01", "http://[bad", ""]:
            info = route_payload(garbage)
            assert info.payload_type in ("text", "url")

    def test_none_input(self):
        assert route_payload(None).payload_type == "text"  # type: ignore[arg-type]

    def test_overlong_payload_truncated(self):
        info = route_payload("https://example.com/" + "a" * 6000)
        assert info.truncated
        assert len(info.raw) == MAX_PAYLOAD_LENGTH
