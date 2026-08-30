"""Tests for the fusion feature contract and risk engine.

The engine tests build a synthetic weights file rather than depending on the trained
one, so they verify the *mechanics* (contract enforcement, tiering, overrides,
explanations) independently of whatever the current training run produced.
"""

import json

import pytest
from fusion.engine import (
    DEFAULT_BLOCKED_MIN,
    FusionEngine,
    WeightsNotFound,
    load_engine,
)
from fusion.features import (
    ABSENT,
    FEATURE_NAMES,
    N_FEATURES,
    BranchInputs,
    build_feature_vector,
    feature_dict,
)
from semantic.rule_engine import FLAG_VOCABULARY


def write_weights(
    tmp_path, coef=None, intercept=-4.0, safe_max=30, blocked_min=70, feature_names=None
):
    """Synthetic weights: only p_structural and p_url carry signal."""
    if coef is None:
        coef = [0.0] * N_FEATURES
        coef[FEATURE_NAMES.index("p_structural")] = 6.0
        coef[FEATURE_NAMES.index("p_url")] = 6.0
    path = tmp_path / "w.json"
    path.write_text(
        json.dumps(
            {
                "feature_names": list(feature_names or FEATURE_NAMES),
                "coef": coef,
                "intercept": intercept,
                "safe_max": safe_max,
                "blocked_min": blocked_min,
            }
        )
    )
    return path


class TestFeatureContract:
    def test_vector_length_matches_names(self):
        v = build_feature_vector(BranchInputs(0.5, 0.5))
        assert len(v) == N_FEATURES == len(FEATURE_NAMES)

    def test_all_rule_flags_have_a_slot(self):
        for flag in FLAG_VOCABULARY:
            assert f"rule_{flag}" in FEATURE_NAMES

    def test_values_and_present_indicators(self):
        v = feature_dict(
            build_feature_vector(BranchInputs(p_structural=0.9, p_url=0.1))
        )
        assert v["p_structural"] == 0.9 and v["structural_present"] == 1.0
        assert v["p_url"] == 0.1 and v["semantic_present"] == 1.0

    def test_abstained_branch_adds_no_risk(self):
        # An abstaining branch must contribute nothing: with a large positive weight,
        # any placeholder value would manufacture risk from an absent branch.
        v = feature_dict(
            build_feature_vector(BranchInputs(p_structural=None, p_url=0.4))
        )
        assert v["p_structural"] == ABSENT == 0.0
        assert v["structural_present"] == 0.0

    def test_llm_absent_by_default(self):
        v = feature_dict(build_feature_vector(BranchInputs(0.1, 0.1)))
        assert v["llm_score"] == ABSENT and v["llm_invoked"] == 0.0

    def test_llm_present_when_supplied(self):
        v = feature_dict(build_feature_vector(BranchInputs(0.1, 0.1, llm_score=0.9)))
        assert v["llm_score"] == 0.9 and v["llm_invoked"] == 1.0

    def test_rule_flags_set_only_their_own_slots(self):
        v = feature_dict(
            build_feature_vector(
                BranchInputs(0.1, 0.1, rule_flags=["non_https", "shortened_url"])
            )
        )
        assert v["rule_non_https"] == 1.0 and v["rule_shortened_url"] == 1.0
        assert v["rule_ip_literal_host"] == 0.0

    def test_unknown_flag_is_ignored(self):
        v = build_feature_vector(BranchInputs(0.1, 0.1, rule_flags=["not_a_real_flag"]))
        assert len(v) == N_FEATURES


class TestEngineLoading:
    def test_missing_weights_raise(self, tmp_path):
        with pytest.raises(WeightsNotFound):
            FusionEngine(tmp_path / "absent.json")

    def test_contract_mismatch_detected(self, tmp_path):
        # Weights trained on a different feature ordering must be rejected loudly,
        # not silently applied to the wrong columns.
        bad = list(FEATURE_NAMES)[::-1]
        path = write_weights(tmp_path, feature_names=bad)
        with pytest.raises(ValueError, match="feature contract"):
            FusionEngine(path)

    def test_wrong_weight_count_detected(self, tmp_path):
        path = write_weights(tmp_path, coef=[0.1, 0.2])
        with pytest.raises(ValueError):
            FusionEngine(path)


class TestScoring:
    def test_clean_and_benign_is_safe(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(p_structural=0.01, p_url=0.02))
        assert r.verdict == "safe"
        assert r.risk_score < 30

    def test_phishing_url_alone_is_blocked(self, tmp_path):
        # clean image + phishing link: the structural branch sees nothing wrong
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(p_structural=0.02, p_url=0.98))
        assert r.verdict == "blocked"

    def test_tampered_image_alone_is_blocked(self, tmp_path):
        # tampered image + benign-looking link: the semantic branch sees nothing wrong
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(p_structural=0.99, p_url=0.02))
        assert r.verdict == "blocked"

    def test_score_is_bounded(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        for ps, pu in [(0.0, 0.0), (1.0, 1.0), (0.5, 0.5)]:
            assert 0 <= e.predict(BranchInputs(ps, pu)).risk_score <= 100

    def test_tiering_boundaries(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path, safe_max=30, blocked_min=70))
        assert e.tier(29) == "safe"
        assert e.tier(30) == "warning"
        assert e.tier(69) == "warning"
        assert e.tier(70) == "blocked"

    def test_partial_analysis_flagged_when_branch_abstains(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        assert e.predict(BranchInputs(p_structural=None, p_url=0.5)).partial_analysis
        assert not e.predict(BranchInputs(0.1, 0.1)).partial_analysis

    def test_missing_image_does_not_block_a_benign_link(self, tmp_path):
        # Regression: with an abstain placeholder of 0.5 and a large p_structural
        # weight, every image-less scan came back Blocked with the reason
        # "QR image appears manipulated" -- for a scan that had no image at all.
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(p_structural=None, p_url=0.02))
        assert r.verdict == "safe"
        assert r.partial_analysis
        assert not any("image" in reason.lower() for reason in r.reasons)

    def test_missing_payload_does_not_block_a_clean_image(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(p_structural=0.01, p_url=None))
        assert r.verdict == "safe"
        assert r.partial_analysis

    def test_high_confidence_semantic_evidence_blocks_when_image_abstains(
        self, tmp_path
    ):
        e = FusionEngine(write_weights(tmp_path, safe_max=30, blocked_min=70))
        r = e.predict(BranchInputs(p_structural=None, p_url=0.70))
        assert r.verdict == "blocked"
        assert r.risk_score == 70
        assert "semantic_only_high_confidence:policy_floor" in r.overrides

    def test_moderate_semantic_evidence_alone_is_capped_at_warning(self, tmp_path):
        coef = [0.0] * N_FEATURES
        coef[FEATURE_NAMES.index("p_url")] = 10.0
        e = FusionEngine(
            write_weights(
                tmp_path,
                coef=coef,
                intercept=0.0,
                safe_max=30,
                blocked_min=70,
            )
        )
        r = e.predict(BranchInputs(p_structural=None, p_url=0.60))
        assert r.verdict == "warning"
        assert r.risk_score == 69
        assert "semantic_only_moderate:policy_cap" in r.overrides


class TestOverrides:
    def test_blocklist_forces_blocked(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(p_structural=0.01, p_url=0.01), blocklist_hit=True)
        assert r.risk_score == 100 and r.verdict == "blocked"
        assert "blocklist" in r.overrides
        assert any("blocklist" in x.lower() for x in r.reasons)

    def test_executable_payload_forces_blocked(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(0.01, 0.01, rule_flags=["js_or_data_uri"]))
        assert r.verdict == "blocked"
        assert r.risk_score >= DEFAULT_BLOCKED_MIN

    def test_policy_rule_lifts_score_to_warning(self, tmp_path):
        # The learned score may move after retraining, but the product contract is
        # stable: an open network is always at least Warning.
        e = FusionEngine(write_weights(tmp_path, safe_max=38, blocked_min=55))
        r = e.predict(
            BranchInputs(
                p_structural=None, p_url=None, rule_flags=["open_wifi_network"]
            )
        )
        assert r.verdict == "warning"
        assert r.risk_score >= 38
        assert any("policy_floor" in o for o in r.overrides)

    def test_floor_still_applies_when_the_rule_has_a_trained_weight(self, tmp_path):
        coef = [0.0] * N_FEATURES
        coef[FEATURE_NAMES.index("rule_open_wifi_network")] = 0.5  # trained
        e = FusionEngine(
            write_weights(tmp_path, coef=coef, safe_max=38, blocked_min=55)
        )
        r = e.predict(BranchInputs(rule_flags=["open_wifi_network"]))
        assert r.verdict == "warning"
        assert any("policy_floor" in o for o in r.overrides)

    def test_floor_never_lowers_an_already_high_score(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path, safe_max=38, blocked_min=55))
        r = e.predict(
            BranchInputs(
                p_structural=0.99, p_url=0.99, rule_flags=["open_wifi_network"]
            )
        )
        assert r.verdict == "blocked"

    def test_no_override_leaves_score_untouched(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(0.02, 0.02))
        assert r.overrides == []


def test_load_engine_supports_explicit_candidate_environment(monkeypatch, tmp_path):
    candidate = write_weights(tmp_path, safe_max=26, blocked_min=76)
    monkeypatch.setenv("QRGUARD_FUSION_WEIGHTS", str(candidate))
    load_engine.cache_clear()
    try:
        engine = load_engine()
        assert engine.path == candidate
        assert (engine.safe_max, engine.blocked_min) == (26, 76)
    finally:
        load_engine.cache_clear()


class TestExplanations:
    def test_reasons_reflect_the_dominant_signal(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(p_structural=0.02, p_url=0.98))
        assert any("link" in x.lower() for x in r.reasons)

    def test_reasons_capped(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path, coef=[1.0] * N_FEATURES))
        r = e.predict(BranchInputs(0.9, 0.9, rule_flags=list(FLAG_VOCABULARY)))
        assert len(r.reasons) <= 5

    def test_contributions_only_include_risk_raising_features(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(p_structural=0.99, p_url=0.99))
        assert all(v > 0 for v in r.contributions.values())

    def test_safe_scan_has_no_alarming_reasons(self, tmp_path):
        e = FusionEngine(write_weights(tmp_path))
        r = e.predict(BranchInputs(p_structural=0.001, p_url=0.001))
        assert r.reasons == []
