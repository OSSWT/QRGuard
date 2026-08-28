"""Method 2 — Behavioral-Contextual Analyzer (LLM reasoning).

Semantic Analysis's second, complementary analyzer. Where Method 1 judges the URL
string, Method 2 reasons over behaviour and world knowledge (expanded destination,
redirect chain, brand impersonation) for the minority of scans Method 1 cannot
resolve confidently. It also produces the human-readable explanation shown in the
UI.

This module is provider-agnostic: it does not import any vendor SDK. The caller
injects an ``llm_call(system_prompt: str, user_message: str) -> str`` function, so
the analyzer is fully unit-testable offline and can run on Claude, Gemini, or any
other API. A thin default that reads an API key from the environment is provided
separately (``default_llm_call``) and is never required for tests.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Protocol

from semantic.payload_router import PayloadInfo
from semantic.rule_engine import RuleFlag

# Trigger band: Method 2 is invoked only when Method 1 is not confident, or when
# behaviour must be inspected. Boundaries are tuned in fusion training (T4).
UNCERTAIN_LOW = 0.35
UNCERTAIN_HIGH = 0.75

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "analyzer_v1.txt"

VALID_VERDICTS = ("benign", "suspicious", "phishing")


class LLMCall(Protocol):
    def __call__(self, system_prompt: str, user_message: str) -> str: ...


@dataclass
class SemanticLLMResult:
    verdict: str  # one of VALID_VERDICTS
    confidence: float
    risk_factors: list[str] = field(default_factory=list)
    explanation: str = ""
    llm_invoked: bool = True
    error: Optional[str] = None

    def to_llm_score(self) -> float:
        """Map verdict + confidence to a 0-1 fraud score for fusion.

        phishing -> confidence; benign -> 1 - confidence; suspicious -> a
        mild-risk value pulled toward 0.5 by confidence.
        """
        if self.verdict == "phishing":
            return self.confidence
        if self.verdict == "benign":
            return 1.0 - self.confidence
        # suspicious: 0.5 at zero confidence, up to ~0.65 when confident it is
        # genuinely ambiguous-but-leaning-risky.
        return 0.5 + 0.15 * self.confidence


def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def should_invoke(
    p_url: float,
    rule_flags: list[RuleFlag],
    *,
    is_shortened_or_redirected: bool,
    is_unseen_domain: bool,
) -> bool:
    """Trigger rule: uncertain band OR shortened/redirected OR unseen domain.

    A confirmed js/data URI is already decisive for the rule engine and does not
    need LLM reasoning, but any other condition sends the case to Method 2.
    """
    if UNCERTAIN_LOW <= p_url <= UNCERTAIN_HIGH:
        return True
    if is_shortened_or_redirected:
        return True
    if is_unseen_domain:
        return True
    return False


def build_input(
    info: PayloadInfo,
    rule_flags: list[RuleFlag],
    p_url: float,
    *,
    final_url: Optional[str] = None,
    redirect_chain: Optional[list[str]] = None,
) -> dict:
    """Assemble the JSON payload the analyst prompt expects."""
    return {
        "original_url": info.normalized_url or info.raw,
        "redirect_chain": redirect_chain or [],
        "final_url": final_url or info.normalized_url or info.raw,
        "registered_domain": info.registered_domain,
        "rule_flags": [f.flag for f in rule_flags],
        "classifier_score": round(float(p_url), 4),
    }


def analyze(model_input: dict, llm_call: LLMCall) -> SemanticLLMResult:
    """Run the LLM analyst on ``model_input`` and parse its verdict.

    Any failure (call error, unparseable output, bad fields) degrades to a
    cautious ``suspicious`` result with ``error`` set — the fusion engine treats
    this as low-confidence intermediate evidence rather than crashing.
    """
    system = load_system_prompt()
    user = json.dumps(model_input, ensure_ascii=False)

    try:
        raw = llm_call(system, user)
    except Exception as exc:  # noqa: BLE001 - any provider error must be contained
        return SemanticLLMResult(
            verdict="suspicious", confidence=0.5,
            risk_factors=["Automated deep analysis unavailable"],
            explanation="Could not complete deep link analysis; treat with caution.",
            error=f"{type(exc).__name__}: {exc}",
        )

    return _parse(raw)


def _parse(raw: str) -> SemanticLLMResult:
    data = _extract_json(raw)
    if data is None:
        return SemanticLLMResult(
            verdict="suspicious", confidence=0.5,
            risk_factors=["Unreadable analysis output"],
            explanation="Deep analysis returned an unexpected format; treat with caution.",
            error="unparseable LLM output",
        )

    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in VALID_VERDICTS:
        verdict = "suspicious"

    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    factors = data.get("risk_factors", [])
    if not isinstance(factors, list):
        factors = []
    factors = [str(x) for x in factors][:5]

    explanation = str(data.get("explanation", "")).strip()

    return SemanticLLMResult(
        verdict=verdict, confidence=confidence,
        risk_factors=factors, explanation=explanation,
    )


_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(raw: str) -> Optional[dict]:
    """Parse a JSON object from an LLM response, tolerating code fences and
    surrounding prose."""
    if not raw or not raw.strip():
        return None
    text = raw.strip()

    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    # Fall back to the first balanced {...} block.
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def default_llm_call(system_prompt: str, user_message: str) -> str:
    """Optional default provider (Anthropic Claude). Requires ANTHROPIC_API_KEY
    and the ``anthropic`` package. Not used by tests. Kept tiny on purpose — the
    orchestrator may swap in Gemini or another provider by injecting its own
    callable instead.
    """
    import os

    import anthropic  # imported lazily so the package is optional

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=os.environ.get("QRGUARD_LLM_MODEL", "claude-haiku-4-5-20251001"),
        max_tokens=512,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")
