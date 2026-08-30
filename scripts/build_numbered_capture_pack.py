"""Build the numbered, camera-first hand-off for the real QR campaign.

The pack starts at the currently active case, skips already complete pairs and
uses plain ``1.png``, ``2.png`` ... reference names. It never stores decoded
payload text. The selected research scope keeps 50 cases per class, five per
quality condition, and an exact 30 train / 10 validation / 10 test split.

This first stage emits intact bases. Run ``prepare_scoped_capture_references``
to create verified EOT adversarial and documented tampered references before
hand-off.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import secrets
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import qrcode

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml_training.structural.src.capture_campaign import (
    CAMPAIGN_ID,
    CampaignCase,
    load_cases,
)
from ml_training.structural.src.prepare_structural_v3_captures import (
    _split_for_group,
)

SPLIT_SEED = 42
SPLIT_TARGETS = {"train": 105, "validation": 22, "test": 23}
SCOPE_TARGETS = {"train": 30, "validation": 10, "test": 10}
SCOPE_CASES_PER_CLASS = 50
SCOPE_CASES_PER_CONDITION = 5
SPLIT_ORDER = ("test", "validation", "train")
MAX_GENERATION_ATTEMPTS = 200


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_paths(reference_root: Path, case_id: str) -> tuple[Path, Path]:
    directory = reference_root / case_id
    return (
        directory / f"{case_id}-gallery-reference.png",
        directory / f"{case_id}-reference.json",
    )


def _load_reference(
    reference_root: Path,
    case: CampaignCase,
    detector: cv2.QRCodeDetector,
) -> dict[str, object] | None:
    image_path, metadata_path = _reference_paths(reference_root, case.case_id)
    if not image_path.exists() and not metadata_path.exists():
        return None
    if not image_path.is_file() or not metadata_path.is_file():
        raise ValueError(f"partial reference exists for {case.case_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("campaign_case_id") != case.case_id:
        raise ValueError(f"reference case mismatch for {case.case_id}")
    if metadata.get("reference_image_sha256") != _sha256_file(image_path):
        raise ValueError(f"reference image hash mismatch for {case.case_id}")
    decoded, _, _ = detector.detectAndDecode(cv2.imread(str(image_path)))
    decoded_hash = hashlib.sha256(decoded.encode()).hexdigest() if decoded else ""
    if decoded_hash != metadata.get("payload_sha256"):
        raise ValueError(f"reference payload hash mismatch for {case.case_id}")
    metadata["assigned_split"] = _split_for_group(decoded_hash, SPLIT_SEED)
    return metadata


def _write_reference(
    reference_root: Path,
    case: CampaignCase,
    assigned_split: str,
    detector: cv2.QRCodeDetector,
) -> dict[str, object]:
    image_path, metadata_path = _reference_paths(reference_root, case.case_id)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        raw_payload = (
            f"https://example.com/?qg3={case.case_id}-{secrets.token_hex(16)}"
        )
        payload_sha256 = hashlib.sha256(raw_payload.encode()).hexdigest()
        if _split_for_group(payload_sha256, SPLIT_SEED) != assigned_split:
            continue
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=16,
            border=4,
        )
        qr.add_data(raw_payload)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        decoded, _, _ = detector.detectAndDecode(np.asarray(image))
        if decoded == raw_payload:
            image.save(image_path)
            break
    else:
        raise RuntimeError(
            f"could not generate a {assigned_split} QR for {case.case_id}"
        )

    metadata: dict[str, object] = {
        "campaign_id": case.campaign_id,
        "campaign_case_id": case.case_id,
        "ground_truth": case.label,
        "quality_condition": case.quality_condition,
        "quality_severity": case.quality_severity,
        "payload_sha256": payload_sha256,
        "reference_image": image_path.name,
        "reference_image_sha256": _sha256_file(image_path),
        "raw_payload_stored_in_metadata": False,
        "payload_policy": "unique non-personal HTTPS URL on example.com",
        "decoder_contract": "opencv exact payload match",
        "assigned_split": assigned_split,
        "split_seed": SPLIT_SEED,
        "generation_attempts": attempt,
        "instruction": (
            "Use this PNG as the Gallery reference and display the same PNG on "
            "another screen for the Camera scan."
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def _assigned_splits(
    cases: list[CampaignCase],
    existing: dict[str, dict[str, object]],
) -> dict[str, str]:
    assignments: dict[str, str] = {
        case_id: str(metadata["assigned_split"])
        for case_id, metadata in existing.items()
    }
    for label in ("clean", "adversarial", "tampered"):
        label_cases = [case for case in cases if case.label == label]
        counts = Counter(
            assignments[case.case_id]
            for case in label_cases
            if case.case_id in assignments
        )
        remaining = {
            split: SPLIT_TARGETS[split] - counts[split] for split in SPLIT_ORDER
        }
        if any(value < 0 for value in remaining.values()):
            raise ValueError(f"existing {label} references exceed split targets")
        missing = [case for case in label_cases if case.case_id not in assignments]
        missing.sort(
            key=lambda case: hashlib.sha256(
                f"numbered-pack-v1:{case.case_id}".encode()
            ).digest()
        )
        targets = [
            split
            for split in SPLIT_ORDER
            for _ in range(remaining[split])
        ]
        if len(missing) != len(targets):
            raise ValueError(f"split quota mismatch for {label}")
        assignments.update(
            (case.case_id, target) for case, target in zip(missing, targets, strict=True)
        )
    return assignments


def _option_cost(cases: tuple[CampaignCase, ...]) -> int:
    """Prefer useful severity and medium coverage without changing split quotas."""
    if not cases:
        return 0
    penalty = sum(case.condition_ordinal for case in cases)
    if cases[0].quality_condition != "normal":
        present = {case.quality_severity for case in cases}
        penalty += 100_000 * len({"mild", "moderate", "severe"} - present)
        severity_counts = Counter(case.quality_severity for case in cases)
        penalty += 500 * (
            abs(severity_counts["mild"] - 2)
            + abs(severity_counts["moderate"] - 2)
            + abs(severity_counts["severe"] - 1)
        )
    if len({case.recommended_medium for case in cases}) < 2:
        penalty += 10_000
    return penalty


def _condition_options(
    cases: list[CampaignCase],
    references: dict[str, dict[str, object]],
    required_ids: set[str],
) -> list[tuple[tuple[int, int, int], int, tuple[CampaignCase, ...]]]:
    required = tuple(case for case in cases if case.case_id in required_ids)
    if len(required) > SCOPE_CASES_PER_CONDITION:
        raise ValueError("too many already-completed cases in one scope cell")
    available = [case for case in cases if case.case_id not in required_ids]
    needed = SCOPE_CASES_PER_CONDITION - len(required)
    best: dict[tuple[int, int, int], tuple[int, tuple[CampaignCase, ...]]] = {}
    for optional in itertools.combinations(available, needed):
        chosen = tuple(sorted(required + optional, key=lambda item: item.condition_ordinal))
        counts = Counter(
            str(references[case.case_id]["assigned_split"]) for case in chosen
        )
        key = (counts["train"], counts["validation"], counts["test"])
        cost = _option_cost(chosen)
        previous = best.get(key)
        if previous is None or (cost, tuple(c.case_id for c in chosen)) < (
            previous[0],
            tuple(c.case_id for c in previous[1]),
        ):
            best[key] = (cost, chosen)
    return [(counts, cost, chosen) for counts, (cost, chosen) in best.items()]


def _select_scope(
    cases: list[CampaignCase],
    references: dict[str, dict[str, object]],
    plan: dict[str, object],
    excluded_ids: set[str] | None = None,
) -> list[CampaignCase]:
    excluded_ids = excluded_ids or set()
    completed_ids = {
        str(item["case_id"])
        for item in plan["cases"]
        if str(item["case_id"]) not in excluded_ids
        if set(item.get("completed_sources", [])) == {"gallery", "camera"}
    }
    selected: list[CampaignCase] = []
    for label in ("clean", "adversarial", "tampered"):
        label_cases = [
            case
            for case in cases
            if case.label == label and case.case_id not in excluded_ids
        ]
        conditions = sorted({case.quality_condition for case in label_cases})
        # State is (train, validation, test) -> (cost, selected cases).
        states: dict[
            tuple[int, int, int], tuple[int, tuple[CampaignCase, ...]]
        ] = {(0, 0, 0): (0, ())}
        for condition in conditions:
            cell = [
                case for case in label_cases if case.quality_condition == condition
            ]
            options = _condition_options(cell, references, completed_ids)
            next_states: dict[
                tuple[int, int, int], tuple[int, tuple[CampaignCase, ...]]
            ] = {}
            for current_counts, (current_cost, current_cases) in states.items():
                for option_counts, option_cost, option_cases in options:
                    counts = tuple(
                        current_counts[index] + option_counts[index]
                        for index in range(3)
                    )
                    if any(
                        counts[index]
                        > (SCOPE_TARGETS["train"], SCOPE_TARGETS["validation"], SCOPE_TARGETS["test"])[index]
                        for index in range(3)
                    ):
                        continue
                    candidate = (current_cost + option_cost, current_cases + option_cases)
                    previous = next_states.get(counts)
                    if previous is None or (
                        candidate[0], tuple(case.case_id for case in candidate[1])
                    ) < (
                        previous[0], tuple(case.case_id for case in previous[1])
                    ):
                        next_states[counts] = candidate
            states = next_states
        target = (
            SCOPE_TARGETS["train"],
            SCOPE_TARGETS["validation"],
            SCOPE_TARGETS["test"],
        )
        if target not in states:
            raise ValueError(f"could not build exact 30/10/10 scope for {label}")
        chosen = list(states[target][1])
        if len(chosen) != SCOPE_CASES_PER_CLASS:
            raise ValueError(f"unexpected selected count for {label}")
        selected.extend(chosen)
    return selected


def _ordered_remaining(
    cases: list[CampaignCase],
    plan: dict[str, object],
    selected_ids: set[str],
) -> list[CampaignCase]:
    plan_cases = list(plan["cases"])
    by_id = {case.case_id: case for case in cases}
    return [
        by_id[str(item["case_id"])]
        for item in plan_cases
        if str(item["case_id"]) in selected_ids
        if set(item.get("completed_sources", [])) != {"gallery", "camera"}
    ]


def _write_slideshow(output: Path, rows: list[dict[str, object]]) -> None:
    compact = [
        {
            "n": row["number"],
            "case": row["case_id"],
            "label": row["label"],
            "condition": row["quality_condition"],
            "severity": row["quality_severity"],
            "medium": row["recommended_medium"],
            "ready": row["capture_ready"],
            "gallery": row["gallery_required_for_test"],
            "instruction": row["condition_instruction"],
        }
        for row in rows
    ]
    data = json.dumps(compact, ensure_ascii=False).replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>QRGuard numbered capture</title>
<style>
body{{margin:0;background:#111;color:#eee;font:18px system-ui;text-align:center}}
main{{display:grid;grid-template-rows:auto 1fr auto;height:100vh}}
#meta{{padding:10px}} img{{max-width:78vmin;max-height:78vmin;background:white}}
button{{font-size:20px;margin:8px;padding:10px 24px}} .stop{{color:#ff7979}}
</style><main><div id="meta"></div><div><img id="qr"></div>
<div><button onclick="move(-1)">Previous</button><button onclick="move(1)">Next</button></div></main>
<script>const rows={data};let i=0;function draw(){{const r=rows[i];
document.getElementById('qr').src=`scan_with_gallery/${{r.n}}.png`;
document.getElementById('meta').innerHTML=`<b>#${{r.n}} | ${{r.case}}</b> | ${{r.label}} / ${{r.condition}} / ${{r.severity}} / ${{r.medium}}<br>${{r.instruction}}<br><span class="${{r.ready?'':'stop'}}">${{r.ready?'CAPTURE READY':'STOP - provenance not ready'}}</span>${{r.gallery?' | TEST: Gallery reference also required':''}}`;}}
function move(d){{i=Math.max(0,Math.min(rows.length-1,i+d));draw()}}
addEventListener('keydown',e=>{{if(e.key==='ArrowRight')move(1);if(e.key==='ArrowLeft')move(-1)}});draw();</script></html>"""
    (output / "OPEN_REFERENCE_SLIDESHOW.html").write_text(html, encoding="utf-8")


def build_pack(
    schedule: Path,
    plan_path: Path,
    reference_root: Path,
    output: Path,
    archive_path: Path,
    selection_output: Path,
    *,
    scope_name: str = "fyp-50x3",
    excluded_case_ids: set[str] | None = None,
) -> tuple[list[dict[str, object]], Path]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing pack: {output}")
    if archive_path.exists():
        raise FileExistsError(f"refusing to overwrite existing archive: {archive_path}")
    cases = load_cases(schedule)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    detector = cv2.QRCodeDetector()
    existing: dict[str, dict[str, object]] = {}
    for case in cases:
        metadata = _load_reference(reference_root, case, detector)
        if metadata is not None:
            existing[case.case_id] = metadata
    assignments = _assigned_splits(cases, existing)
    references = dict(existing)
    for case in cases:
        if case.case_id not in references:
            references[case.case_id] = _write_reference(
                reference_root, case, assignments[case.case_id], detector
            )

    split_counts = Counter(
        (case.label, str(references[case.case_id]["assigned_split"]))
        for case in cases
    )
    for label in ("clean", "adversarial", "tampered"):
        for split, expected in SPLIT_TARGETS.items():
            if split_counts[(label, split)] != expected:
                raise ValueError(f"unexpected final split count for {label}/{split}")

    excluded_case_ids = excluded_case_ids or set()
    selected = _select_scope(cases, references, plan, excluded_case_ids)
    selected_ids = {case.case_id for case in selected}
    overlap = selected_ids & excluded_case_ids
    if overlap:
        raise ValueError(f"selected excluded cases: {sorted(overlap)}")
    completed_ids = {
        str(item["case_id"])
        for item in plan["cases"]
        if str(item["case_id"]) in selected_ids
        and set(item.get("completed_sources", [])) == {"gallery", "camera"}
    }
    selection = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "scope_name": scope_name,
        "cases_per_class": SCOPE_CASES_PER_CLASS,
        "cases_per_condition_per_class": SCOPE_CASES_PER_CONDITION,
        "split_targets_per_class": SCOPE_TARGETS,
        "selected_cases": [
            {
                "case_id": case.case_id,
                "label": case.label,
                "quality_condition": case.quality_condition,
                "quality_severity": case.quality_severity,
                "condition_ordinal": case.condition_ordinal,
                "assigned_split": str(references[case.case_id]["assigned_split"]),
                "completed_pair": case.case_id in completed_ids,
            }
            for case in selected
        ],
    }
    selection_output.parent.mkdir(parents=True, exist_ok=True)
    selection_output.write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")

    gallery = output / "scan_with_gallery"
    live = output / "scan_with_live_cam"
    metadata_dir = output / "reference_metadata"
    gallery.mkdir(parents=True)
    live.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    ordered = _ordered_remaining(cases, plan, selected_ids)
    rows: list[dict[str, object]] = []
    payload_hashes: set[str] = set()
    for number, case in enumerate(ordered, start=1):
        metadata = references[case.case_id]
        payload_hash = str(metadata["payload_sha256"])
        if payload_hash in payload_hashes:
            raise ValueError(f"duplicate payload hash for {case.case_id}")
        payload_hashes.add(payload_hash)
        source_image, source_metadata = _reference_paths(reference_root, case.case_id)
        shutil.copy2(source_image, gallery / f"{number}.png")
        numbered_metadata = dict(metadata)
        numbered_metadata["capture_number"] = number
        numbered_metadata["numbered_reference"] = f"{number}.png"
        (metadata_dir / f"{number}.json").write_text(
            json.dumps(numbered_metadata, indent=2) + "\n", encoding="utf-8"
        )
        split = str(metadata["assigned_split"])
        capture_ready = case.label == "clean"
        rows.append(
            {
                "number": number,
                "case_id": case.case_id,
                "label": case.label,
                "quality_condition": case.quality_condition,
                "quality_severity": case.quality_severity,
                "condition_ordinal": case.condition_ordinal,
                "recommended_medium": case.recommended_medium,
                "condition_instruction": case.condition_instruction,
                "assigned_split": split,
                "gallery_required_for_test": split == "test",
                "capture_ready": capture_ready,
                "readiness_reason": (
                    "ready_clean_reference"
                    if capture_ready
                    else "requires_verified_eot_attack"
                    if case.label == "adversarial"
                    else "requires_documented_manipulation"
                ),
                "gallery_reference": f"scan_with_gallery/{number}.png",
                "live_camera_review_name": f"scan_with_live_cam/{number}.png",
                "payload_sha256": payload_hash,
                "reference_sha256": str(metadata["reference_image_sha256"]),
                "canonical_evidence": "QRGuard Capture offline ZIP",
            }
        )
        if source_metadata.stat().st_size == 0:
            raise ValueError(f"empty metadata for {case.case_id}")

    fieldnames = list(rows[0])
    with (output / "capture_index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    (output / "capture_index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "campaign_id": CAMPAIGN_ID,
                "scope_name": scope_name,
                "selected_cases": len(selected),
                "numbered_cases": len(rows),
                "completed_pairs_already_counted": len(completed_ids),
                "split_seed": SPLIT_SEED,
                "split_targets_per_class": SCOPE_TARGETS,
                "rows": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (live / "README.txt").write_text(
        "Optional review screenshots may be named 1.png, 2.png, 3.png, ... here.\n"
        "They are not training evidence. Keep and upload the QRGuard Capture ZIP.\n",
        encoding="utf-8",
    )
    gallery_count = sum(bool(row["gallery_required_for_test"]) for row in rows)
    (output / "README_FIRST.md").write_text(
        "# QRGuard numbered camera-first pack\n\n"
        f"Scope: `{scope_name}`. Target: 50 Clean + 50 Adversarial + 50 "
        f"Tampered ({len(selected)} selected). This pack contains {len(rows)} "
        f"remaining Camera scans; {len(completed_ids)} completed pairs are "
        "already counted.\n\n"
        "1. Start at `scan_with_gallery/1.png`; it maps to the current active case.\n"
        "2. Display that file full-screen and capture it through QRGuard Live Camera.\n"
        f"3. Gallery is needed only for the {gallery_count} cases where "
        "`gallery_required_for_test` is `True`; select the same numbered original "
        "PNG, never a screenshot.\n"
        "4. Export the QRGuard offline ZIP every 40 Camera sessions or sooner.\n"
        "5. Files in `scan_with_live_cam` are optional review screenshots only.\n"
        "6. Stop when `capture_ready` is `False`; those base QRs still require valid "
        "attack/manipulation provenance.\n\n"
        "The App ZIP, not a renamed screenshot, is canonical training evidence.\n",
        encoding="utf-8",
    )
    _write_slideshow(output, rows)

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output).as_posix())
    return rows, archive_path


def main() -> None:
    campaign = ROOT / "ml_training" / "structural" / "campaigns" / CAMPAIGN_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, default=campaign / "campaign.csv")
    parser.add_argument(
        "--plan",
        type=Path,
        default=ROOT / "app" / "assets" / "capture" / "offline_capture_plan.json",
    )
    parser.add_argument(
        "--reference-root",
        type=Path,
        default=ROOT / "data" / "capture_pilot" / CAMPAIGN_ID,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "data"
            / "numbered_capture_pack"
            / f"{CAMPAIGN_ID}-50x3-r01"
        ),
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=(
            ROOT
            / "data"
            / "numbered_capture_pack"
            / f"{CAMPAIGN_ID}-50x3-r01.zip"
        ),
    )
    parser.add_argument(
        "--selection-output",
        type=Path,
        default=campaign / "scope_50x3_selection.json",
    )
    parser.add_argument("--scope-name", default="fyp-50x3")
    parser.add_argument(
        "--exclude-selection",
        type=Path,
        help="optional prior selection JSON whose cases must not be reused",
    )
    args = parser.parse_args()
    excluded_case_ids: set[str] = set()
    if args.exclude_selection is not None:
        exclusion = json.loads(args.exclude_selection.read_text(encoding="utf-8"))
        if exclusion.get("campaign_id") != CAMPAIGN_ID:
            raise ValueError("exclusion selection campaign ID does not match")
        excluded_case_ids = {
            str(item["case_id"]) for item in exclusion["selected_cases"]
        }
    rows, archive = build_pack(
        args.schedule,
        args.plan,
        args.reference_root,
        args.output,
        args.archive,
        args.selection_output,
        scope_name=args.scope_name,
        excluded_case_ids=excluded_case_ids,
    )
    ready = sum(bool(row["capture_ready"]) for row in rows)
    tests = sum(bool(row["gallery_required_for_test"]) for row in rows)
    print(
        f"wrote {len(rows)} numbered remaining cases; ready={ready}; "
        f"remaining_test_gallery={tests}; archive={archive}"
    )


if __name__ == "__main__":
    main()
