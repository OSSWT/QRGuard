"""Build a controlled, clean QR pack for the SEM-11 screen-camera study."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_H

from scripts.build_qr_codes_demo import _build_card

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist/SEM11_Root_Cause_Test_Pack"
BASE_PAYLOAD = "QRGuard demo order 4471"


@dataclass(frozen=True)
class RootCauseSpec:
    case_id: str
    family: str
    payload: str
    requested_version: int | None
    requested_mask: int | None
    changed_variable: str


@dataclass(frozen=True)
class BuiltCase:
    case_id: str
    family: str
    payload: str
    payload_sha256: str
    requested_version: int | None
    actual_version: int
    module_count: int
    requested_mask: int | None
    actual_mask: int
    error_correction: str
    border_modules: int
    dark_module_ratio: float
    row_transitions: int
    column_transitions: int
    maximum_dark_run: int
    qr_matrix_sha256: str
    image_path: str
    image_sha256: str
    structural_ground_truth: str
    intended_verdict: str
    changed_variable: str


def _specs() -> tuple[RootCauseSpec, ...]:
    layout = tuple(
        RootCauseSpec(
            case_id=f"RC-LAYOUT-{suffix}",
            family="same_length_payload_layout",
            payload=f"QRGuard demo order {suffix}",
            requested_version=None,
            requested_mask=None,
            changed_variable="same-length payload changes module layout",
        )
        for suffix in (4470, 4471, 4472)
    )
    masks = tuple(
        RootCauseSpec(
            case_id=f"RC-MASK-{mask}",
            family="forced_mask",
            payload=BASE_PAYLOAD,
            requested_version=3,
            requested_mask=mask,
            changed_variable="mask only; payload and version are fixed",
        )
        for mask in range(8)
    )
    version = (
        RootCauseSpec(
            case_id="RC-VERSION-4",
            family="forced_version",
            payload=BASE_PAYLOAD,
            requested_version=4,
            requested_mask=None,
            changed_variable="version only; payload is fixed",
        ),
    )
    return (*layout, *masks, *version)


def _qr(spec: RootCauseSpec) -> qrcode.QRCode:
    qr = qrcode.QRCode(
        version=spec.requested_version,
        error_correction=ERROR_CORRECT_H,
        border=4,
        mask_pattern=spec.requested_mask,
    )
    qr.add_data(spec.payload)
    qr.make(fit=spec.requested_version is None)
    return qr


def _actual_mask(spec: RootCauseSpec, matrix: list[list[bool]], version: int) -> int:
    if spec.requested_mask is not None:
        return spec.requested_mask
    for mask in range(8):
        candidate = qrcode.QRCode(
            version=version,
            error_correction=ERROR_CORRECT_H,
            border=4,
            mask_pattern=mask,
        )
        candidate.add_data(spec.payload)
        candidate.make(fit=False)
        if candidate.modules == matrix:
            return mask
    raise RuntimeError(f"Could not recover selected mask for {spec.case_id}")


def _matrix_metrics(matrix: list[list[bool]]) -> dict[str, int | float | str]:
    side = len(matrix)
    dark = sum(sum(row) for row in matrix)
    row_transitions = sum(
        matrix[y][x] != matrix[y][x - 1]
        for y in range(side)
        for x in range(1, side)
    )
    column_transitions = sum(
        matrix[y][x] != matrix[y - 1][x]
        for x in range(side)
        for y in range(1, side)
    )
    runs: list[int] = []
    for row in matrix:
        run = 0
        for value in row:
            run = run + 1 if value else 0
            runs.append(run)
    for x in range(side):
        run = 0
        for y in range(side):
            run = run + 1 if matrix[y][x] else 0
            runs.append(run)
    bits = "".join("1" if value else "0" for row in matrix for value in row)
    return {
        "dark_module_ratio": round(dark / (side * side), 6),
        "row_transitions": row_transitions,
        "column_transitions": column_transitions,
        "maximum_dark_run": max(runs),
        "qr_matrix_sha256": hashlib.sha256(bits.encode("ascii")).hexdigest(),
    }


def _title(spec: RootCauseSpec) -> str:
    if spec.family == "forced_mask":
        return f"PLAIN TEXT · MASK {spec.requested_mask}"
    if spec.family == "forced_version":
        return "PLAIN TEXT · VERSION 4"
    return f"PLAIN TEXT · {spec.payload[-4:]}"


def _write_readme(output: Path, cases: list[BuiltCase]) -> None:
    masks = next(case.actual_mask for case in cases if case.case_id == "RC-LAYOUT-4471")
    text = f"""# SEM-11 root-cause test pack

All cards are clean, harmless Plain Text QR codes generated with error correction
H and a four-module quiet zone.  This pack is diagnosis-only and must never be
used as Structural training data.

The canonical payload auto-selects Version 3 and mask {masks}.  The pack separates
same-length payload layout, masks 0-7, and a forced Version 4 control.

## Efficient physical screening

1. Keep the image viewer/browser at the same 80% condition that previously
   reproduced the false Blocked result.
2. Scan each card in `SCREENING_ORDER.csv` three independent times.
3. Do not change brightness, distance or angle within the first screening pass.
4. Export the App diagnostic session with the actual rectified crops.  Result
   screenshots alone are insufficient for retraining.
5. Only cases that fail or score near the class boundary continue to 60%, 100%
   and ten-repeat confirmation.

Build the companion Android collector with:

```powershell
cd app
flutter build apk --debug --no-pub `
  --dart-define=QRGUARD_DIAGNOSTIC_CAPTURE=true `
  --dart-define=QRGUARD_DIAGNOSTIC_PLAN_ASSET=assets/capture/sem11_root_cause_capture_plan.json
```

The debug collector uses the `.capture` Android application ID and a campaign-
specific database, so it installs beside production QRGuard and cannot mix this
campaign with older pending diagnostic sessions.

Every expected Structural type is `clean`, Semantic is `not_applicable`, and the
intended final verdict is `Safe`.  A Blocked result is therefore a visible error;
a non-clean Structural result is a branch error even if future Fusion behaviour
does not change the final verdict.
"""
    (output / "README.md").write_text(text, encoding="utf-8")


def _write_screening_order(output: Path, cases: list[BuiltCase]) -> None:
    fields = (
        "order",
        "case_id",
        "image_path",
        "screen_scale_percent",
        "repetitions",
        "expected_structural_type",
        "expected_verdict",
    )
    with (output / "SCREENING_ORDER.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, case in enumerate(cases, start=1):
            writer.writerow(
                {
                    "order": index,
                    "case_id": case.case_id,
                    "image_path": case.image_path,
                    "screen_scale_percent": 80,
                    "repetitions": 3,
                    "expected_structural_type": "clean",
                    "expected_verdict": "Safe",
                }
            )


def build_pack(output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            f"Refusing to overwrite non-empty output directory: {output}"
        )
    cards = output / "cards"
    cards.mkdir(parents=True, exist_ok=True)
    built: list[BuiltCase] = []
    for spec in _specs():
        qr = _qr(spec)
        matrix = [list(row) for row in qr.modules]
        if qr.version is None:
            raise RuntimeError(f"QR version was not resolved for {spec.case_id}")
        actual_mask = _actual_mask(spec, matrix, qr.version)
        metrics = _matrix_metrics(matrix)
        image_path = cards / f"{spec.case_id}.png"
        decoded = _build_card(
            qr.make_image(fill_color="black", back_color="white").convert("RGB"),
            image_path,
            case_id=spec.case_id,
            title=_title(spec),
            expected="SAFE",
            condition="screen root-cause control",
            note=spec.changed_variable,
        )
        if decoded != spec.payload:
            raise RuntimeError(f"Decoded payload mismatch for {spec.case_id}")
        built.append(
            BuiltCase(
                case_id=spec.case_id,
                family=spec.family,
                payload=spec.payload,
                payload_sha256=hashlib.sha256(spec.payload.encode()).hexdigest(),
                requested_version=spec.requested_version,
                actual_version=qr.version,
                module_count=len(matrix),
                requested_mask=spec.requested_mask,
                actual_mask=actual_mask,
                error_correction="H",
                border_modules=4,
                image_path=image_path.relative_to(output).as_posix(),
                image_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
                structural_ground_truth="clean",
                intended_verdict="Safe",
                changed_variable=spec.changed_variable,
                **metrics,
            )
        )

    manifest = {
        "schema_version": 1,
        "pack_id": "sem11-root-cause-2026-09-r01",
        "purpose": "controlled screen-camera diagnosis; never training data",
        "base_payload": BASE_PAYLOAD,
        "case_count": len(built),
        "screening": {"scale_percent": 80, "repetitions_per_case": 3},
        "cases": [asdict(case) for case in built],
    }
    (output / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_readme(output, built)
    _write_screening_order(output, built)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_pack(args.output.resolve())
    print(f"Built {manifest['case_count']} cases at {args.output.resolve()}")


if __name__ == "__main__":
    main()
