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

import os
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from statistics import median
from typing import Optional

from fusion.engine import load_engine
from fusion.features import BranchInputs
from semantic.domain_reputation import domain_unknown
from semantic.duitnow_qr import parse_duitnow
from semantic.payload_router import PayloadInfo, route_payload
from semantic.rule_engine import RuleFlag, check_url
from semantic.semantic_service import load_analyzer as load_semantic
from structural.image_quality import assess_image_quality, normalize_measured_range
from structural.qr_decoder import estimate_qr_module_count
from structural.structural_service import load_analyzer as load_structural
from structural.structural_service import load_camera_analyzer as load_camera_structural
from structural.structural_service import load_unified_candidate_analyzer

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
    """Structural evidence from one crop or a bounded camera consensus."""

    effective: Optional[float]
    raw_score: Optional[float]
    predicted_type: Optional[str]
    manipulation_confidence: Optional[float]
    confirmed_manipulation: bool = False
    quality_status: Optional[str] = None
    quality_conditions: tuple[str, ...] = ()
    rescan_reason: Optional[str] = None
    frames_received: int = 0
    frames_analyzed: int = 0
    consensus: Optional[str] = None
    camera_definitive_manipulation_floor: Optional[float] = None
    module_count: int | None = None
    minimum_module_pixels: float | None = None


_CAMERA_BLOCK_CONFIDENCE = 0.95
_CAMERA_CONSENSUS_MIN_FRAMES = 3
# The promoted exact-app camera holdout contains crops from 257 px upward. The
# model has no deployment evidence below that acquisition scale; upsampling a
# 120 px high-version QR to 224 px manufactured confident false manipulation in
# the physical-phone repeatability study. New multi-frame camera callers must
# therefore provide at least three crops inside the validated range.
_CAMERA_MIN_CROP_SIDE = 256
# The r02 physical-development capture contains 240 independently collected
# frames across QR versions 1-14. Its observed acquisition range is
# 5.15-17.44 px/module. Five pixels is therefore the first evidence-backed,
# version-aware floor; it replaces neither the 256 px floor nor unknown-grid
# fallback. A QR whose grid cannot be observed is never labelled from that fact.
_CAMERA_MIN_MODULE_PIXELS = 5.0
_CAMERA_CROP_QUIET_ZONE_SCALE = 1.30
_RECOVERABLE_DYNAMIC_RANGE = 70.0
_RECOVERABLE_FOCUS = 55.0


def _normalize_camera_capture(image):
    """Correct global exposure while preserving local colour/shape evidence.

    Phone and projector captures often turn a black/white QR into a narrow grey
    range. The camera model learned that acquisition artefact too strongly. A
    percentile stretch restores the global paper/ink range but does not blur,
    threshold, erase a logo, or remove local adversarial colour variation.
    """
    import numpy as np
    from PIL import Image

    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    luminance = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    black, white = np.percentile(luminance, (5, 95))
    if white - black < 30:
        return image.convert("RGB")

    gain = float(np.clip(239.0 / (white - black), 0.70, 2.20))
    normalized = np.clip(rgb * gain + (8.0 - black * gain), 0, 255).astype(np.uint8)
    return Image.fromarray(normalized, mode="RGB")


def _recover_unified_camera_quality(image, quality):
    """Recover exposure range only when measured detail still exists.

    This is one global affine transform; it cannot redraw modules, remove local
    colour perturbations, heal an overlay, or sharpen blur. The original quality
    conditions remain in the response together with ``range_corrected``.
    """
    exposure_only = set(quality.conditions).issubset(
        {"underexposure", "overexposure", "low_contrast"}
    )
    if (
        not exposure_only
        or quality.dynamic_range < _RECOVERABLE_DYNAMIC_RANGE
        or quality.laplacian_variance < _RECOVERABLE_FOCUS
    ):
        return None
    prepared = normalize_measured_range(image, quality, allow_unusable=True)
    recovered = assess_image_quality(prepared)
    if not recovered.usable:
        return None
    return prepared


def _analyse_one_image(
    image, source: str, *, defer_camera_uncertainty: bool = False
) -> StructuralSignals:
    """Score one crop using the currently selected Structural artifact."""
    unified_artifacts = os.getenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS")
    if unified_artifacts:
        quality = assess_image_quality(image)
        quality_status = quality.status
        quality_conditions = quality.conditions
        if not quality.usable:
            prepared = (
                _recover_unified_camera_quality(image, quality)
                if source == "camera"
                else None
            )
            if prepared is None:
                return StructuralSignals(
                    None,
                    None,
                    None,
                    None,
                    quality_status=quality.status,
                    quality_conditions=quality.conditions,
                    rescan_reason=quality.rescan_reason,
                    frames_received=1,
                    consensus="single_frame",
                )
            quality_status = "marginal"
            quality_conditions = tuple(
                dict.fromkeys((*quality.conditions, "range_corrected"))
            )
        else:
            prepared = normalize_measured_range(image, quality)
        analyzer = load_unified_candidate_analyzer(unified_artifacts)
        result = analyzer.predict(prepared)
        score = float(result.p_structural)
        manipulation_confidence = max(
            float(result.probs.get("adversarial", 0.0)),
            float(result.probs.get("tampered", 0.0)),
        )
        definitive_floor = getattr(
            analyzer, "camera_definitive_manipulation_floor", None
        )
        if (
            source == "camera"
            and result.predicted_type != "clean"
            and definitive_floor is not None
            and score < definitive_floor
            and not defer_camera_uncertainty
        ):
            return StructuralSignals(
                None,
                score,
                None,
                manipulation_confidence,
                quality_status="marginal",
                quality_conditions=tuple(
                    dict.fromkeys(
                        (*quality_conditions, "uncertain_structural_prediction")
                    )
                ),
                rescan_reason=(
                    "Camera image evidence is too close to the Structural decision "
                    "boundary; hold the QR code steady and scan again."
                ),
                frames_received=1,
                frames_analyzed=1,
                consensus="single_frame",
                camera_definitive_manipulation_floor=definitive_floor,
            )
        return StructuralSignals(
            score,
            score,
            result.predicted_type,
            manipulation_confidence,
            confirmed_manipulation=result.predicted_type != "clean",
            quality_status=quality_status,
            quality_conditions=quality_conditions,
            frames_received=1,
            frames_analyzed=1,
            consensus="single_frame",
            camera_definitive_manipulation_floor=definitive_floor,
        )

    image = _normalize_camera_capture(image) if source == "camera" else image
    analyzer = load_camera_structural() if source == "camera" else load_structural()
    result = analyzer.predict(image)
    score = float(result.p_structural)
    manipulation_confidence = max(
        float(result.probs.get("adversarial", 0.0)),
        float(result.probs.get("tampered", 0.0)),
    )

    # The camera artifact is a three-class model. For an argmax ``clean`` result,
    # summing both losing manipulation classes inflated ordinary Google/YouTube/
    # UTAR captures across the decision boundaries. Use the strongest competing
    # manipulation class as the deployed camera evidence and keep the original
    # 1-P(clean) value in p_structural_raw for auditability. A model prediction of
    # adversarial/tampered is sent through the independent confirmation below.
    primary_effective = (
        manipulation_confidence
        if source == "camera" and result.predicted_type == "clean"
        else score
    )

    if source != "camera" or result.predicted_type == "clean":
        return StructuralSignals(
            primary_effective,
            score,
            result.predicted_type,
            manipulation_confidence,
            frames_received=1,
            frames_analyzed=1,
            consensus="single_frame",
        )

    # A suspected camera manipulation gets a second, independent view. Requiring
    # both models to see non-clean structure rejects the exposure false-positive
    # mode without weakening semantic URL checks. The minimum keeps one highly
    # uncertain model from manufacturing a large fused risk score.
    reference = load_structural().predict(image)
    reference_confidence = max(
        float(reference.probs.get("adversarial", 0.0)),
        float(reference.probs.get("tampered", 0.0)),
    )
    reference_effective = (
        reference_confidence
        if reference.predicted_type == "clean"
        else float(reference.p_structural)
    )
    models_confirm_manipulation = reference.predicted_type != "clean"
    effective = min(primary_effective, reference_effective)
    return StructuralSignals(
        effective,
        score,
        result.predicted_type if models_confirm_manipulation else "clean",
        effective,
        models_confirm_manipulation,
        frames_received=1,
        frames_analyzed=1,
        consensus="single_frame",
    )


def _consensus(signals: list[StructuralSignals], received: int) -> StructuralSignals:
    """Aggregate independent camera frames by median score and majority class."""
    valid = [signal for signal in signals if signal.effective is not None]
    if len(valid) < _CAMERA_CONSENSUS_MIN_FRAMES:
        raw_scores = [
            signal.raw_score for signal in signals if signal.raw_score is not None
        ]
        manipulation_confidences = [
            signal.manipulation_confidence
            for signal in signals
            if signal.manipulation_confidence is not None
        ]
        conditions = tuple(
            dict.fromkeys(
                condition
                for signal in signals
                for condition in signal.quality_conditions
            )
        )
        return StructuralSignals(
            None,
            float(median(raw_scores)) if raw_scores else None,
            None,
            (
                float(median(manipulation_confidences))
                if manipulation_confidences
                else None
            ),
            quality_status="unusable",
            quality_conditions=conditions or ("insufficient_clear_frames",),
            rescan_reason=(
                "Camera image evidence is too close to the Structural decision "
                "boundary; hold the QR code steady and scan again."
                if "uncertain_structural_prediction" in conditions
                else "QR image detail is insufficient; move closer and hold the code "
                "inside the guide before scanning again."
            ),
            frames_received=received,
            frames_analyzed=sum(signal.frames_analyzed for signal in signals),
            consensus=(
                "insufficient_confidence"
                if "uncertain_structural_prediction" in conditions
                else "insufficient_quality"
            ),
        )

    nonclean = [
        signal
        for signal in valid
        if signal.confirmed_manipulation
        and signal.predicted_type in {"adversarial", "tampered"}
    ]
    confirmed = len(nonclean) > len(valid) / 2
    predicted_type = "clean"
    if confirmed:
        predicted_type = Counter(
            signal.predicted_type for signal in nonclean
        ).most_common(1)[0][0]
    statuses = {signal.quality_status for signal in valid}
    conditions = tuple(
        dict.fromkeys(
            condition for signal in valid for condition in signal.quality_conditions
        )
    )
    effective = float(median(signal.effective for signal in valid))
    raw_score = float(median(signal.raw_score for signal in valid))
    manipulation_confidence = float(
        median(signal.manipulation_confidence for signal in valid)
    )
    definitive_floors = {
        signal.camera_definitive_manipulation_floor
        for signal in valid
        if signal.camera_definitive_manipulation_floor is not None
    }
    if len(definitive_floors) > 1:
        raise ValueError("Camera consensus mixed incompatible Structural policies")
    definitive_floor = next(iter(definitive_floors), None)
    if confirmed and definitive_floor is not None and effective < definitive_floor:
        return StructuralSignals(
            None,
            raw_score,
            None,
            manipulation_confidence,
            quality_status="unusable",
            quality_conditions=tuple(
                dict.fromkeys((*conditions, "uncertain_structural_prediction"))
            ),
            rescan_reason=(
                "Camera image evidence is too close to the Structural decision "
                "boundary; hold the QR code steady and scan again."
            ),
            frames_received=received,
            frames_analyzed=len(valid),
            consensus="insufficient_confidence",
            camera_definitive_manipulation_floor=definitive_floor,
        )
    return StructuralSignals(
        effective=effective,
        raw_score=raw_score,
        predicted_type=predicted_type,
        manipulation_confidence=manipulation_confidence,
        confirmed_manipulation=confirmed,
        quality_status="marginal" if "marginal" in statuses else "usable",
        quality_conditions=conditions,
        frames_received=received,
        frames_analyzed=len(valid),
        consensus="median_score_majority_class",
        camera_definitive_manipulation_floor=definitive_floor,
    )


def _analyse_images(
    images: Sequence,
    source: str,
    *,
    require_camera_consensus: bool = False,
) -> StructuralSignals:
    """Score Gallery once or form a bounded multi-frame Camera consensus.

    One-image callers retain the established contract. Current Camera callers
    send the best three eligible crops from a five-observation fallback pool.
    Crops below the minimum exact-app
    deployment scale are not treated as clean or malicious; at least three
    in-range frames are required before a consensus can reach Fusion.
    """
    selected = list(images[:5])
    module_count = None
    minimum_module_pixels = None
    if source == "camera" and selected:
        module_count = next(
            (
                observed
                for candidate in selected
                if (observed := estimate_qr_module_count(candidate)) is not None
            ),
            None,
        )
        if module_count is not None:
            minimum_module_pixels = min(
                min(image.width, image.height)
                / (_CAMERA_CROP_QUIET_ZONE_SCALE * module_count)
                for image in selected
            )

    def with_grid_measurements(signal: StructuralSignals) -> StructuralSignals:
        return replace(
            signal,
            module_count=module_count,
            minimum_module_pixels=minimum_module_pixels,
        )

    if not selected and not (source == "camera" and require_camera_consensus):
        return StructuralSignals(None, None, None, None)
    if source != "camera":
        return _analyse_one_image(selected[0], source)
    if len(selected) < _CAMERA_CONSENSUS_MIN_FRAMES:
        if not require_camera_consensus:
            return with_grid_measurements(_analyse_one_image(selected[0], source))
        return with_grid_measurements(
            StructuralSignals(
                None,
                None,
                None,
                None,
                quality_status="unusable",
                quality_conditions=("insufficient_camera_frames",),
                rescan_reason=(
                    "Fewer than three distinct camera frames were available; hold "
                    "the QR code steady and scan again."
                ),
                frames_received=len(selected),
                frames_analyzed=0,
                consensus="insufficient_quality",
            )
        )

    in_range = [
        image
        for image in selected
        if min(image.width, image.height) >= _CAMERA_MIN_CROP_SIDE
        and (
            module_count is None
            or min(image.width, image.height)
            / (_CAMERA_CROP_QUIET_ZONE_SCALE * module_count)
            >= _CAMERA_MIN_MODULE_PIXELS
        )
    ]
    if len(in_range) < _CAMERA_CONSENSUS_MIN_FRAMES:
        module_scale_failed = bool(
            module_count is not None
            and any(
                min(image.width, image.height) >= _CAMERA_MIN_CROP_SIDE
                and min(image.width, image.height)
                / (_CAMERA_CROP_QUIET_ZONE_SCALE * module_count)
                < _CAMERA_MIN_MODULE_PIXELS
                for image in selected
            )
        )
        return with_grid_measurements(
            StructuralSignals(
                None,
                None,
                None,
                None,
                quality_status="unusable",
                quality_conditions=(
                    "insufficient_module_scale"
                    if module_scale_failed
                    else "small_camera_crop",
                ),
                rescan_reason=(
                    "QR modules are too small for reliable image-integrity analysis; "
                    "move closer until the whole code fills more of the guide."
                    if module_scale_failed
                    else "QR image detail is insufficient; move closer and hold the "
                    "code inside the guide before scanning again."
                ),
                frames_received=len(selected),
                frames_analyzed=0,
                consensus="insufficient_quality",
            )
        )
    return with_grid_measurements(
        _consensus(
            [
                _analyse_one_image(image, source, defer_camera_uncertainty=True)
                for image in in_range
            ],
            received=len(selected),
        )
    )


def _is_low_risk_known_url(sem: SemanticSignals) -> bool:
    return bool(
        sem.info.is_url
        and sem.p_url is not None
        and sem.p_url <= 0.15
        and sem.domain_unknown == 0.0
        and not sem.flags
    )


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
    payload_was_decoded: bool = False,
    require_camera_consensus: bool = False,
) -> ScanResponse:
    """Full pipeline for one scan. `image` is an optional PIL Image of the QR crop.

    `payload` is optional: when it is missing the image is decoded server-side. The
    phone app always sends it (decoding on-device is faster and works offline), but
    Swagger, curl and evaluation scripts only have a picture. A QR too damaged to
    decode yields `payload_source="undecodable"` — the semantic branch abstains while
    the structural branch still reports what it sees. `payload_was_decoded` preserves
    that provenance when the HTTP layer has already decoded and rectified a Web
    Gallery upload.
    """
    started = time.perf_counter()

    source = image_source if image_source in {"camera", "gallery"} else "unknown"
    image_list = (
        list(images) if images is not None else ([] if image is None else [image])
    )
    structural_started = time.perf_counter()
    structural = _analyse_images(
        image_list,
        source,
        require_camera_consensus=require_camera_consensus,
    )
    structural_ms = int((time.perf_counter() - structural_started) * 1000)
    p_structural_raw = structural.raw_score
    p_structural = structural.effective
    structural_type = structural.predicted_type
    structural_status = (
        "completed"
        if structural.effective is not None
        else "inconclusive"
        if structural.quality_status == "unusable" or structural.rescan_reason
        else "unavailable"
        if source in {"camera", "gallery"} or image_expected
        else "not_applicable"
    )

    payload_decode_started = time.perf_counter()
    payload_source = "decoded" if payload_was_decoded else "provided"
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
    payload_decode_ms = int((time.perf_counter() - payload_decode_started) * 1000)

    semantic_started = time.perf_counter()
    sem = analyse_payload(payload or "")
    flag_names = [f.flag for f in sem.flags]
    semantic_status = (
        "unavailable"
        if payload_source == "undecodable"
        else "completed"
        if sem.p_url is not None
        else "not_applicable"
    )
    semantic_ms = int((time.perf_counter() - semantic_started) * 1000)

    fusion_started = time.perf_counter()
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
    fusion_ms = int((time.perf_counter() - fusion_started) * 1000)

    policy_started = time.perf_counter()
    # The rule engine's evidence strings are more specific than the generic fusion
    # reason text, so they are merged in for flags that actually fired.
    reasons = list(fusion.reasons)
    if structural.rescan_reason and structural.rescan_reason not in reasons:
        reasons.append(structural.rescan_reason)
    for f in sem.flags:
        if f.evidence not in reasons:
            reasons.append(f.evidence)

    risk_score = fusion.risk_score
    verdict = fusion.verdict

    # Source-neutral quality abstention means "insufficient image evidence",
    # never "the image is safe" and never "the image is malicious". Keep the
    # result at least Warning so both Gallery and Camera ask for a better scan.
    if structural_status == "inconclusive" and verdict == "safe":
        verdict = "warning"
        risk_score = engine.safe_max
        quality_reason = structural.rescan_reason or (
            "Image quality is insufficient; capture the QR code again"
        )
        if quality_reason not in reasons:
            reasons.append(quality_reason)

    # When an image was supplied but its payload cannot be decoded, Semantic has
    # not cleared the destination. A clean-looking QR surface is not evidence
    # that the hidden/unknown payload is safe. Fail closed to a rescan Warning;
    # confirmed Structural manipulation below can still raise this to Blocked.
    if (
        payload_source == "undecodable"
        and semantic_status == "unavailable"
        and (source in {"camera", "gallery"} or image_expected)
        and verdict == "safe"
    ):
        verdict = "warning"
        risk_score = engine.safe_max
        decode_reason = (
            "QR payload could not be decoded; capture a clearer image before "
            "trusting the destination"
        )
        if decode_reason not in reasons:
            reasons.append(decode_reason)

    # A completed Structural prediction whose winning class is adversarial or
    # tampered is confirmed manipulation evidence, not merely a continuous risk
    # hint. Preserve that class-level decision across the Fusion boundary even
    # when calibration leaves p_structural just below the numeric block cutoff.
    # This rule is deliberately source-neutral for the unified candidate model.
    # The explicit DuitNow and attendance hand-off policies below may still
    # downgrade the result because those payloads require specialised handling.
    if structural_status == "completed" and structural.confirmed_manipulation:
        verdict = "blocked"
        risk_score = max(risk_score, engine.blocked_min)
        manipulation_reason = "Structural model confirmed QR manipulation"
        if manipulation_reason not in reasons:
            reasons.append(manipulation_reason)

    # Camera evidence below the model's high-confidence attack band must not be
    # the sole reason a widely recognised, low-risk URL becomes Blocked. This is
    # cross-modal disagreement, so retain a Warning and let the user inspect the
    # decoded destination. High-confidence camera attacks and every risky URL keep
    # the normal fusion verdict; gallery uses its separately validated model.
    if (
        source == "camera"
        and verdict == "blocked"
        and _is_low_risk_known_url(sem)
        and not structural.confirmed_manipulation
        and (structural.manipulation_confidence or 0.0) < _CAMERA_BLOCK_CONFIDENCE
    ):
        verdict = "warning"
        risk_score = engine.safe_max
        disagreement_reason = (
            "Camera image evidence is uncertain; verify the decoded destination"
        )
        if disagreement_reason not in reasons:
            reasons.append(disagreement_reason)

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

    # hi-hive attendance QR values are opaque app tokens, not web destinations.
    # QRGuard can recognise the envelope but cannot authenticate or redeem it.
    # Never claim Safe, and never let projector/logo artefacts prevent the user
    # from handing control to the official hi-hive app for a fresh scan.
    if sem.info.payload_type == "attendance":
        verdict = "warning"
        risk_score = engine.safe_max
        attendance_reason = (
            "Recognised hi-hive attendance format; verify it in the official app"
        )
        if attendance_reason not in reasons:
            reasons.append(attendance_reason)

    policy_ms = int((time.perf_counter() - policy_started) * 1000)
    total_ms = int((time.perf_counter() - started) * 1000)

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
            structural_quality_status=structural.quality_status,
            structural_quality_conditions=list(structural.quality_conditions),
            structural_rescan_reason=structural.rescan_reason,
            structural_frames_received=structural.frames_received,
            structural_frames_analyzed=structural.frames_analyzed,
            structural_consensus=structural.consensus,
            structural_module_count=structural.module_count,
            structural_min_module_pixels=structural.minimum_module_pixels,
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
        elapsed_ms=total_ms,
        timings_ms={
            "structural_inference": structural_ms,
            "payload_decode": payload_decode_ms,
            "semantic_inference": semantic_ms,
            "fusion": fusion_ms,
            "policy": policy_ms,
            "pipeline_total": total_ms,
        },
    )
