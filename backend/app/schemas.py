"""API request/response schemas.

These are the contract between the Flutter app and the backend. Field names mirror the
internal signal names so a response can be traced straight back to the module that
produced it.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Verdict = Literal["safe", "warning", "blocked"]
AnalysisStatus = Literal["completed", "not_applicable", "unavailable", "inconclusive"]


class BranchScores(BaseModel):
    """Per-branch signals, surfaced for transparency and debugging."""

    p_structural: Optional[float] = Field(
        None, description="Structural evidence used by fusion; null if it abstained"
    )
    structural_status: AnalysisStatus = Field(
        "not_applicable",
        description="Whether image-integrity analysis completed, did not apply, "
        "or was unavailable",
    )
    p_structural_raw: Optional[float] = Field(
        None, description="Raw 1 - P(clean) from the image CNN before source handling"
    )
    structural_type: Optional[str] = Field(
        None, description="clean | adversarial | tampered"
    )
    structural_quality_status: Optional[str] = Field(
        None, description="usable | marginal | unusable for the unified candidate"
    )
    structural_quality_conditions: list[str] = Field(default_factory=list)
    structural_rescan_reason: Optional[str] = None
    structural_frames_received: int = Field(0, ge=0, le=5)
    structural_frames_analyzed: int = Field(0, ge=0, le=5)
    structural_consensus: Optional[str] = Field(
        None,
        description="single_frame | median_score_majority_class | insufficient_quality",
    )
    p_url: Optional[float] = Field(
        None, description="phishing probability from Method 1; null if not a URL"
    )
    semantic_status: AnalysisStatus = Field(
        "not_applicable",
        description="Whether the URL model completed; non-URL payloads are not_applicable",
    )
    llm_score: Optional[float] = Field(
        None, description="Method 2 verdict mapped to 0-1; null unless deep check ran"
    )
    domain_unknown: Optional[float] = Field(
        None, description="1 when the registered domain is not widely recognised"
    )
    image_source: Literal["camera", "gallery", "unknown"] = "unknown"


class ScanResponse(BaseModel):
    verdict: Verdict
    risk_score: int = Field(..., ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    payload_type: str
    normalized_url: Optional[str] = None
    registered_domain: Optional[str] = None
    rule_flags: list[str] = Field(default_factory=list)
    branch_scores: BranchScores
    partial_analysis: bool = Field(
        False,
        description="true only when an expected branch was unavailable or inconclusive; "
        "not_applicable is a complete result",
    )
    deep_check_available: bool = Field(
        False, description="true when POST /deep-check can add an LLM second opinion"
    )
    payload: Optional[str] = Field(None, description="the payload actually analysed")
    payload_source: Literal["provided", "decoded", "undecodable"] = Field(
        "provided",
        description="'decoded' = read from the image server-side; 'undecodable' = the "
        "image could not be read, so the semantic branch abstained",
    )
    elapsed_ms: int
    timings_ms: dict[str, int] = Field(
        default_factory=dict,
        description="Privacy-safe stage timings; contains no payload or image data",
    )


class AnalyzeUrlRequest(BaseModel):
    payload: str = Field(..., description="decoded QR payload (usually a URL)")


class DeepCheckRequest(BaseModel):
    """User-initiated second opinion. Never called automatically."""

    payload: str = Field(..., description="decoded QR payload")
    p_structural: Optional[float] = Field(
        None, description="carry over from /scan so the verdict can be recomputed"
    )
    expand_redirects: bool = Field(
        True, description="follow the redirect chain before reasoning (HEAD-only)"
    )


class DeepCheckResponse(BaseModel):
    """Result of the LLM analysis, plus the re-fused verdict."""

    llm_verdict: Literal["benign", "suspicious", "phishing"]
    llm_confidence: float
    explanation: str
    risk_factors: list[str] = Field(default_factory=list)

    # Behavioural evidence gathered for the LLM, also shown to the user.
    final_url: Optional[str] = None
    redirect_chain: list[str] = Field(default_factory=list)
    redirect_blocked_reason: Optional[str] = None

    # Verdict after folding the LLM opinion back into fusion.
    verdict: Verdict
    risk_score: int = Field(..., ge=0, le=100)
    previous_risk_score: int = Field(..., ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)

    llm_available: bool = True
    error: Optional[str] = None
    elapsed_ms: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    components: dict[str, str]
