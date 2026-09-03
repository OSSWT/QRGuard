"""QRGuard backend API.

Run from the repo root:
    uvicorn app.main:app --app-dir backend --reload

Interactive docs are then at http://127.0.0.1:8000/docs

Endpoints
    GET  /health       component readiness
    POST /analyze-url  fast path: payload only, no image
    POST /scan         full path: QR image crop + decoded payload
    POST /deep-check   user-initiated LLM second opinion (never automatic)
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.pipeline import run_deep_check, run_scan
from app.schemas import (
    AnalyzeUrlRequest,
    DeepCheckRequest,
    DeepCheckResponse,
    HealthResponse,
    ScanResponse,
)

log = logging.getLogger("qrguard")
scan_log = logging.getLogger("uvicorn.error")

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_SCAN_IMAGES = 5
MAX_TOTAL_IMAGE_BYTES = 20 * 1024 * 1024
CAPTURE_QUALITY_CONDITIONS = {
    "normal",
    "overexposure",
    "underexposure",
    "motion_blur",
    "defocus_blur",
    "far_distance",
    "perspective",
    "glare",
    "shadow",
    "screen_moire_or_compression",
}
CAPTURE_QUALITY_SEVERITIES = {"none", "mild", "moderate", "severe"}
CAPTURE_ATTACK_METHODS = {
    "none",
    "eot_fgsm",
    "eot_pgd",
    "verified_physical_patch",
    "other_verified",
}
CAPTURE_MANIPULATION_METHODS = {
    "none",
    "sticker_overlay",
    "module_erasure",
    "finder_damage",
    "cut_and_paste",
    "printed_obstruction",
    "other_documented",
}


def _structural_startup_loaders():
    """Select exactly the Structural analyzers used by the request pipeline."""
    from structural.structural_service import load_analyzer as load_structural
    from structural.structural_service import load_unified_candidate_analyzer

    unified_artifacts = os.getenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "").strip()
    if unified_artifacts:
        return (
            (
                "structural-unified",
                lambda: load_unified_candidate_analyzer(unified_artifacts),
            ),
        )
    # Gallery and Camera share the active source-neutral artifact. Retain one
    # startup load so local development cannot silently select a legacy model.
    return (("structural-unified", load_structural),)


def _capture_case_context(capture_root: Path) -> dict[str, object]:
    """Read an operator-controlled case file without restarting the backend."""
    configured = os.getenv("QRGUARD_CAPTURE_CASE_FILE", "").strip()
    if not configured:
        return {}
    path = Path(configured)
    if not path.is_absolute():
        path = capture_root / path
    resolved_root = capture_root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("capture case file must stay inside QRGUARD_DUMP_SCANS") from exc
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("capture case file must contain one JSON object")
    return payload


def _capture_identifier(value: object) -> str | None:
    text = str(value or "").strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    return text if 1 <= len(text) <= 80 and set(text) <= allowed else None


def _capture_value(
    context: dict[str, object], key: str, environment_name: str, default: str
) -> str:
    return str(context.get(key) or os.getenv(environment_name, default)).strip()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Load models once at startup so the first real scan is not slow.

    Failures are logged, not fatal: /health then reports which component is down and
    the pipeline still serves whatever branch is available.
    """
    from fusion.engine import load_engine
    from semantic.semantic_service import load_analyzer as load_semantic
    for name, loader in (
        *_structural_startup_loaders(),
        ("semantic", load_semantic),
        ("fusion", load_engine),
    ):
        try:
            loader()
            log.info("loaded %s", name)
        except Exception as exc:  # noqa: BLE001 - startup must not crash on one module
            log.warning("could not load %s: %s", name, exc)
    yield


app = FastAPI(
    title="QRGuard API",
    version="0.1.0",
    description="Real-time QR code fraud detection: structural + semantic analysis "
    "fused into a Safe / Warning / Blocked verdict.",
    lifespan=lifespan,
)

# Flutter web runs on a random localhost port during VS Code development. Restrict
# browser access to loopback origins by default; production web origins are supplied
# as a comma-separated Cloud Run environment variable. Android clients do not use CORS.
cors_origins = [
    origin.strip()
    for origin in os.getenv("QRGUARD_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": "QRGuard API",
        "health": "/health",
        "docs": "/docs",
    }


def _dump_if_requested(images, payload: str | None, image_source: str, result) -> None:
    """Save anonymised runtime evidence when QRGUARD_DUMP_SCANS is set.

    The structural branch is only meaningful if it receives a crop of the code.
    A phone sends whatever its camera pipeline produced, and the difference
    between "the code" and "a photo of a room containing the code" is the
    difference between p_structural 0.0001 and 0.99. Being able to look at the
    exact bytes is the only way to tell those apart from the outside.

    Off unless the environment variable is set, so it costs nothing in normal
    runs and never writes user images by surprise.
    """
    directory = os.getenv("QRGUARD_DUMP_SCANS")
    if not directory or not images:
        return
    try:
        target = Path(directory)
        context = _capture_case_context(target)
        capture_label = _capture_value(
            context, "ground_truth", "QRGUARD_CAPTURE_LABEL", "unlabelled"
        ).lower()
        if capture_label not in {"clean", "adversarial", "tampered"}:
            capture_label = "unlabelled"
        quality_condition = _capture_value(
            context,
            "quality_condition",
            "QRGUARD_CAPTURE_QUALITY_CONDITION",
            "normal",
        ).lower()
        if quality_condition not in CAPTURE_QUALITY_CONDITIONS:
            quality_condition = "normal"
        quality_severity = _capture_value(
            context,
            "quality_severity",
            "QRGUARD_CAPTURE_QUALITY_SEVERITY",
            "none",
        ).lower()
        if quality_severity not in CAPTURE_QUALITY_SEVERITIES:
            quality_severity = "none"
        target = target / capture_label
        target.mkdir(parents=True, exist_ok=True)
        captured_at = datetime.now(timezone.utc)
        capture_session_id = uuid.uuid4().hex
        folder_case_id = (
            _capture_identifier(context.get("campaign_case_id"))
            or f"{capture_label}-unassigned"
        )
        session = target / (
            f"capture_{folder_case_id}_{image_source}_{capture_session_id[:8]}"
        ).lower()
        session.mkdir()
        for index, image in enumerate(images):
            image.convert("RGB").save(session / f"crop_{index:02d}.png")

        branch = result.branch_scores
        payload_hash = hashlib.sha256((payload or "").encode()).hexdigest()
        pair_token = _capture_value(
            context, "pair_token", "QRGUARD_CAPTURE_PAIR_ID", ""
        )
        paired_group = (
            hashlib.sha256(pair_token.encode()).hexdigest()
            if pair_token
            else payload_hash
        )
        physical_token = _capture_value(
            context,
            "physical_qr_token",
            "QRGUARD_CAPTURE_PHYSICAL_QR_ID",
            "",
        )
        physical_qr = (
            hashlib.sha256(physical_token.encode()).hexdigest()
            if physical_token
            else paired_group
        )
        attack_method = _capture_value(
            context, "attack_method", "QRGUARD_CAPTURE_ATTACK_METHOD", "none"
        ).lower()
        if attack_method not in CAPTURE_ATTACK_METHODS:
            attack_method = "none"
        attack_reference = _capture_value(
            context,
            "attack_reference_sha256",
            "QRGUARD_CAPTURE_ATTACK_REFERENCE_SHA256",
            "",
        ).lower()
        if len(attack_reference) != 64 or any(
            character not in "0123456789abcdef" for character in attack_reference
        ):
            attack_reference = ""
        manipulation_method = _capture_value(
            context,
            "manipulation_method",
            "QRGUARD_CAPTURE_MANIPULATION_METHOD",
            "none",
        ).lower()
        if manipulation_method not in CAPTURE_MANIPULATION_METHODS:
            manipulation_method = "none"
        metadata = {
            "captured_at": captured_at.isoformat(),
            "capture_session_id": capture_session_id,
            "campaign_id": _capture_identifier(context.get("campaign_id")),
            "campaign_case_id": _capture_identifier(
                context.get("campaign_case_id")
            ),
            "ground_truth": None if capture_label == "unlabelled" else capture_label,
            "payload_sha256": payload_hash,
            "paired_group_sha256": paired_group,
            "physical_qr_sha256": physical_qr,
            "image_source": image_source,
            "quality_condition": quality_condition,
            "quality_severity": quality_severity,
            "selected_frame_index": 0 if len(images) == 1 else None,
            "frame_aggregation": branch.structural_consensus,
            "frames_received": branch.structural_frames_received,
            "frames_analyzed": branch.structural_frames_analyzed,
            "device_model": _capture_value(
                context, "device_model", "QRGUARD_CAPTURE_DEVICE", "not_recorded"
            )[:80],
            "medium": _capture_value(
                context, "medium", "QRGUARD_CAPTURE_MEDIUM", "not_recorded"
            )[:80],
            "environment": _capture_value(
                context,
                "environment",
                "QRGUARD_CAPTURE_ENVIRONMENT",
                "not_recorded",
            )[:80],
            "attack_method": attack_method,
            "attack_reference_sha256": attack_reference,
            "manipulation_method": manipulation_method,
            "image_sizes": [[image.width, image.height] for image in images],
            "p_structural_effective": branch.p_structural,
            "structural_type": branch.structural_type,
            "structural_quality_status": branch.structural_quality_status,
            "structural_quality_conditions": branch.structural_quality_conditions,
            "structural_rescan_reason": branch.structural_rescan_reason,
            "structural_module_count": branch.structural_module_count,
            "structural_min_module_pixels": branch.structural_min_module_pixels,
            "payload_type": result.payload_type,
            "rule_flags": result.rule_flags,
            "verdict": result.verdict,
            "risk_score": result.risk_score,
        }
        (session / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        log.info("dumped anonymised scan evidence to %s", session)
    except Exception:  # a debugging aid must never break a scan
        log.warning("could not dump upload", exc_info=True)


def _llm_ready() -> bool:
    from semantic.llm_providers import is_configured

    return is_configured()


def _structural_health_status() -> str:
    """Report the analyzer selection that the scan pipeline will actually use."""
    from structural.structural_service import load_analyzer as load_structural
    from structural.structural_service import load_unified_candidate_analyzer

    unified_artifacts = os.getenv("QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS", "").strip()
    if unified_artifacts:
        analyzer = load_unified_candidate_analyzer(unified_artifacts)
        metadata_path = Path(unified_artifacts) / "model_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        version = str(metadata.get("version", "unknown"))
        return (
            f"unified={version}/{analyzer.model_path.name}; "
            "sources=gallery,camera"
        )

    analyzer = load_structural()
    version = analyzer.version or "active"
    return f"unified={version}/{analyzer.model_path.name}; sources=gallery,camera"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    from fusion.engine import load_engine
    from semantic.domain_reputation import list_size
    from semantic.semantic_service import load_analyzer as load_semantic

    components: dict[str, str] = {}
    for name, check in (
        ("structural", _structural_health_status),
        ("semantic", lambda: load_semantic().model_path.name),
        (
            "fusion",
            lambda: (
                f"safe<{load_engine().safe_max} blocked>={load_engine().blocked_min}"
            ),
        ),
        ("qr_decoder", lambda: f"opencv {__import__('cv2').__version__}"),
        ("domain_list", lambda: f"{list_size()} domains"),
        # Optional by design (option E): "not configured" is not a fault, so this
        # never flips overall status to degraded.
        ("deep_check", lambda: "configured" if _llm_ready() else "not configured"),
    ):
        try:
            components[name] = check()
        except Exception as exc:  # noqa: BLE001
            components[name] = f"unavailable: {type(exc).__name__}"

    status = (
        "ok"
        if not any(v.startswith("unavailable") for v in components.values())
        else "degraded"
    )
    return HealthResponse(status=status, components=components)


@app.post("/analyze-url", response_model=ScanResponse)
def analyze_url(req: AnalyzeUrlRequest) -> ScanResponse:
    """Semantic-only path — used when no image is available, or for quick testing."""
    if not req.payload.strip():
        raise HTTPException(status_code=422, detail="payload must not be empty")
    return run_scan(req.payload)


@app.post("/scan", response_model=ScanResponse)
async def scan(
    payload: str | None = Form(
        None,
        description="Decoded QR text. LEAVE THIS EMPTY to have the server decode the "
        "image for you (handy in this UI); the phone app decodes on-device "
        "and sends it.",
    ),
    image: UploadFile | None = File(None, description="QR region crop (PNG/JPEG)"),
    images: list[UploadFile] | None = File(
        None,
        description="Additional live-camera crops for bounded temporal consensus",
    ),
    image_source: str = Form(
        "unknown", description="Image acquisition source: camera, gallery, or unknown"
    ),
    camera_evidence_policy: str | None = Form(
        None,
        description="temporal_consensus_v1 requires at least three distinct Camera crops",
    ),
) -> ScanResponse:
    """Full scan: image goes to the structural branch, payload to the semantic branch."""
    route_started = time.perf_counter()
    uploads = ([image] if image is not None else []) + list(images or [])
    image_required = image_source in {"camera", "gallery"}
    if camera_evidence_policy not in {None, "", "temporal_consensus_v1"}:
        raise HTTPException(status_code=422, detail="unsupported camera evidence policy")
    if camera_evidence_policy and image_source != "camera":
        raise HTTPException(
            status_code=422,
            detail="camera evidence policy is valid only for camera scans",
        )
    if not (payload or "").strip() and not uploads:
        raise HTTPException(
            status_code=422, detail="provide a payload, an image, or both"
        )
    if image_required and not uploads:
        raise HTTPException(
            status_code=422,
            detail=f"{image_source} scans require valid QR image evidence",
        )
    if len(uploads) > MAX_SCAN_IMAGES:
        raise HTTPException(
            status_code=413, detail=f"at most {MAX_SCAN_IMAGES} images are allowed"
        )

    image_decode_started = time.perf_counter()
    pil_images = []
    total_bytes = 0
    seen_image_hashes: set[str] = set()
    for upload in uploads:
        raw = await upload.read()
        total_bytes += len(raw)
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="image too large")
        if total_bytes > MAX_TOTAL_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="combined images are too large")
        try:
            from PIL import Image

            pil_image = Image.open(io.BytesIO(raw))
            pil_image.load()
            pil_image = pil_image.convert("RGB")
            digest = hashlib.sha256()
            digest.update(pil_image.width.to_bytes(4, "big"))
            digest.update(pil_image.height.to_bytes(4, "big"))
            digest.update(pil_image.tobytes())
            image_hash = digest.hexdigest()
            if image_hash in seen_image_hashes:
                log.info("duplicate image upload ignored")
                continue
            seen_image_hashes.add(image_hash)
            pil_images.append(pil_image)
        except Exception:
            # Unknown/legacy callers may still use semantic evidence when an
            # optional upload is corrupt. Explicit camera/gallery callers are
            # rejected below so they cannot receive a misleading Partial result.
            log.warning("unreadable image upload; structural branch abstains")
            continue
    image_read_decode_ms = int(
        (time.perf_counter() - image_decode_started) * 1000
    )

    if image_required and not pil_images:
        raise HTTPException(
            status_code=422,
            detail=f"{image_source} image could not be decoded",
        )

    # Web browsers can choose a file but mobile_scanner cannot analyse that file
    # on Web. In that one payload-less Gallery path, decode and rectify server-side
    # before Structural sees the image. This prevents a whole screenshot/room from
    # being mistaken for a tampered QR and preserves the one-code contract used by
    # the native Gallery picker.
    gallery_crop_started = time.perf_counter()
    gallery_payload_decoded = False
    if image_source == "gallery" and not (payload or "").strip() and pil_images:
        from structural.qr_decoder import decode_and_crop_qrs

        detections = decode_and_crop_qrs(pil_images[0])
        if not detections:
            raise HTTPException(
                status_code=422,
                detail="No readable QR code was found in that image",
            )
        if len(detections) > 1:
            raise HTTPException(
                status_code=422,
                detail="That image contains multiple QR codes; choose an image with one",
            )
        payload, gallery_crop = detections[0]
        pil_images = [gallery_crop]
        gallery_payload_decoded = True
    gallery_decode_crop_ms = int(
        (time.perf_counter() - gallery_crop_started) * 1000
    )

    # Gallery remains a deterministic single-image path. Camera clients may send
    # a bounded temporal burst; the pipeline reports its explicit consensus and
    # abstains when fewer than three crops contain deployment-range detail.
    analysed_images = pil_images[:1] if image_source == "gallery" else pil_images
    result = run_scan(
        payload,
        image_source=image_source,
        images=analysed_images,
        image_expected=bool(uploads),
        payload_was_decoded=gallery_payload_decoded,
        require_camera_consensus=camera_evidence_policy == "temporal_consensus_v1",
    )
    result.timings_ms = {
        "image_read_decode": image_read_decode_ms,
        "gallery_decode_crop": gallery_decode_crop_ms,
        **result.timings_ms,
        "server_total": int((time.perf_counter() - route_started) * 1000),
    }
    _dump_if_requested(analysed_images, payload, image_source, result)
    branch = result.branch_scores
    # Deliberately omit the payload and domain: this is enough to diagnose a
    # camera/gallery mismatch without putting scanned destinations in logs.
    scan_log.info(
        "scan result source=%s structural_raw=%s structural_effective=%s "
        "structural_type=%s semantic=%s verdict=%s risk=%d",
        branch.image_source,
        _score_for_log(branch.p_structural_raw),
        _score_for_log(branch.p_structural),
        branch.structural_type,
        _score_for_log(branch.p_url),
        result.verdict,
        result.risk_score,
    )
    return result


def _score_for_log(value: float | None) -> str:
    return "none" if value is None else f"{value:.3f}"


@app.post("/deep-check", response_model=DeepCheckResponse)
async def deep_check(req: DeepCheckRequest) -> DeepCheckResponse:
    """User-initiated LLM second opinion (option E).

    Never called automatically: measurement showed fusion already suppresses Method 1's
    false positives from ~25% to ~2%, so an always-on LLM pass was not worth its latency
    and cost. The user taps "check this link in depth" on a Warning/Blocked screen, and
    this endpoint expands the redirect chain and reasons over the result.
    """
    if not req.payload.strip():
        raise HTTPException(status_code=422, detail="payload must not be empty")
    return await run_deep_check(
        req.payload,
        p_structural=req.p_structural,
        expand_redirects=req.expand_redirects,
    )
