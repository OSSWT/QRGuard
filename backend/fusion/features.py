"""Fusion feature contract — turns branch outputs into a fixed-length vector.

The meta-classifier is a trained model, so the feature vector must have the SAME
length and the SAME ordering on every call, forever. `FEATURE_NAMES` is that
contract: appending is safe (retrain required), reordering or removing entries
silently corrupts every prediction.

Missing branches are represented explicitly: an abstaining branch contributes
**nothing** to the score (value 0.0) and sets its `*_present` indicator to 0.

The indicator, not the value, is what carries "no evidence" — because these are
risk probabilities multiplied by large positive weights, any non-zero placeholder
would manufacture risk out of an absent branch. An earlier version used 0.5 here
and every image-less scan came back Blocked with the reason "QR image appears
manipulated", for a scan that had no image at all. Callers must surface
`partial_analysis` so a verdict resting on one branch is visibly provisional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from semantic.rule_engine import FLAG_VOCABULARY

ABSENT = 0.0  # an abstaining branch must add no risk of its own

FEATURE_NAMES: tuple[str, ...] = (
    "p_structural",       # 1 - P(clean) from the CNN
    "structural_present",
    "p_url",              # phishing probability from Method 1
    "semantic_present",
    "llm_score",          # Method 2 verdict mapped to 0-1
    "llm_invoked",
    "domain_unknown",     # registered domain not in the well-known list
    *(f"rule_{flag}" for flag in FLAG_VOCABULARY),
)

N_FEATURES = len(FEATURE_NAMES)


@dataclass(frozen=True)
class BranchInputs:
    """Everything the fusion engine may receive for one scan."""

    p_structural: Optional[float] = None      # None = structural branch abstained
    p_url: Optional[float] = None             # None = semantic branch abstained
    llm_score: Optional[float] = None         # None = Method 2 not invoked
    rule_flags: Sequence[str] = ()            # flag names that fired
    domain_unknown: Optional[float] = None    # 1 = registered domain not well known


def build_feature_vector(inputs: BranchInputs) -> np.ndarray:
    """Assemble the fixed-order feature vector for one scan."""
    fired = set(inputs.rule_flags)
    values = [
        ABSENT if inputs.p_structural is None else float(inputs.p_structural),
        0.0 if inputs.p_structural is None else 1.0,
        ABSENT if inputs.p_url is None else float(inputs.p_url),
        0.0 if inputs.p_url is None else 1.0,
        ABSENT if inputs.llm_score is None else float(inputs.llm_score),
        0.0 if inputs.llm_score is None else 1.0,
        # Domain reliability. Absent (non-URL payload) adds no risk either:
        # "there is no domain to be unknown".
        ABSENT if inputs.domain_unknown is None else float(inputs.domain_unknown),
        *(1.0 if flag in fired else 0.0 for flag in FLAG_VOCABULARY),
    ]
    return np.asarray(values, dtype=np.float64)


def feature_dict(vector: np.ndarray) -> dict[str, float]:
    """Name -> value, for logging and explanation."""
    return dict(zip(FEATURE_NAMES, (float(v) for v in vector)))
