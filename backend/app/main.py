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
from contextlib import asynccontextmanager
from datetime import datetime
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Load models once at startup so the first real scan is not slow.

    Failures are logged, not fatal: /health then reports which component is down and
    the pipeline still serves whatever branch is available.
    """
    from fusion.engine import load_engine
    from semantic.semantic_service import load_analyzer as load_semantic
    from structural.structural_service import load_analyzer as load_structural
    from structural.structural_service import (
        load_camera_analyzer as load_camera_structural,
    )

    for name, loader in (
        ("structural", load_structural),
        ("structural-camera", load_camera_structural),
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
        capture_label = os.getenv("QRGUARD_CAPTURE_LABEL", "unlabelled").lower()
        if capture_label not in {"clean", "adversarial", "tampered"}:
            capture_label = "unlabelled"
        target = target / capture_label
        target.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        session = target / f"scan_{stamp}"
        session.mkdir()
        for index, image in enumerate(images):
            image.convert("RGB").save(session / f"crop_{index:02d}.png")

        branch = result.branch_scores
        metadata = {
            "captured_at": datetime.now().astimezone().isoformat(),
            "ground_truth": None if capture_label == "unlabelled" else capture_label,
            "payload_sha256": hashlib.sha256((payload or "").encode()).hexdigest(),
            "image_source": image_source,
            "image_sizes": [[image.width, image.height] for image in images],
            "p_structural_effective": branch.p_structural,
            "structural_type": branch.structural_type,
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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    from fusion.engine import load_engine
    from semantic.domain_reputation import list_size
    from semantic.semantic_service import load_analyzer as load_semantic
    from structural.structural_service import load_analyzer as load_structural
    from structural.structural_service import (
        load_camera_analyzer as load_camera_structural,
    )

    components: dict[str, str] = {}
    for name, check in (
        (
            "structural",
            lambda: (
                f"gallery=RUN5/{load_structural().model_path.name}; "
                "camera=structural-2026.02/"
                f"{load_camera_structural().model_path.name}"
            ),
        ),
        ("semantic", lambda: load_semantic().model_path.name),
        (
            "fusion",
            lambda: (
                f"safe<{load_engine().safe_max} blocked>={load_engine().blocked_min}"
            ),
        ),
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
        description="Legacy live-camera crops; only the first usable crop is analysed",
    ),
    image_source: str = Form(
        "unknown", description="Image acquisition source: camera, gallery, or unknown"
    ),
) -> ScanResponse:
    """Full scan: image goes to the structural branch, payload to the semantic branch."""
    uploads = ([image] if image is not None else []) + list(images or [])
    if not (payload or "").strip() and not uploads:
        raise HTTPException(
            status_code=422, detail="provide a payload, an image, or both"
        )
    if len(uploads) > MAX_SCAN_IMAGES:
        raise HTTPException(
            status_code=413, detail=f"at most {MAX_SCAN_IMAGES} images are allowed"
        )

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
            # A corrupt upload must not fail the whole scan: the structural branch
            # abstains and the response is marked partial_analysis.
            log.warning("unreadable image upload; structural branch abstains")
            continue

    # Camera and gallery share one Structural contract. New clients upload only
    # the clearest selected crop; for legacy multi-frame clients, preserve order
    # and analyse the first usable crop rather than applying hidden consensus.
    analysed_images = pil_images[:1]
    result = run_scan(
        payload,
        image_source=image_source,
        images=analysed_images,
        image_expected=bool(uploads),
    )
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
