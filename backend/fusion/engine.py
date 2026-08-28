"""Fusion Risk Engine — combines both branches into one verdict.

Four stages, in order:

  1. Calibration   -- already applied inside each branch (temperature scaling), so the
                      probabilities arriving here are directly comparable.
  2. Stacking      -- a trained logistic regression over the fixed feature vector
                      produces p_fraud. Logistic weights are linear, so each feature's
                      contribution to the score can be read off directly and turned
                      into a user-facing reason.
  3. Override rules-- safety net applied AFTER the score (blocklist hits, executable
                      payload schemes). Rules can only raise risk, never lower it.
  4. Decision      -- risk_score = round(100 * p_fraud), then
                      Safe < SAFE_MAX <= Warning < BLOCKED_MIN <= Blocked.

Why not a fixed weighted average (FYP1's OR rule / a 0.5/0.5 blend): a linear model
learned from labelled data can express "two weak signals together mean fraud", gives a
graded score the Warning tier needs, and does not inflate false positives as branches
are added.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from fusion.features import FEATURE_NAMES, N_FEATURES, BranchInputs, build_feature_vector

_DEFAULT_WEIGHTS = Path(__file__).resolve().parent / "fusion_weights.json"

# Defaults; the trained weights file overrides these with tuned values.
DEFAULT_SAFE_MAX = 30
DEFAULT_BLOCKED_MIN = 70

# Human-readable reason text per feature. Keys match FEATURE_NAMES entries.
REASON_TEXT = {
    "p_structural": "QR image appears manipulated",
    "p_url": "Destination link matches phishing patterns",
    "llm_score": "Deep link analysis flagged this destination",
    "domain_unknown": "Destination is not a widely-recognised website",
    "rule_js_or_data_uri": "Payload contains executable content",
    "rule_ip_literal_host": "Link points to a raw IP address",
    "rule_punycode_host": "Domain uses look-alike characters",
    "rule_non_https": "Destination does not use HTTPS",
    "rule_shortened_url": "Shortened link hides the real destination",
    "rule_suspicious_tld": "Domain uses a frequently-abused extension",
    "rule_excessive_subdomains": "Unusually deep subdomain nesting",
    "rule_userinfo_in_url": "Link uses the '@' trick to disguise its host",
    "rule_long_url": "Unusually long link",
    "rule_brand_in_subdomain": "Link imitates a known brand",
    "rule_open_wifi_network": "Wi-Fi network is unencrypted",
}

# Rules that force Blocked regardless of the model score. These encode facts, not
# predictions, so overriding a probabilistic score is justified.
HARD_OVERRIDE_FLAGS = ("js_or_data_uri",)

# Deterministic caution policies stay separate from the learned score. These facts
# must produce at least Warning even when their learned contribution lands just below
# a newly tuned threshold. Keeping the floor after scoring prevents the exact bug in
# which an open Wi-Fi QR was detected and explained but still displayed as Safe.
RULE_TIER_FLOORS = {
    "open_wifi_network": "warning",
    "userinfo_in_url": "warning",
}


class WeightsNotFound(FileNotFoundError):
    """Raised when the trained fusion weights are missing."""


@dataclass(frozen=True)
class FusionResult:
    risk_score: int                     # 0-100
    verdict: str                        # "safe" | "warning" | "blocked"
    p_fraud: float
    reasons: list[str] = field(default_factory=list)
    contributions: dict[str, float] = field(default_factory=dict)
    overrides: list[str] = field(default_factory=list)
    partial_analysis: bool = False      # a branch abstained


class FusionEngine:
    """Trained meta-classifier plus override rules and the tiering policy."""

    def __init__(self, weights_path: Path | str | None = None) -> None:
        path = Path(weights_path or _DEFAULT_WEIGHTS)
        if not path.is_file():
            raise WeightsNotFound(
                f"Fusion weights not found: {path}\n"
                "Train them with: python scripts/train_fusion.py"
            )
        blob = json.loads(path.read_text())

        names = blob.get("feature_names")
        if names and list(names) != list(FEATURE_NAMES):
            raise ValueError(
                "Fusion weights were trained on a different feature contract.\n"
                f"  trained on: {names}\n  current   : {list(FEATURE_NAMES)}\n"
                "Retrain with scripts/train_fusion.py."
            )

        self.coef = np.asarray(blob["coef"], dtype=np.float64)
        self.intercept = float(blob["intercept"])
        if self.coef.shape != (N_FEATURES,):
            raise ValueError(f"Expected {N_FEATURES} weights, got {self.coef.shape}")

        self.safe_max = int(blob.get("safe_max", DEFAULT_SAFE_MAX))
        self.blocked_min = int(blob.get("blocked_min", DEFAULT_BLOCKED_MIN))
        self.metadata = blob.get("metadata", {})
        self.path = path

    # -- scoring ----------------------------------------------------------
    def predict(
        self,
        inputs: BranchInputs,
        *,
        blocklist_hit: bool = False,
    ) -> FusionResult:
        x = build_feature_vector(inputs)
        z = float(self.coef @ x + self.intercept)
        p_fraud = 1.0 / (1.0 + np.exp(-z))
        score = int(round(100 * p_fraud))

        # Per-feature contribution to z, used for explanation. A feature only
        # explains the verdict if it is genuinely elevated -- a large weight times a
        # LOW probability still yields a positive product, so a threshold on the
        # product alone would report "link matches phishing patterns" for a link
        # scored 0.01. Probability features must therefore be above 0.5 to count;
        # rule flags are facts, so firing is enough.
        contributions = {
            name: float(w * v)
            for name, w, v in zip(FEATURE_NAMES, self.coef, x)
            if w > 0 and (v >= 1.0 if name.startswith("rule_") else v >= 0.5)
        }

        overrides: list[str] = []
        if blocklist_hit:
            overrides.append("blocklist")
            score = 100
        for flag in HARD_OVERRIDE_FLAGS:
            if flag in inputs.rule_flags:
                overrides.append(flag)
                score = max(score, self.blocked_min)

        # Policy floors are unconditional: retraining a non-zero rule coefficient
        # must not silently remove a deterministic product requirement.
        for flag, tier in RULE_TIER_FLOORS.items():
            if flag in inputs.rule_flags:
                floor = self.safe_max if tier == "warning" else self.blocked_min
                if score < floor:
                    overrides.append(f"{flag}:policy_floor")
                    score = floor

        verdict = self.tier(score)
        partial = inputs.p_structural is None or inputs.p_url is None

        return FusionResult(
            risk_score=score,
            verdict=verdict,
            p_fraud=p_fraud,
            reasons=self._reasons(contributions, overrides),
            contributions=contributions,
            overrides=overrides,
            partial_analysis=partial,
        )

    def _weight_of(self, feature_name: str) -> float:
        try:
            return float(self.coef[FEATURE_NAMES.index(feature_name)])
        except ValueError:
            return 0.0

    def tier(self, score: int) -> str:
        if score < self.safe_max:
            return "safe"
        if score < self.blocked_min:
            return "warning"
        return "blocked"

    @staticmethod
    def _reasons(contributions: dict[str, float], overrides: Sequence[str]) -> list[str]:
        """Top risk drivers, strongest first, as user-facing sentences."""
        reasons: list[str] = []
        if "blocklist" in overrides:
            reasons.append("Destination appears on a known-malicious blocklist")
        for name, _ in sorted(contributions.items(), key=lambda kv: -kv[1]):
            text = REASON_TEXT.get(name)
            if text and text not in reasons:
                reasons.append(text)
        return reasons[:5]


@lru_cache(maxsize=1)
def load_engine(weights_path: Optional[str] = None) -> FusionEngine:
    """Process-wide cached engine. FastAPI calls this once at startup."""
    return FusionEngine(weights_path)
