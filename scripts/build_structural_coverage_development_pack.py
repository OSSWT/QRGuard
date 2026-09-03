"""Build balanced low/medium/high-Version development references for Structural.

The 48 cases cross 16 pristine QR identities with clean, verified gradient-based
EOT attacks and documented sticker-overlay variants.  Every class contains all
three Version and payload-length bands, and every mask appears exactly twice.
This pack is development data only; a fresh blinded holdout is still required
after training.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import qrcode
from PIL import Image
from qrcode.constants import ERROR_CORRECT_H

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_qr_codes_demo import _build_card
from scripts.prepare_scoped_capture_references import (
    ATTACK_SIZE,
    DISPLAY_SIZE,
    _attack_array,
    _eot_views,
    _load_victim,
    _normalise,
    _write_tampered,
)

PACK_ID = "structural-coverage-development-2026-09-r01"
DEFAULT_OUTPUT = ROOT / "dist/Structural_Coverage_Development_2026-09-r01"
DEFAULT_APP_PLAN = ROOT / "app/assets/capture/structural_coverage_development_plan.json"
DEFAULT_ARCHIVE = (
    ROOT.parent
    / "90_Rebuildable_Caches/Structural_Coverage_Development_2026-09-r01.zip"
)


@dataclass(frozen=True)
class BaseSpec:
    base_id: str
    qr_version: int
    module_count: int
    mask_pattern: int
    version_band: str
    payload_length_bin: str
    payload: str
    development_split: str


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    label: str
    label_code: str
    base: BaseSpec
    attack_profile: str = "automatic"


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _payload(
    base_number: int, target_bytes: int, namespace: str = "coverage-payload"
) -> str:
    prefix_tag = "CVG" if namespace == "coverage-payload" else "BLD"
    prefix = f"QRG-{prefix_tag}-{base_number:02d}-"
    if len(prefix) > target_bytes:
        raise ValueError("payload prefix exceeds requested byte length")
    digest = hashlib.sha256(f"{namespace}:{base_number}".encode()).hexdigest()
    required = target_bytes - len(prefix)
    return prefix + (digest * ((required + len(digest) - 1) // len(digest)))[:required]


def base_specs() -> tuple[BaseSpec, ...]:
    # Five low + five medium + six high identities.  Across the 16 identities,
    # every mask occurs exactly twice.  The last identity in low/medium and the
    # last two in high are validation-only; parent identities never cross splits.
    assignments = (
        *(
            (
                3,
                mask,
                "low_v1_v3",
                "short_1_32",
                24,
                "validation" if mask == 4 else "train",
            )
            for mask in range(5)
        ),
        *(
            (
                5,
                mask,
                "medium_v4_v6",
                "medium_33_96",
                40,
                "validation" if mask == 1 else "train",
            )
            for mask in (5, 6, 7, 0, 1)
        ),
        *(
            (
                10,
                mask,
                "high_v7_plus",
                "long_97_plus",
                112,
                "validation" if mask in {6, 7} else "train",
            )
            for mask in (2, 3, 4, 5, 6, 7)
        ),
    )
    return tuple(
        BaseSpec(
            base_id=f"CVG-BASE-{index:02d}",
            qr_version=version,
            module_count=17 + 4 * version,
            mask_pattern=mask,
            version_band=band,
            payload_length_bin=length_bin,
            payload=_payload(index, target_bytes),
            development_split=split,
        )
        for index, (version, mask, band, length_bin, target_bytes, split) in enumerate(
            assignments, start=1
        )
    )


def case_specs() -> tuple[CaseSpec, ...]:
    labels = (
        ("clean", "CLN"),
        ("adversarial", "ADV"),
        ("tampered", "TMP"),
    )
    return tuple(
        CaseSpec(
            case_id=f"CVG-{code}-V{base.qr_version:02d}-M{base.mask_pattern}-{base.base_id[-2:]}",
            label=label,
            label_code=code,
            base=base,
        )
        for base in base_specs()
        for label, code in labels
    )


def _matrix_sha256(matrix: list[list[bool]]) -> str:
    bits = "".join("1" if value else "0" for row in matrix for value in row)
    return _sha256_bytes(bits.encode("ascii"))


def _pristine_qr(base: BaseSpec) -> tuple[Image.Image, dict[str, Any]]:
    qr = qrcode.QRCode(
        version=base.qr_version,
        error_correction=ERROR_CORRECT_H,
        border=4,
        box_size=1,
        mask_pattern=base.mask_pattern,
    )
    qr.add_data(base.payload, optimize=0)
    qr.make(fit=False)
    matrix = [list(row) for row in qr.modules]
    if len(matrix) != base.module_count:
        raise RuntimeError(f"module count mismatch for {base.base_id}")
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    image = image.resize((DISPLAY_SIZE, DISPLAY_SIZE), Image.Resampling.NEAREST)
    dark = sum(sum(row) for row in matrix)
    return image, {
        "qr_matrix_sha256": _matrix_sha256(matrix),
        "dark_module_ratio": round(dark / (len(matrix) ** 2), 6),
    }


def _decode(path: Path, detector: cv2.QRCodeDetector) -> str:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return ""
    payload, _, _ = detector.detectAndDecode(image)
    return payload


def _attack_projection(module_count: int, mode: str) -> np.ndarray:
    if mode == "full":
        return np.ones((ATTACK_SIZE, ATTACK_SIZE, 1), dtype=np.float32)
    total_modules = module_count + 8
    coordinates = (np.arange(ATTACK_SIZE, dtype=np.float32) + 0.5) * (
        total_modules / ATTACK_SIZE
    )
    grid_x, grid_y = np.meshgrid(coordinates, coordinates)
    inside = (
        (grid_x >= 4)
        & (grid_x < total_modules - 4)
        & (grid_y >= 4)
        & (grid_y < total_modules - 4)
    )
    module_x = grid_x - 4
    module_y = grid_y - 4
    finder = (
        ((module_x < 9) & (module_y < 9))
        | ((module_x >= module_count - 9) & (module_y < 9))
        | ((module_x < 9) & (module_y >= module_count - 9))
    )
    allowed = inside & ~finder
    if mode == "module_interiors":
        fraction_x = grid_x - np.floor(grid_x)
        fraction_y = grid_y - np.floor(grid_y)
        allowed &= (
            (fraction_x >= 0.16)
            & (fraction_x <= 0.84)
            & (fraction_y >= 0.16)
            & (fraction_y <= 0.84)
        )
    return allowed[:, :, None].astype(np.float32)


def _screen_camera_eot_views(tensor: Any) -> Any:
    """Deterministic differentiable views for display-to-camera survival.

    The transforms cover resampling, mild defocus, luminance/contrast/gamma
    changes and sub-pixel-equivalent shifts.  They deliberately avoid random
    state so reference generation can be reproduced and audited.
    """

    import torch
    from torch.nn import functional

    settings = (
        # brightness offset, contrast, gamma, inner size, blur kernel, y/x shift
        (0.00, 1.00, 1.00, 224, 1, 0, 0),
        (0.06, 0.92, 0.90, 208, 1, 2, -2),
        (-0.06, 1.08, 1.10, 208, 1, -2, 2),
        (0.04, 0.88, 0.92, 192, 3, 1, 3),
        (-0.04, 1.12, 1.08, 192, 3, -3, -1),
        (0.08, 0.84, 0.86, 176, 3, 2, 2),
        (-0.08, 1.16, 1.14, 176, 3, -2, -2),
        (0.02, 0.94, 0.96, 160, 3, 3, -1),
        (-0.02, 1.06, 1.04, 160, 3, -1, 3),
        (0.05, 0.90, 0.90, 144, 5, 1, -3),
        (-0.05, 1.10, 1.10, 144, 5, -3, 1),
        (0.00, 1.00, 1.00, 184, 5, 2, -2),
    )
    variants = []
    for offset, contrast, gamma, inner_size, blur, shift_y, shift_x in settings:
        view = tensor.clamp(0, 1).pow(gamma)
        view = (view - 0.5) * contrast + 0.5 + offset
        if inner_size != ATTACK_SIZE:
            view = functional.interpolate(
                view,
                size=(inner_size, inner_size),
                mode="bilinear",
                align_corners=False,
            )
            view = functional.interpolate(
                view,
                size=(ATTACK_SIZE, ATTACK_SIZE),
                mode="bilinear",
                align_corners=False,
            )
        if blur > 1:
            view = functional.avg_pool2d(
                view, kernel_size=blur, stride=1, padding=blur // 2
            )
        view = torch.roll(view, shifts=(shift_y, shift_x), dims=(2, 3))
        variants.append(view.clamp(0, 1))
    return torch.cat(variants)


def _write_decodable_adversarial(
    source: Path,
    destination: Path,
    expected_payload: str,
    module_count: int,
    detector: cv2.QRCodeDetector,
    victim: Any,
    attack_profile: str = "automatic",
) -> dict[str, Any]:
    """Build an EOT attack and verify both attack and QR decode contracts."""

    import torch
    from torch.nn import functional

    original_image = (
        Image.open(source)
        .convert("RGB")
        .resize((ATTACK_SIZE, ATTACK_SIZE), Image.Resampling.BILINEAR)
    )
    original = np.asarray(original_image, dtype=np.float32)
    original_tensor = (
        torch.from_numpy(original.transpose(2, 0, 1)).float().unsqueeze(0) / 255.0
    )
    robust_v2 = attack_profile in {
        "screen_camera_robust_v2_function",
        "screen_camera_robust_v2_alternate",
    }
    device = next(victim.parameters()).device
    original_tensor = original_tensor.to(device)
    eot_views = _screen_camera_eot_views if robust_v2 else _eot_views
    if robust_v2:
        with torch.no_grad():
            baseline_label = int(
                victim(_normalise(original_tensor)).argmax(1).item()
            )
            baseline_predictions = victim(
                _normalise(eot_views(original_tensor))
            ).argmax(1)
            baseline_consistency = float(
                (baseline_predictions == baseline_label).float().mean().item()
            )
        gradient_source = original_tensor.detach().clone().requires_grad_(True)
        labels = torch.full(
            (eot_views(gradient_source).shape[0],),
            baseline_label,
            dtype=torch.long,
            device=device,
        )
        loss = functional.cross_entropy(
            victim(_normalise(eot_views(gradient_source))), labels
        )
        gradient = torch.autograd.grad(loss, gradient_source)[0].sign()
        attacked = (
            (original_tensor + (32.0 / 255.0) * gradient)
            .clamp(0, 1)[0]
            .detach()
            .cpu()
            .numpy()
            .transpose(1, 2, 0)
            * 255
        ).round().astype(np.uint8)
        initial = {
            "victim_baseline_class": baseline_label,
            "victim_baseline_consistency": baseline_consistency,
        }
    else:
        attacked, initial = _attack_array(source, victim)
    gradient_sign = np.sign(attacked.astype(np.float32) - original)
    baseline_label = int(initial["victim_baseline_class"])
    required_success_rate = 0.75 if robust_v2 else 0.5
    eot_transform_count = 12 if robust_v2 else 6
    attempts: list[dict[str, Any]] = []

    def verify_candidate(
        candidate_array: np.ndarray,
    ) -> tuple[float, list[tuple[str, Image.Image]]]:
        tensor = (
            torch.from_numpy(candidate_array.transpose(2, 0, 1)).float().unsqueeze(0)
            / 255.0
        ).to(device)
        with torch.no_grad():
            predictions = victim(_normalise(eot_views(tensor))).argmax(1)
        success_rate = float((predictions != baseline_label).float().mean().item())
        decoded_displays: list[tuple[str, Image.Image]] = []
        for interpolation in (
            Image.Resampling.NEAREST,
            Image.Resampling.BILINEAR,
        ):
            display = Image.fromarray(candidate_array).resize(
                (DISPLAY_SIZE, DISPLAY_SIZE), interpolation
            )
            display_bgr = cv2.cvtColor(np.asarray(display), cv2.COLOR_RGB2BGR)
            decoded, _, _ = detector.detectAndDecode(display_bgr)
            if decoded == expected_payload:
                decoded_displays.append((interpolation.name.lower(), display))
        return success_rate, decoded_displays

    def successful_result(
        *,
        method: str,
        epsilon_pixels: int,
        projection_name: str,
        success_rate: float,
        decoded_displays: list[tuple[str, Image.Image]],
        iterations: int,
    ) -> dict[str, Any] | None:
        if success_rate < required_success_rate or not decoded_displays:
            return None
        interpolation_name, display = decoded_displays[0]
        display.save(destination)
        return {
            "method": method,
            "epsilon_pixels": epsilon_pixels,
            "epsilon_linf": epsilon_pixels / 255.0,
            "iterations": iterations,
            "eot_transform_count": eot_transform_count,
            "eot_suite": "screen_camera_v2" if robust_v2 else "baseline_v1",
            "required_eot_success_rate": required_success_rate,
            "generation_device": str(device),
            "victim_baseline_class": baseline_label,
            "victim_baseline_consistency": initial["victim_baseline_consistency"],
            "verified_eot_success_rate": success_rate,
            "projection": projection_name,
            "decoder_verified": True,
            "display_size": DISPLAY_SIZE,
            "resize_interpolation": interpolation_name,
        }

    fgsm_profiles = {
        "automatic": (
            ("function_safe", "module_interiors", "full"),
            (8, 12, 16, 20, 24, 32),
        ),
        "screen_robust_fgsm_function": (("function_safe",), (32,)),
        "screen_robust_fgsm_module": (("module_interiors",), (32,)),
        "screen_robust_fgsm_full": (("full",), (32,)),
        "screen_robust_function": (("function_safe",), (32, 24)),
        "screen_robust_alternate": (
            ("full", "module_interiors"),
            (32, 24),
        ),
        "screen_camera_robust_v2_function": (
            ("function_safe", "module_interiors"),
            (32, 28, 24),
        ),
        "screen_camera_robust_v2_alternate": (
            ("module_interiors", "full"),
            (32, 28, 24),
        ),
    }
    if attack_profile not in fgsm_profiles:
        raise ValueError(f"unknown adversarial attack profile: {attack_profile}")
    fgsm_projections, fgsm_epsilons = fgsm_profiles[attack_profile]
    for projection_name in fgsm_projections:
        projection_mode = (
            "module_interiors" if projection_name == "module_interiors" else "full"
        )
        projection = _attack_projection(module_count, projection_mode)
        if projection_name == "function_safe":
            projection = _attack_projection(module_count, "function_safe")
        for epsilon_pixels in fgsm_epsilons:
            candidate = (
                np.clip(original + epsilon_pixels * gradient_sign * projection, 0, 255)
                .round()
                .astype(np.uint8)
            )
            success_rate, decoded_displays = verify_candidate(candidate)
            result = successful_result(
                method="eot_fgsm_qr_function_projection",
                epsilon_pixels=epsilon_pixels,
                projection_name=projection_name,
                success_rate=success_rate,
                decoded_displays=decoded_displays,
                iterations=1,
            )
            if result is not None:
                return {**result, "attack_profile": attack_profile}
            attempts.append(
                {
                    "method": "eot_fgsm_qr_function_projection",
                    "projection": projection_name,
                    "epsilon_pixels": epsilon_pixels,
                    "verified_eot_success_rate": success_rate,
                    "decoded_interpolations": [name for name, _ in decoded_displays],
                }
            )

    # Low-Version layouts can be locally insensitive to a one-step update.
    # Iterative PGD stays inside the same L-infinity bound and projection masks.
    pgd_profiles = {
        "automatic": (
            ("module_interiors", "function_safe", "full"),
            (24, 32),
        ),
        "screen_robust_function": (("function_safe",), (32, 24)),
        "screen_robust_alternate": (
            ("full", "module_interiors"),
            (32, 24),
        ),
        "screen_camera_robust_v2_function": (
            ("function_safe", "module_interiors"),
            (32, 28, 24),
        ),
        "screen_camera_robust_v2_alternate": (
            ("module_interiors", "full"),
            (32, 28, 24),
        ),
    }
    pgd_projections, pgd_epsilons = pgd_profiles.get(attack_profile, ((), ()))
    for projection_name in pgd_projections:
        projection = _attack_projection(module_count, projection_name)
        projection_tensor = torch.from_numpy(projection.transpose(2, 0, 1)).float()
        projection_tensor = projection_tensor.unsqueeze(0).to(device)
        for epsilon_pixels in pgd_epsilons:
            epsilon = epsilon_pixels / 255.0
            candidate_tensor = original_tensor.detach().clone()
            iterations = 20 if robust_v2 else 12
            step_pixels = 3.0 if robust_v2 else 4.0
            for _ in range(iterations):
                candidate_tensor.requires_grad_(True)
                labels = torch.full(
                    (eot_views(candidate_tensor).shape[0],),
                    baseline_label,
                    dtype=torch.long,
                    device=device,
                )
                loss = functional.cross_entropy(
                    victim(_normalise(eot_views(candidate_tensor))), labels
                )
                gradient = torch.autograd.grad(loss, candidate_tensor)[0]
                with torch.no_grad():
                    candidate_tensor = candidate_tensor + (
                        (step_pixels / 255.0) * gradient.sign() * projection_tensor
                    )
                    delta = (candidate_tensor - original_tensor).clamp(
                        -epsilon, epsilon
                    )
                    candidate_tensor = (original_tensor + delta).clamp(0, 1)
            candidate = (
                (
                    candidate_tensor[0]
                    .detach()
                    .cpu()
                    .numpy()
                    .transpose(1, 2, 0)
                    .clip(0, 1)
                    * 255
                )
                .round()
                .astype(np.uint8)
            )
            success_rate, decoded_displays = verify_candidate(candidate)
            result = successful_result(
                method="eot_pgd_qr_function_projection",
                epsilon_pixels=epsilon_pixels,
                projection_name=projection_name,
                success_rate=success_rate,
                decoded_displays=decoded_displays,
                iterations=iterations,
            )
            if result is not None:
                return {**result, "attack_profile": attack_profile}
            attempts.append(
                {
                    "method": "eot_pgd_qr_function_projection",
                    "projection": projection_name,
                    "epsilon_pixels": epsilon_pixels,
                    "verified_eot_success_rate": success_rate,
                    "decoded_interpolations": [name for name, _ in decoded_displays],
                }
            )
    raise RuntimeError(
        f"no decodable verified EOT attack for {source}; "
        f"attempts={json.dumps(attempts, separators=(',', ':'))}"
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _capture_order_rows(
    rows: list[dict[str, Any]], *, is_blind: bool
) -> list[dict[str, Any]]:
    if not is_blind:
        return rows
    return [
        {
            "order": row["order"],
            "case_id": row["case_id"],
            "card_path": row["card_path"],
        }
        for row in rows
    ]


def _capture_plan(
    rows: list[dict[str, Any]],
    *,
    pack_id: str = PACK_ID,
    evidence_role: str = "development_train_or_validation_only",
) -> dict[str, Any]:
    is_blind = evidence_role == "blind_holdout"
    return {
        "schema_version": 1,
        "campaign_id": pack_id,
        "frames_per_session": 5,
        "repeats_per_distance": 1,
        "distances": [
            {
                "id": "screen-80",
                "label": "Screen 80%",
                "instruction": (
                    "Keep the viewer at 80% and hold display brightness, camera "
                    "distance and angle constant for the full "
                    f"{'blinded' if is_blind else 'development'} pass."
                ),
                "metadata": {
                    "capture_medium": "screen",
                    "screen_scale_percent": 80,
                    "role": evidence_role,
                },
            }
        ],
        "privacy": {
            "raw_payload_stored": False,
            "payload_identifier": "sha256 of on-device decoded text",
        },
        "cases": [
            {
                "case_id": row["case_id"],
                "label": (
                    f"{row['case_id']} - blinded acceptance case"
                    if is_blind
                    else f"{row['case_id']} - {row['label']} - "
                    f"V{row['qr_version']} mask {row['mask_pattern']}"
                ),
                "ground_truth": row["label"],
                "expected_payload_sha256": row["payload_sha256"],
                "instruction": (
                    f"Display only {row['card_path']} at 80%, then collect the "
                    "automatic five-frame burst. Do not skip or reorder cases."
                    if is_blind
                    else f"Display only {row['card_path']} at 80%, then collect the "
                    "automatic five-frame burst."
                ),
                "metadata": {
                    "base_identity": row["base_id"],
                    "development_split": row["development_split"],
                    "deployment_holdout_eligible": is_blind,
                    "qr_version": row["qr_version"],
                    "module_count": row["module_count"],
                    "mask_pattern": row["mask_pattern"],
                    "version_band": row["version_band"],
                    "payload_length_bin": row["payload_length_bin"],
                    "payload_utf8_bytes": row["payload_utf8_bytes"],
                    "qr_matrix_sha256": row["qr_matrix_sha256"],
                    "reference_image_sha256": row["card_sha256"],
                    "attack_method": row["attack_method"],
                    "attack_reference_sha256": row["attack_reference_sha256"],
                    "attack_profile": row.get("attack_profile", "none"),
                    "epsilon_pixels": row.get("epsilon_pixels"),
                    "projection": row.get("projection"),
                    "verified_eot_success_rate": row.get("verified_eot_success_rate"),
                    "manipulation_method": row["manipulation_method"],
                    "case_identity_source": (
                        "generator_assigned_after_candidate_freeze; opaque random "
                        "order; no operator case selection"
                        if is_blind
                        else "operator_selection_plus_payload_hash; the three class "
                        "variants share a base payload"
                    ),
                },
            }
            for row in rows
        ],
    }


def _validate_distribution(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 48:
        raise RuntimeError(f"expected 48 cases, got {len(rows)}")
    for label in ("clean", "adversarial", "tampered"):
        selected = [row for row in rows if row["label"] == label]
        if len(selected) != 16:
            raise RuntimeError(f"{label} count mismatch")
        bands = Counter(row["version_band"] for row in selected)
        if bands != {"low_v1_v3": 5, "medium_v4_v6": 5, "high_v7_plus": 6}:
            raise RuntimeError(f"{label} Version band imbalance: {bands}")
        masks = Counter(row["mask_pattern"] for row in selected)
        if masks != {mask: 2 for mask in range(8)}:
            raise RuntimeError(f"{label} mask imbalance: {masks}")


def _readme(evidence_role: str = "development_train_or_validation_only") -> str:
    if evidence_role == "blind_holdout":
        return """# Structural QR coverage blinded acceptance pack

This pack contains 48 generator-assigned cases created after the candidate was
frozen. Case names and capture order do not disclose their Structural class.
The identities must never be used for training, threshold selection or case
selection. Capture all cards once at screen 80%, in the supplied order, with
the same display, brightness, distance and angle.

The collector automatically saves five rectified crops after verifying the
on-device decoded payload hash. Export one diagnostic ZIP only after 48/48
sessions are complete. Do not inspect MANIFEST.json before capture.
"""
    return """# Structural QR coverage development pack

This pack contains 48 development cases: 16 controlled QR identities crossed
with clean, verified gradient-based EOT adversarial and documented
sticker-overlay tampered variants. Every class has five V3, five V5 and six V10 cases; masks
0-7 each occur twice per class. Payloads cover short, medium and long byte bins.

Capture every card once at screen 80%. The collector automatically stores five
rectified crops. Keep screen, brightness, distance and angle fixed. Export the
single diagnostic ZIP after 48/48 sessions are complete.

These identities are assigned to development train/validation only. They must
not be reported as a deployment holdout. After the Structural candidate is
frozen, a fresh unseen pack is required for M8 blind acceptance.
"""


def build_pack(
    output: Path,
    app_plan: Path,
    archive: Path,
    victim_checkpoint: Path,
    *,
    specs: tuple[CaseSpec, ...] | None = None,
    pack_id: str = PACK_ID,
    evidence_role: str = "development_train_or_validation_only",
    distribution_validator: Callable[[list[dict[str, Any]]], None] | None = None,
    readme_text: str | None = None,
    candidate_model_sha256: str | None = None,
) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {output}")
    cards = output / "cards"
    raw = output / "raw_references"
    cards.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    detector = cv2.QRCodeDetector()
    victim = None
    victim_hash = _sha256(victim_checkpoint)
    base_images: dict[str, tuple[Path, dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []

    selected_specs = specs or case_specs()
    is_blind = evidence_role == "blind_holdout"
    for index, spec in enumerate(selected_specs, start=1):
        base = spec.base
        if base.base_id not in base_images:
            pristine, matrix = _pristine_qr(base)
            base_path = raw / f"{base.base_id}.png"
            pristine.save(base_path, optimize=True)
            if _decode(base_path, detector) != base.payload:
                raise RuntimeError(f"pristine decode failed: {base.base_id}")
            base_images[base.base_id] = (base_path, matrix)
        base_path, matrix = base_images[base.base_id]
        reference = raw / f"{spec.case_id}.png"
        provenance: dict[str, Any]
        if spec.label == "clean":
            Image.open(base_path).save(reference, optimize=True)
            provenance = {
                "attack_method": "none",
                "attack_reference_sha256": "",
                "manipulation_method": "none",
                "decoder_verified": True,
            }
        elif spec.label == "adversarial":
            if victim is None:
                victim = _load_victim(victim_checkpoint)
            import torch

            robust_v2 = spec.attack_profile in {
                "screen_camera_robust_v2_function",
                "screen_camera_robust_v2_alternate",
            }
            generation_device = torch.device(
                "cuda" if robust_v2 and torch.cuda.is_available() else "cpu"
            )
            victim = victim.to(generation_device)
            attack = _write_decodable_adversarial(
                base_path,
                reference,
                base.payload,
                base.module_count,
                detector,
                victim,
                spec.attack_profile,
            )
            provenance = {
                "attack_method": attack["method"],
                "attack_reference_sha256": _sha256(reference),
                "manipulation_method": "none",
                "victim_checkpoint_sha256": victim_hash,
                **attack,
            }
        else:
            tamper = _write_tampered(
                base_path, reference, base.payload, spec.case_id, detector
            )
            provenance = {
                "attack_method": "none",
                "attack_reference_sha256": "",
                "manipulation_method": "sticker_overlay",
                **tamper,
            }
        if _decode(reference, detector) != base.payload:
            raise RuntimeError(f"final reference decode failed: {spec.case_id}")
        card_path = cards / f"{spec.case_id}.png"
        decoded = _build_card(
            Image.open(reference).convert("RGB"),
            card_path,
            case_id=spec.case_id,
            title=(
                f"BLINDED ACCEPTANCE CASE {index:02d}"
                if is_blind
                else f"{spec.label.upper()} - V{base.qr_version} - "
                f"MASK {base.mask_pattern}"
            ),
            expected=(
                "CAPTURE ALL CASES"
                if is_blind
                else "SAFE"
                if spec.label == "clean"
                else "BLOCKED"
            ),
            condition=(
                "blinded acceptance screen 80%"
                if is_blind
                else "coverage development screen 80%"
            ),
            note=(
                "Do not skip or reorder"
                if is_blind
                else f"{base.version_band}; {base.payload_length_bin}"
            ),
        )
        if decoded != base.payload:
            raise RuntimeError(f"card payload changed: {spec.case_id}")
        rows.append(
            {
                "order": index,
                "case_id": spec.case_id,
                "label": spec.label,
                "base_id": base.base_id,
                "development_split": base.development_split,
                "deployment_holdout_eligible": is_blind,
                "qr_version": base.qr_version,
                "module_count": base.module_count,
                "mask_pattern": base.mask_pattern,
                "version_band": base.version_band,
                "payload_length_bin": base.payload_length_bin,
                "payload_utf8_bytes": len(base.payload.encode("utf-8")),
                "payload_sha256": _sha256_bytes(base.payload.encode("utf-8")),
                "qr_matrix_sha256": matrix["qr_matrix_sha256"],
                "dark_module_ratio": matrix["dark_module_ratio"],
                "reference_path": reference.relative_to(output).as_posix(),
                "reference_sha256": _sha256(reference),
                "card_path": card_path.relative_to(output).as_posix(),
                "card_sha256": _sha256(card_path),
                **provenance,
            }
        )
        if index % 8 == 0:
            print(f"built {index}/{len(selected_specs)} cases", flush=True)

    (distribution_validator or _validate_distribution)(rows)
    manifest = {
        "schema_version": 1,
        "pack_id": pack_id,
        "purpose": (
            "fresh blinded physical deployment acceptance; never training"
            if is_blind
            else "development train/validation coverage expansion; not holdout"
        ),
        "case_count": len(rows),
        "base_identity_count": len(base_images),
        "victim_checkpoint_sha256": victim_hash,
        "raw_payload_stored": False,
        "cases": rows,
    }
    plan = _capture_plan(rows, pack_id=pack_id, evidence_role=evidence_role)
    if candidate_model_sha256 is not None:
        normalised_candidate_sha256 = candidate_model_sha256.lower()
        if (
            len(normalised_candidate_sha256) != 64
            or any(value not in "0123456789abcdef" for value in normalised_candidate_sha256)
        ):
            raise ValueError("candidate model SHA-256 must be 64 lowercase hex digits")
        manifest["candidate_model_sha256"] = normalised_candidate_sha256
        plan["candidate_model_sha256"] = normalised_candidate_sha256
    (output / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "DIAGNOSTIC_CAPTURE_PLAN.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "README.md").write_text(
        readme_text or _readme(evidence_role), encoding="utf-8"
    )
    _write_csv(
        output / "CAPTURE_ORDER.csv",
        _capture_order_rows(rows, is_blind=is_blind),
    )
    app_plan.parent.mkdir(parents=True, exist_ok=True)
    app_plan.write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"temporary archive already exists: {temporary}")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(output).as_posix())
    temporary.replace(archive)
    return {
        "manifest": manifest,
        "plan": plan,
        "archive": str(archive),
        "archive_sha256": _sha256(archive),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--app-plan", type=Path, default=DEFAULT_APP_PLAN)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--victim-checkpoint", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_pack(
        args.output.resolve(),
        args.app_plan.resolve(),
        args.archive.resolve(),
        args.victim_checkpoint.resolve(strict=True),
    )
    print(
        json.dumps(
            {
                "cases": result["manifest"]["case_count"],
                "archive": result["archive"],
                "archive_sha256": result["archive_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
