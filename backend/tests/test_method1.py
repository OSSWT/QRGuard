"""Tests for semantic.method1 (DomURLs_BERT inference service).

Skipped automatically when the exported artifacts are not on disk, so the suite
still runs on a clean checkout. The reference-value tests act as a regression
guard: if preprocessing, tokenization or calibration ever drift, the scores stop
matching the values the Colab notebook produced.
"""

import pytest

from semantic.method1 import ArtifactsNotFound, Method1Analyzer, load_analyzer

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def analyzer():
    try:
        return load_analyzer()
    except (ArtifactsNotFound, ImportError) as exc:
        pytest.skip(f"Method 1 artifacts unavailable: {exc}")


class TestLoading:
    def test_loads_and_reports_model(self, analyzer):
        assert analyzer.model_path.exists()
        assert analyzer.model_path.suffix == ".onnx"

    def test_run3_temperature_applied(self, analyzer):
        # RUN 3 fitted T = 2.2033; a value of exactly 1.0 would mean calibration
        # was silently skipped.
        assert analyzer.temperature == pytest.approx(2.2033, abs=1e-3)

    def test_missing_artifacts_raise_clear_error(self, tmp_path):
        with pytest.raises(ArtifactsNotFound):
            Method1Analyzer(tmp_path / "does_not_exist")

    def test_load_analyzer_is_cached(self, analyzer):
        assert load_analyzer() is analyzer


class TestReferenceValues:
    """Scores must match the Colab RUN 3 predict_url() demo."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.google.com/maps", 0.014),
            ("http://paypal-secure-verify.top/login/update.php", 0.990),
            ("https://bit.ly/3xYzAb", 0.989),
            ("https://login.maybank2u.com.my/", 0.953),
            ("http://203.0.113.7/account/confirm", 0.992),
        ],
    )
    def test_matches_colab(self, analyzer, url, expected):
        assert analyzer.predict(url).p_url == pytest.approx(expected, abs=0.01)


class TestBehaviour:
    def test_probability_in_range(self, analyzer):
        for url in ["https://example.com", "http://x.tk/login", "nonsense"]:
            assert 0.0 <= analyzer.predict(url).p_url <= 1.0

    def test_obvious_phishing_scores_higher_than_obvious_benign(self, analyzer):
        benign = analyzer.predict("https://www.google.com/maps").p_url
        phish = analyzer.predict("http://paypal-secure-verify.top/login/update.php").p_url
        assert phish > benign + 0.5

    def test_calibrated_differs_from_raw(self, analyzer):
        # Temperature 2.2 must actually change the number.
        r = analyzer.predict("http://paypal-secure-verify.top/login/update.php")
        assert r.p_url != pytest.approx(r.p_uncalibrated, abs=1e-6)

    def test_empty_url_is_neutral(self, analyzer):
        assert analyzer.predict("").p_url == 0.5
        assert analyzer.predict("   ").p_url == 0.5

    def test_deterministic(self, analyzer):
        url = "https://login.maybank2u.com.my/"
        assert analyzer.predict(url).p_url == analyzer.predict(url).p_url

    def test_very_long_url_truncates_without_error(self, analyzer):
        long_url = "https://example.com/" + "a" * 5000
        assert 0.0 <= analyzer.predict(long_url).p_url <= 1.0


class TestBatch:
    def test_batch_matches_single(self, analyzer):
        # Dynamic INT8 quantization recomputes activation scales per run, so a
        # batch of 2 does not produce bit-identical logits to two batches of 1
        # (~0.003 observed). Irrelevant next to the 0.35/0.75 trigger band, but
        # it means batch scores must not be treated as exactly reproducible.
        # Production always uses predict() (batch size 1).
        urls = ["https://www.google.com/maps", "http://x.tk/login/verify"]
        batch = [r.p_url for r in analyzer.predict_batch(urls)]
        single = [analyzer.predict(u).p_url for u in urls]
        assert batch == pytest.approx(single, abs=0.01)

    def test_empty_batch(self, analyzer):
        assert analyzer.predict_batch([]) == []
