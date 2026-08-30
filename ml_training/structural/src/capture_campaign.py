"""Create, activate and audit the Structural v3 real paired-capture campaign.

The schedule contains opaque non-personal tokens only. Activating a case writes
one small control file that the local backend reads before every scan, so the
backend does not need to be restarted between 450 cases. Raw QR payloads are
never written to the schedule, control file, or capture metadata.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import secrets
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

CAMPAIGN_ID = "structural-v3-real-2026.03-r01"
LABELS = ("clean", "adversarial", "tampered")
QUALITY_CONDITIONS = (
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
)
LABEL_CODES = {"clean": "cln", "adversarial": "adv", "tampered": "tmp"}
CONDITION_CODES = {
    "normal": "normal",
    "overexposure": "overexp",
    "underexposure": "underexp",
    "motion_blur": "motion",
    "defocus_blur": "defocus",
    "far_distance": "far",
    "perspective": "angle",
    "glare": "glare",
    "shadow": "shadow",
    "screen_moire_or_compression": "screen",
}
CONDITION_INSTRUCTIONS = {
    "normal": "Even light, QR centred, normal focus and working distance.",
    "overexposure": "Increase illumination until highlights wash out QR modules.",
    "underexposure": "Reduce illumination while keeping the same QR ground truth.",
    "motion_blur": "Move the phone during acquisition; do not alter QR modules.",
    "defocus_blur": "Defocus the camera; do not edit or damage the QR image.",
    "far_distance": "Increase distance so the QR occupies less of the frame.",
    "perspective": "Capture at an oblique angle while keeping the whole QR visible.",
    "glare": "Introduce a real reflection across part of the QR surface.",
    "shadow": "Cast a real partial shadow without drawing on QR modules.",
    "screen_moire_or_compression": "Display on a screen and capture visible moire/compression.",
}
ATTACK_METHODS = {
    "eot_fgsm",
    "eot_pgd",
    "verified_physical_patch",
    "other_verified",
}
MANIPULATION_METHODS = {
    "sticker_overlay",
    "module_erasure",
    "finder_damage",
    "cut_and_paste",
    "printed_obstruction",
    "other_documented",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SAFE_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._/-]{0,79}$")


@dataclass(frozen=True)
class CampaignCase:
    campaign_id: str
    case_id: str
    label: str
    quality_condition: str
    quality_severity: str
    condition_ordinal: int
    pair_token: str
    physical_qr_token: str
    recommended_medium: str
    condition_instruction: str
    ground_truth_instruction: str
    unique_payload_required: bool
    gallery_required: bool
    camera_required: bool
    attack_provenance_required: bool
    manipulation_provenance_required: bool


@dataclass
class CampaignProgress:
    campaign_id: str
    total_cases: int
    expected_sessions: int
    valid_planned_sessions: int
    complete_pairs: int
    pending_cases: int
    invalid_cases: int
    unplanned_sessions: int
    per_label_complete_pairs: dict[str, int]
    per_label_condition_complete_pairs: dict[str, dict[str, int]]
    errors: list[str]


def _severity(condition: str, ordinal: int) -> str:
    if condition == "normal":
        return "none"
    if ordinal <= 5:
        return "mild"
    if ordinal <= 10:
        return "moderate"
    return "severe"


def _ground_truth_instruction(label: str) -> str:
    if label == "clean":
        return "Use an intact QR. Capture degradation remains clean, never malicious."
    if label == "adversarial":
        return (
            "Use only a verified EOT/physical adversarial reference with a recorded "
            "method and SHA-256; ordinary blur, glare or exposure is not adversarial."
        )
    return (
        "Use a physically manipulated QR and record the manipulation method; "
        "ordinary camera degradation alone is not tampering."
    )


def build_cases(cases_per_condition: int = 15) -> list[CampaignCase]:
    if cases_per_condition < 5:
        raise ValueError("at least five cases per condition are required")
    cases: list[CampaignCase] = []
    for label in LABELS:
        for condition in QUALITY_CONDITIONS:
            for ordinal in range(1, cases_per_condition + 1):
                case_id = (
                    f"{LABEL_CODES[label]}-{CONDITION_CODES[condition]}-{ordinal:02d}"
                )
                token_base = f"{CAMPAIGN_ID}:{case_id}"
                cases.append(
                    CampaignCase(
                        campaign_id=CAMPAIGN_ID,
                        case_id=case_id,
                        label=label,
                        quality_condition=condition,
                        quality_severity=_severity(condition, ordinal),
                        condition_ordinal=ordinal,
                        pair_token=f"{token_base}:pair",
                        physical_qr_token=f"{token_base}:physical",
                        recommended_medium=(
                            "screen"
                            if condition == "screen_moire_or_compression"
                            else "printed-paper" if ordinal % 2 else "screen"
                        ),
                        condition_instruction=CONDITION_INSTRUCTIONS[condition],
                        ground_truth_instruction=_ground_truth_instruction(label),
                        unique_payload_required=True,
                        gallery_required=True,
                        camera_required=True,
                        attack_provenance_required=label == "adversarial",
                        manipulation_provenance_required=label == "tampered",
                    )
                )
    return cases


def write_campaign(output_dir: Path, cases_per_condition: int = 15) -> list[CampaignCase]:
    cases = build_cases(cases_per_condition)
    output_dir.mkdir(parents=True, exist_ok=True)
    schedule = output_dir / "campaign.csv"
    with schedule.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CampaignCase.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(case) for case in cases)
    metadata = {
        "campaign_id": CAMPAIGN_ID,
        "cases": len(cases),
        "expected_sessions": len(cases) * 2,
        "classes": list(LABELS),
        "quality_conditions": list(QUALITY_CONDITIONS),
        "cases_per_class": len(cases) // len(LABELS),
        "cases_per_condition_per_class": cases_per_condition,
        "severity_policy": {
            "normal": "15 none",
            "other_conditions": "first 5 mild, next 5 moderate, final 5 severe",
        },
        "privacy": "No raw payloads or personal identifiers are stored.",
        "status": "prepared_no_real_captures_yet",
    }
    (output_dir / "campaign.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return cases


def load_cases(schedule: Path) -> list[CampaignCase]:
    with schedule.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    cases = []
    for row in rows:
        row["condition_ordinal"] = int(row["condition_ordinal"])
        for name in (
            "unique_payload_required",
            "gallery_required",
            "camera_required",
            "attack_provenance_required",
            "manipulation_provenance_required",
        ):
            row[name] = str(row[name]).lower() in {"true", "1", "yes"}
        cases.append(CampaignCase(**row))
    return cases


def _safe_value(name: str, value: str) -> str:
    value = value.strip()
    if not SAFE_VALUE_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a non-personal 1-80 character descriptor")
    return value


def activate_case(
    schedule: Path,
    case_id: str,
    output: Path,
    *,
    device: str,
    medium: str | None = None,
    environment: str,
    attack_method: str | None = None,
    attack_reference_sha256: str | None = None,
    manipulation_method: str | None = None,
) -> dict[str, object]:
    matches = [case for case in load_cases(schedule) if case.case_id == case_id]
    if len(matches) != 1:
        raise ValueError(f"campaign case not found or duplicated: {case_id}")
    case = matches[0]

    if case.attack_provenance_required:
        if attack_method not in ATTACK_METHODS:
            raise ValueError("adversarial cases require a verified attack method")
        reference = str(attack_reference_sha256 or "").lower()
        if not SHA256_PATTERN.fullmatch(reference):
            raise ValueError("adversarial cases require a 64-character reference SHA-256")
    else:
        attack_method = "none"
        reference = ""

    if case.manipulation_provenance_required:
        if manipulation_method not in MANIPULATION_METHODS:
            raise ValueError("tampered cases require a documented manipulation method")
    else:
        manipulation_method = "none"

    context: dict[str, object] = {
        "campaign_id": case.campaign_id,
        "campaign_case_id": case.case_id,
        "ground_truth": case.label,
        "quality_condition": case.quality_condition,
        "quality_severity": case.quality_severity,
        "pair_token": case.pair_token,
        "physical_qr_token": case.physical_qr_token,
        "device_model": _safe_value("device", device),
        "medium": _safe_value("medium", medium or case.recommended_medium),
        "environment": _safe_value("environment", environment),
        "attack_method": attack_method,
        "attack_reference_sha256": reference,
        "manipulation_method": manipulation_method,
        "operator_instruction": (
            "Scan Gallery and Camera for this same case before activating another case."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(context, indent=2), encoding="utf-8")
    temporary.replace(output)
    return context


def create_pilot_reference(
    schedule: Path,
    case_id: str,
    output_dir: Path,
    *,
    force: bool = False,
) -> dict[str, object]:
    """Generate one non-personal QR reference without persisting its raw payload."""
    import cv2
    import numpy as np
    import qrcode

    matches = [case for case in load_cases(schedule) if case.case_id == case_id]
    if len(matches) != 1:
        raise ValueError(f"campaign case not found or duplicated: {case_id}")
    case = matches[0]
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / f"{case.case_id}-gallery-reference.png"
    metadata_path = output_dir / f"{case.case_id}-reference.json"
    if not force and (image_path.exists() or metadata_path.exists()):
        raise FileExistsError(
            f"pilot reference already exists for {case.case_id}; do not replace "
            "a payload after capture has started"
        )

    detector = cv2.QRCodeDetector()
    for generation_attempts in range(1, 21):
        raw_payload = f"https://example.com/?qg3={case.case_id}-{secrets.token_hex(16)}"
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=16,
            border=4,
        )
        qr.add_data(raw_payload)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        decoded, _, _ = detector.detectAndDecode(np.asarray(image.convert("L")))
        if decoded == raw_payload:
            break
    else:
        raise RuntimeError("could not generate an OpenCV-decodable pilot QR")

    image.save(image_path)
    metadata: dict[str, object] = {
        "campaign_id": case.campaign_id,
        "campaign_case_id": case.case_id,
        "ground_truth": case.label,
        "quality_condition": case.quality_condition,
        "quality_severity": case.quality_severity,
        "payload_sha256": hashlib.sha256(raw_payload.encode()).hexdigest(),
        "reference_image": image_path.name,
        "reference_image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "raw_payload_stored_in_metadata": False,
        "payload_policy": "unique non-personal HTTPS URL on example.com",
        "decoder_contract": "opencv exact payload match",
        "generation_attempts": generation_attempts,
        "instruction": (
            "Download this PNG for Gallery, then display the same PNG on another "
            "screen for the Camera scan."
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def audit_campaign(schedule: Path, capture_root: Path) -> CampaignProgress:
    cases = load_cases(schedule)
    by_id = {case.case_id: case for case in cases}
    valid: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    errors: list[str] = []
    invalid_case_ids: set[str] = set()
    unplanned = 0

    for metadata_path in sorted(capture_root.glob("*/scan_*/metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            unplanned += 1
            errors.append(f"invalid metadata: {metadata_path.as_posix()}")
            continue
        if metadata.get("campaign_id") != CAMPAIGN_ID:
            unplanned += 1
            continue
        case_id = str(metadata.get("campaign_case_id", ""))
        case = by_id.get(case_id)
        if case is None:
            unplanned += 1
            errors.append(f"unknown campaign case: {case_id or '<missing>'}")
            continue
        source = str(metadata.get("image_source", ""))
        case_errors = []
        expected = {
            "ground_truth": case.label,
            "quality_condition": case.quality_condition,
            "quality_severity": case.quality_severity,
            "paired_group_sha256": _hash_token(case.pair_token),
            "physical_qr_sha256": _hash_token(case.physical_qr_token),
        }
        for field, expected_value in expected.items():
            if metadata.get(field) != expected_value:
                case_errors.append(f"{field} mismatch")
        if source not in {"gallery", "camera"}:
            case_errors.append("invalid image_source")
        if not SHA256_PATTERN.fullmatch(str(metadata.get("payload_sha256", ""))):
            case_errors.append("invalid payload_sha256")
        if case.attack_provenance_required:
            if metadata.get("attack_method") not in ATTACK_METHODS:
                case_errors.append("missing verified attack_method")
            if not SHA256_PATTERN.fullmatch(
                str(metadata.get("attack_reference_sha256", ""))
            ):
                case_errors.append("missing attack_reference_sha256")
        if case.manipulation_provenance_required and (
            metadata.get("manipulation_method") not in MANIPULATION_METHODS
        ):
            case_errors.append("missing manipulation_method")
        if source in valid[case_id]:
            case_errors.append(f"duplicate {source} session")
        if case_errors:
            invalid_case_ids.add(case_id)
            errors.extend(f"{case_id}: {message}" for message in case_errors)
            continue
        valid[case_id][source] = metadata

    complete: set[str] = set()
    for case_id, sources in valid.items():
        if case_id in invalid_case_ids:
            continue
        if set(sources) != {"gallery", "camera"}:
            continue
        if sources["gallery"]["payload_sha256"] != sources["camera"]["payload_sha256"]:
            invalid_case_ids.add(case_id)
            errors.append(f"{case_id}: Gallery/Camera payload hash mismatch")
            continue
        complete.add(case_id)

    per_label = Counter(by_id[case_id].label for case_id in complete)
    per_cell: dict[str, Counter] = defaultdict(Counter)
    for case_id in complete:
        case = by_id[case_id]
        per_cell[case.label][case.quality_condition] += 1
    progress = CampaignProgress(
        campaign_id=CAMPAIGN_ID,
        total_cases=len(cases),
        expected_sessions=len(cases) * 2,
        valid_planned_sessions=sum(len(sources) for sources in valid.values()),
        complete_pairs=len(complete),
        pending_cases=len(cases) - len(complete),
        invalid_cases=len(invalid_case_ids),
        unplanned_sessions=unplanned,
        per_label_complete_pairs={label: per_label[label] for label in LABELS},
        per_label_condition_complete_pairs={
            label: {condition: per_cell[label][condition] for condition in QUALITY_CONDITIONS}
            for label in LABELS
        },
        errors=errors,
    )
    capture_root.mkdir(parents=True, exist_ok=True)
    (capture_root / "campaign_progress.json").write_text(
        json.dumps(asdict(progress), indent=2), encoding="utf-8"
    )
    rows = []
    for case in cases:
        sources = valid.get(case.case_id, {})
        rows.append(
            {
                "case_id": case.case_id,
                "label": case.label,
                "quality_condition": case.quality_condition,
                "quality_severity": case.quality_severity,
                "gallery_captured": "gallery" in sources,
                "camera_captured": "camera" in sources,
                "complete_pair": case.case_id in complete,
                "invalid": case.case_id in invalid_case_ids,
            }
        )
    with (capture_root / "campaign_progress.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return progress


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create")
    create.add_argument("output_dir", type=Path)
    create.add_argument("--cases-per-condition", type=int, default=15)

    activate = commands.add_parser("activate")
    activate.add_argument("schedule", type=Path)
    activate.add_argument("case_id")
    activate.add_argument("--output", type=Path, required=True)
    activate.add_argument("--device", required=True)
    activate.add_argument("--medium")
    activate.add_argument("--environment", required=True)
    activate.add_argument("--attack-method", choices=sorted(ATTACK_METHODS))
    activate.add_argument("--attack-reference-sha256")
    activate.add_argument(
        "--manipulation-method", choices=sorted(MANIPULATION_METHODS)
    )

    audit = commands.add_parser("audit")
    audit.add_argument("schedule", type=Path)
    audit.add_argument("capture_root", type=Path)

    pilot = commands.add_parser("make-pilot")
    pilot.add_argument("schedule", type=Path)
    pilot.add_argument("case_id")
    pilot.add_argument("output_dir", type=Path)
    pilot.add_argument("--force", action="store_true")

    args = parser.parse_args()
    if args.command == "create":
        cases = write_campaign(args.output_dir, args.cases_per_condition)
        print(f"wrote {len(cases)} campaign cases to {args.output_dir}")
    elif args.command == "activate":
        context = activate_case(
            args.schedule,
            args.case_id,
            args.output,
            device=args.device,
            medium=args.medium,
            environment=args.environment,
            attack_method=args.attack_method,
            attack_reference_sha256=args.attack_reference_sha256,
            manipulation_method=args.manipulation_method,
        )
        print(json.dumps(context, indent=2))
    elif args.command == "audit":
        progress = audit_campaign(args.schedule, args.capture_root)
        print(json.dumps(asdict(progress), indent=2))
    else:
        metadata = create_pilot_reference(
            args.schedule, args.case_id, args.output_dir, force=args.force
        )
        print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
