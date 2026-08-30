"""Build the Android offline-capture plan from the canonical campaign.

The generated asset contains only opaque case identifiers and SHA-256 group
identifiers.  It never contains a QR payload.  Existing, valid runtime sessions
are marked complete so a freshly installed capture APK cannot silently collect
duplicates for cases that already passed the desktop audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml_training.structural.src.capture_campaign import (
    ATTACK_METHODS,
    CAMPAIGN_ID,
    MANIPULATION_METHODS,
    CampaignCase,
    load_cases,
)

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _valid_completed_sources(
    cases: list[CampaignCase], capture_root: Path
) -> dict[str, set[str]]:
    by_id = {case.case_id: case for case in cases}
    completed: dict[str, set[str]] = {case.case_id: set() for case in cases}
    duplicates: set[tuple[str, str]] = set()

    for metadata_path in sorted(capture_root.glob("*/scan_*/metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if metadata.get("campaign_id") != CAMPAIGN_ID:
            continue
        case_id = str(metadata.get("campaign_case_id", ""))
        source = str(metadata.get("image_source", ""))
        case = by_id.get(case_id)
        if case is None or source not in {"gallery", "camera"}:
            continue
        expected = {
            "ground_truth": case.label,
            "quality_condition": case.quality_condition,
            "quality_severity": case.quality_severity,
            "paired_group_sha256": _sha256_text(case.pair_token),
            "physical_qr_sha256": _sha256_text(case.physical_qr_token),
        }
        if any(metadata.get(key) != value for key, value in expected.items()):
            continue
        if not SHA256_PATTERN.fullmatch(str(metadata.get("payload_sha256", ""))):
            continue
        key = (case_id, source)
        if key in duplicates or source in completed[case_id]:
            completed[case_id].discard(source)
            duplicates.add(key)
            continue
        completed[case_id].add(source)
    return completed


def build_plan(
    schedule: Path,
    capture_root: Path,
    *,
    initial_case_id: str | None = None,
    selected_case_ids: set[str] | None = None,
    selected_case_metadata: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    cases = load_cases(schedule)
    if selected_case_ids is not None:
        known_ids = {case.case_id for case in cases}
        unknown = selected_case_ids - known_ids
        if unknown:
            raise ValueError(f"selection contains unknown cases: {sorted(unknown)}")
        cases = [case for case in cases if case.case_id in selected_case_ids]
    if not cases:
        raise ValueError("campaign schedule is empty")
    if any(case.campaign_id != CAMPAIGN_ID for case in cases):
        raise ValueError("campaign schedule contains an unexpected campaign ID")

    explicit_capture_numbers: dict[str, int] = {}
    if selected_case_metadata is not None:
        for case in cases:
            metadata = selected_case_metadata.get(case.case_id, {})
            number = metadata.get("capture_number")
            if isinstance(number, int) and number > 0:
                explicit_capture_numbers[case.case_id] = number
            expected_payload = str(metadata.get("expected_payload_sha256", ""))
            if expected_payload and not SHA256_PATTERN.fullmatch(expected_payload):
                raise ValueError(
                    f"invalid expected payload SHA-256 for {case.case_id}"
                )
    if explicit_capture_numbers:
        if len(explicit_capture_numbers) != len(cases):
            raise ValueError("selection has partial explicit capture numbering")
        expected_numbers = list(range(1, len(cases) + 1))
        if sorted(explicit_capture_numbers.values()) != expected_numbers:
            raise ValueError("selection capture numbers must be contiguous from 1")
        cases.sort(key=lambda case: explicit_capture_numbers[case.case_id])

    by_id = {case.case_id: case for case in cases}
    if initial_case_id is not None and initial_case_id not in by_id:
        raise ValueError(f"unknown initial case: {initial_case_id}")
    completed = _valid_completed_sources(cases, capture_root)
    if initial_case_id is None:
        initial_case_id = next(
            (
                case.case_id
                for case in cases
                if completed[case.case_id] != {"gallery", "camera"}
            ),
            cases[0].case_id,
        )

    if explicit_capture_numbers:
        ordered_pending = [
            case
            for case in cases
            if completed[case.case_id] != {"gallery", "camera"}
        ]
    else:
        initial_index = next(
            index for index, case in enumerate(cases) if case.case_id == initial_case_id
        )
        rotated = cases[initial_index:] + cases[:initial_index]
        pending = [
            case
            for case in rotated
            if completed[case.case_id] != {"gallery", "camera"}
        ]
        initial_label = by_id[initial_case_id].label
        label_order = [initial_label] + [
            label
            for label in ("clean", "adversarial", "tampered")
            if label != initial_label
        ]
        ordered_pending = [
            case for label in label_order for case in pending if case.label == label
        ]
    ordered_cases = ordered_pending + [
        case
        for case in cases
        if completed[case.case_id] == {"gallery", "camera"}
    ]
    capture_numbers = (
        {
            case.case_id: explicit_capture_numbers[case.case_id]
            for case in ordered_pending
        }
        if explicit_capture_numbers
        else {
            case.case_id: number
            for number, case in enumerate(ordered_pending, start=1)
        }
    )

    return {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_case_id": initial_case_id,
        "capture_defaults": {
            "device_model": "xiaomi-10t-pro",
            "environment": "indoor-controlled",
            "max_unexported_sessions": 40,
        },
        "allowed_attack_methods": sorted(ATTACK_METHODS),
        "allowed_manipulation_methods": sorted(MANIPULATION_METHODS),
        "privacy": {
            "raw_payload_stored": False,
            "payload_identifier": "sha256 of on-device decoded text",
        },
        "cases": [
            {
                "case_id": case.case_id,
                "capture_number": capture_numbers.get(case.case_id, 0),
                "label": case.label,
                "quality_condition": case.quality_condition,
                "quality_severity": case.quality_severity,
                "condition_ordinal": case.condition_ordinal,
                "paired_group_sha256": _sha256_text(case.pair_token),
                "physical_qr_sha256": _sha256_text(case.physical_qr_token),
                "recommended_medium": case.recommended_medium,
                "condition_instruction": case.condition_instruction,
                "ground_truth_instruction": case.ground_truth_instruction,
                "attack_provenance_required": case.attack_provenance_required,
                "manipulation_provenance_required": (
                    case.manipulation_provenance_required
                ),
                "default_attack_method": str(
                    (selected_case_metadata or {})
                    .get(case.case_id, {})
                    .get("default_attack_method", "none")
                ),
                "default_attack_reference_sha256": str(
                    (selected_case_metadata or {})
                    .get(case.case_id, {})
                    .get("default_attack_reference_sha256", "")
                ),
                "default_manipulation_method": str(
                    (selected_case_metadata or {})
                    .get(case.case_id, {})
                    .get("default_manipulation_method", "none")
                ),
                "expected_payload_sha256": str(
                    (selected_case_metadata or {})
                    .get(case.case_id, {})
                    .get("expected_payload_sha256", "")
                ),
                "gallery_required_for_test": (
                    (selected_case_metadata or {})
                    .get(case.case_id, {})
                    .get("assigned_split")
                    == "test"
                ),
                "completed_sources": sorted(completed[case.case_id]),
            }
            for case in ordered_cases
        ],
    }


def main() -> None:
    root = ROOT
    default_campaign = (
        root / "ml_training" / "structural" / "campaigns" / CAMPAIGN_ID / "campaign.csv"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, default=default_campaign)
    parser.add_argument(
        "--capture-root", type=Path, default=root / "data" / "runtime_captures"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "app" / "assets" / "capture" / "offline_capture_plan.json",
    )
    parser.add_argument("--initial-case")
    parser.add_argument(
        "--selection",
        type=Path,
        help="optional scope JSON containing selected_cases",
    )
    args = parser.parse_args()

    selected_case_ids = None
    selected_case_metadata = None
    if args.selection is not None:
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
        if selection.get("campaign_id") != CAMPAIGN_ID:
            raise ValueError("selection campaign ID does not match")
        selected_case_metadata = {
            str(item["case_id"]): item for item in selection["selected_cases"]
        }
        selected_case_ids = set(selected_case_metadata)

    plan = build_plan(
        args.schedule,
        args.capture_root,
        initial_case_id=args.initial_case,
        selected_case_ids=selected_case_ids,
        selected_case_metadata=selected_case_metadata,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {len(plan['cases'])} cases to {args.output}; "
        f"initial={plan['initial_case_id']}"
    )


if __name__ == "__main__":
    main()
