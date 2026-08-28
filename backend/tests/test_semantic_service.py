"""Regression and contract tests for the deployed Semantic Training model."""

from __future__ import annotations

import pytest

from semantic.semantic_service import ArtifactsNotFound, SemanticAnalyzer, load_analyzer
from semantic.semantic_features import enrich_url


@pytest.fixture(scope="module")
def analyzer():
    try:
        return load_analyzer()
    except (ArtifactsNotFound, ImportError) as exc:
        pytest.skip(f"Semantic Training artifacts unavailable: {exc}")


class TestLoading:
    def test_loads_approved_joblib(self, analyzer):
        assert analyzer.model_path.name == "semantic_model.joblib"
        assert analyzer.metadata["display_name"] == "Semantic Training"
        assert analyzer.metadata["gates_passed"] is True

    def test_missing_artifacts_raise_clear_error(self, tmp_path):
        with pytest.raises(ArtifactsNotFound):
            SemanticAnalyzer(tmp_path / "does_not_exist")

    def test_load_is_cached(self, analyzer):
        assert load_analyzer() is analyzer


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.utar.edu.my/", 0.030906),
        ("https://www.google.com/maps", 0.009089),
        ("http://paypal-secure-verify.top/login/update.php", 0.988869),
        ("https://login.maybank2u.com.my/", 0.656086),
        ("http://203.0.113.7/account/confirm", 0.996112),
    ],
)
def test_reference_probabilities(analyzer, url, expected):
    assert analyzer.predict(url).p_url == pytest.approx(expected, abs=1e-5)


def test_official_utar_is_benign_and_lookalike_is_dangerous(analyzer):
    benign = analyzer.predict("https://www.utar.edu.my/").p_url
    phish = analyzer.predict("http://utar-login.secure-check.test/verify").p_url
    assert benign < 0.10
    assert phish > 0.90


def test_empty_and_batch_contract(analyzer):
    assert analyzer.predict(" ").p_url == 0.5
    urls = ["https://www.utar.edu.my/", "http://x.test/login/verify"]
    assert [item.p_url for item in analyzer.predict_batch(urls)] == pytest.approx(
        [analyzer.predict(url).p_url for url in urls], abs=1e-12
    )


def test_scheme_assumption_has_train_serve_feature_parity():
    assert enrich_url("example.com/account/login") == enrich_url(
        "http://example.com/account/login"
    )
