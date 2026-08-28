"""Scan pipeline — runs both branches and the fusion engine for one scan.

This is the single place where the whole system is composed, so the ordering and the
abstain rules live here rather than being duplicated in each route:

    image  ->  structural CNN            ->  p_structural, predicted_type
    payload->  router -> rules -> Semantic Training -> p_url, flags, domain_unknown
                            \\
                             +-> fusion -> risk score, verdict, reasons

Both branches are optional. A scan with no image can still produce a complete
content verdict, and a non-URL payload can still produce a structural verdict.
Only an expected branch that is unavailable or inconclusive marks the response partial;
a deliberately inapplicable branch is a normal completed analysis.
Method 2 (the LLM) is deliberately NOT called here: measurement showed fusion already
suppresses the legacy classifier's false positives, so an always-on second opinion
was not worth its latency and cost. It runs only when the user asks, via /deep-check.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Sequence

from fusion.engine import load_engine
from fusion.features import BranchInputs
from semantic.domain_reputation import domain_unknown
from semantic.duitnow_qr import parse_duitnow
from semantic.payload_router import PayloadInfo, route_payload
from semantic.rule_engine import RuleFlag, check_url
from semantic.semantic_service import load_analyzer as load_semantic
from structural.structural_service import load_analyzer as load_structural
from structural.structural_service import load_camera_analyzer as load_camera_structural

from app.schemas import BranchScores, ScanResponse


def _llm_configured() -> bool:
    from semantic.llm_providers import is_configured

    return is_configured()


@dataclass
class SemanticSignals:
    info: PayloadInfo
    flags: list[RuleFlag]
    p_url: Optional[float]
    domain_unknown: Optional[float]


@dataclass(frozen=True)
class StructuralSignals:
    """Structural evidence from the one selected QR crop."""

    effective: Optional[float]
    raw_score: Optional[float]
    predicted_type: Optional[str]


def _analyse_images(images: Sequence, source: str) -> StructuralSignals:
    """Score one crop with the model validated for its acquisition domain.

    The Flutter client ranks live observations for acquisition quality and sends
    the clearest rectified crop first. Gallery keeps the stable pristine-image
    model; camera uses the camera-robust model because the gallery artifact has a
    measured 80.84% clean false-positive rate on camera-derived images. No score
    is suppressed or threshold-replaced. Legacy clients may still submit several
    crops; only the first is authoritative.
    """
    if not images:
        return StructuralSignals(None, None, None)

    analyzer = load_camera_structural() if source == "camera" else load_structural()
    result = analyzer.predict(images[0])
    score = float(result.p_structural)
    return StructuralSignals(score, score, result.predicted_type)


def analyse_payload(payload: str) -> SemanticSignals:
    """Semantic branch: route, apply rules, score the URL string."""
    info = route_payload(payload)
    flags = check_url(info)

    p_url = None
    unknown = None
    if info.is_url and info.scheme not in ("javascript", "data"):
        # javascript:/data: payloads have no host to classify - the rule engine has
        # already flagged them, and Semantic Training excludes hostless strings.
        p_url = load_semantic().predict(info.normalized_url or info.raw).p_url
        unknown = domain_unknown(info.registered_domain)

    return SemanticSignals(info=info, flags=flags, p_url=p_url, domain_unknown=unknown)


async def run_deep_check(
    payload: str,
    p_structural: Optional[float] = None,
    expand_redirects: bool = True,
    llm_call=None,
):
    """User-initiated deep check (option E) — the only path that calls Method 2.

    Adds two things the automatic scan deliberately skips because they cost time:
    the real redirect chain, and an LLM reasoning pass with world knowledge. The
    result is folded back through fusion so the user sees an updated verdict rather
    than a second, disconnected opinion.
    """
    import time

    from semantic.llm_providers import get_default_call
    from semantic.method2 import analyze, build_input
    from semantic.redirect_expander import expand

    from app.schemas import DeepCheckResponse

    started = time.perf_counter()
    sem = analyse_payload(payload)
    flag_names = [f.flag for f in sem.flags]

    def fuse(llm_score):
        return load_engine().predict(
            BranchInputs(
                p_structural=p_structural,
                p_url=sem.p_url,
                llm_score=llm_score,
                rule_flags=flag_names,
                domain_unknown=sem.domain_unknown,
            )
        )

    before = fuse(None)

    # 1. Behavioural evidence: where does the link actually go?
    final_url = sem.info.normalized_url or sem.info.raw
    chain: list[str] = []
    blocked_reason = None
    if expand_redirects and sem.info.is_url and sem.info.scheme in ("http", "https"):
        expansion = await expand(final_url)
        chain = expansion.chain
        final_url = expansion.final_url
        blocked_reason = expansion.blocked_reason

    # 2. LLM reasoning over that evidence.
    call = llm_call or get_default_call()
    if call is None:
        return DeepCheckResponse(
            llm_verdict="suspicious",
            llm_confidence=0.5,
            explanation="Deep analysis is not configured on this server.",
            risk_factors=[],
            final_url=final_url,
            redirect_chain=chain,
            redirect_blocked_reason=blocked_reason,
            verdict=before.verdict,
            risk_score=before.risk_score,
            previous_risk_score=before.risk_score,
            reasons=before.reasons,
            llm_available=False,
            error="No LLM credential configured (set GEMINI_API_KEY).",
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )

    result = analyze(
        build_input(
            sem.info,
            sem.flags,
            sem.p_url or 0.0,
            final_url=final_url,
            redirect_chain=chain,
        ),
        call,
    )

    # 3. Re-fuse with the LLM opinion included.
    after = fuse(result.to_llm_score())
    reasons = list(after.reasons)
    if result.explanation and result.explanation not in reasons:
        reasons.insert(0, result.explanation)

    return DeepCheckResponse(
        llm_verdict=result.verdict,
        llm_confidence=result.confidence,
        explanation=result.explanation,
        risk_factors=result.risk_factors,
        final_url=final_url,
        redirect_chain=chain,
        redirect_blocked_reason=blocked_reason,
        verdict=after.verdict,
        risk_score=after.risk_score,
        previous_risk_score=before.risk_score,
        reasons=reasons[:6],
        llm_available=result.error is None,
        error=result.error,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


def run_scan(
    payload: Optional[str] = None,
    image=None,
    image_source: str = "unknown",
    images: Optional[Sequence] = None,
    image_expected: bool = False,
) -> ScanResponse:
    """Full pipeline for one scan. `image` is an optional PIL Image of the QR crop.

    `payload` is optional: when it is missing the image is decoded server-side. The
    phone app always sends it (decoding on-device is faster and works offline), but
    Swagger, curl and evaluation scripts only have a picture. A QR too damaged to
    decode yields `payload_source="undecodable"` — the semantic branch abstains while
    the structural branch still reports what it sees.
    """
    started = time.perf_counter()

    source = image_source if image_source in {"camera", "gallery"} else "unknown"
    image_list = (
        list(images) if images is not None else ([] if image is None else [image])
    )
    structural = _analyse_images(image_list, source)
    p_structural_raw = structural.raw_score
    p_structural = structural.effective
    structural_type = structural.predicted_type
    structural_status = (
        "completed"
        if structural.effective is not None
        else "unavailable"
        if source in {"camera", "gallery"} or image_expected
        else "not_applicable"
    )

    payload_source = "provided"
    if not (payload or "").strip():
        payload = None
        if image_list:
            from structural.qr_decoder import decode_qr

            payload = next(
                (
                    decoded
                    for candidate in image_list
                    if (decoded := decode_qr(candidate))
                ),
                None,
            )
        payload_source = "decoded" if payload else "undecodable"

    sem = analyse_payload(payload or "")
    flag_names = [f.flag for f in sem.flags]
    semantic_status = (
        "unavailable"
        if payload_source == "undecodable"
        else "completed"
        if sem.p_url is not None
        else "not_applicable"
    )

    engine = load_engine()
    fusion = engine.predict(
        BranchInputs(
            p_structural=p_structural,
            p_url=sem.p_url,
            llm_score=None,
            rule_flags=flag_names,
            domain_unknown=sem.domain_unknown,
        )
    )

    # The rule engine's evidence strings are more specific than the generic fusion
    # reason text, so they are merged in for flags that actually fired.
    reasons = list(fusion.reasons)
    for f in sem.flags:
        if f.evidence not in reasons:
            reasons.append(f.evidence)

    risk_score = fusion.risk_score
    verdict = fusion.verdict

    # A CRC-valid Malaysian DuitNow payload is handed to the payment app, where
    # the user must confirm recipient and amount. Camera acquisition artefacts on
    # dense/branded payment codes must not manufacture a hard Blocked result and
    # prevent that verification step. Keep the Structural score/type visible,
    # retain a Warning, and never apply this policy to invalid EMV text or generic
    # payment URIs.
    if parse_duitnow(payload or "") is not None and verdict == "blocked":
        verdict = "warning"
        risk_score = engine.safe_max
        payment_reason = (
            "Verified DuitNow format; confirm the recipient and amount in the "
            "payment app"
        )
        if payment_reason not in reasons:
            reasons.append(payment_reason)

    return ScanResponse(
        verdict=verdict,
        risk_score=risk_score,
        reasons=reasons[:6],
        payload_type=sem.info.payload_type,
        normalized_url=sem.info.normalized_url,
        registered_domain=sem.info.registered_domain,
        rule_flags=flag_names,
        branch_scores=BranchScores(
            p_structural=p_structural,
            structural_status=structural_status,
            p_structural_raw=p_structural_raw,
            structural_type=structural_type,
            p_url=sem.p_url,
            semantic_status=semantic_status,
            llm_score=None,
            domain_unknown=sem.domain_unknown,
            image_source=source,
        ),
        # A deliberately inapplicable model is not a failed analysis. Wi-Fi,
        # plain text and verified DuitNow payloads do not need a URL-model score.
        partial_analysis=bool(
            structural_status in {"unavailable", "inconclusive"}
            or semantic_status in {"unavailable", "inconclusive"}
        ),
        # A deep check only makes sense for URLs the user is actually being warned
        # about, and only if a provider is configured.
        deep_check_available=bool(
            sem.info.is_url and verdict != "safe" and _llm_configured()
        ),
        payload=payload,
        payload_source=payload_source,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
