"""Build the current QRGuard QR_Codes_Demo pack for supervisor demonstrations."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import qrcode
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ml_training/datasets/qr_codes_demo"
STRUCTURAL_OUTPUT = OUTPUT / "Structural_Cases"
SEMANTIC_OUTPUT = OUTPUT / "Semantic_and_Payload_Cases"
STRUCTURAL_MANIFEST = (
    ROOT
    / "ml_training/datasets/structural/processed/structural-2026.03-r01/manifest.csv"
)
WIDTH, HEIGHT = 1080, 1350
QR_AREA = 760
QR_SIDE_CANDIDATES = (760, 672, 560, 448, 336)
CONDITIONS = (
    ("normal", "normal"),
    ("angle", "perspective"),
    ("defocus", "defocus_blur"),
    ("far", "far_distance"),
    ("glare", "glare"),
    ("motion", "motion_blur"),
    ("overexp", "overexposure"),
    ("screen", "screen_moire_or_compression"),
    ("shadow", "shadow"),
    ("underexp", "underexposure"),
)
LABELS = (
    ("clean", "cln", "SAFE"),
    ("adversarial", "adv", "BLOCKED"),
    ("tampered", "tmp", "BLOCKED"),
)


@dataclass(frozen=True)
class DemoCase:
    case_id: str
    category: str
    title: str
    intended_verdict: str
    note: str
    image_path: str
    image_sha256: str
    payload_sha256: str
    decoded_payload: str
    structural_ground_truth: str | None
    scan_condition: str
    source_path: str | None
    source_exposure: str
    demo_role: str = "demo_only"
    independent_evaluation: bool = False


@dataclass(frozen=True)
class SemanticSpec:
    case_id: str
    title: str
    payload: str
    intended_verdict: str
    note: str


SEMANTIC_CASES = (
    SemanticSpec(
        "SEM-01-SAFE-HTTPS",
        "SAFE HTTPS CONTROL",
        "https://example.com/qrguard-demo/safe",
        "SAFE",
        "Clean image and reserved safe demonstration URL.",
    ),
    SemanticSpec(
        "SEM-02-BRAND-PHISH",
        "BRAND IMPERSONATION",
        "http://maybank2u-verify.example.invalid/login/update",
        "BLOCKED",
        "Clean QR; Semantic branch must identify phishing-style URL risk.",
    ),
    SemanticSpec(
        "SEM-03-RAW-IP",
        "RAW IP DESTINATION",
        "http://203.0.113.7/account/confirm",
        "BLOCKED",
        "Documentation-only IP range; no live destination.",
    ),
    SemanticSpec(
        "SEM-04-PUNYCODE",
        "PUNYCODE LOOK-ALIKE",
        "http://xn--pypal-4ve.invalid/signin",
        "WARNING",
        "Reserved invalid domain containing an IDN/punycode look-alike.",
    ),
    SemanticSpec(
        "SEM-05-USERINFO",
        "USERINFO @ TRICK",
        "http://www.paypal.com@evil-site.invalid/login",
        "BLOCKED",
        "The real host follows the @ character.",
    ),
    SemanticSpec(
        "SEM-06-DEEP-SUBDOMAINS",
        "EXCESSIVE SUBDOMAINS",
        "http://login.secure.account.verify.demo.invalid/auth",
        "BLOCKED",
        "Demonstrates suspicious URL nesting without a live destination.",
    ),
    SemanticSpec(
        "SEM-07-SHORTENER",
        "SHORTENED URL",
        "https://bit.ly/qrguard-demo-invalid",
        "BLOCKED",
        "Do not open; scan only to demonstrate shortener handling.",
    ),
    SemanticSpec(
        "SEM-08-JAVASCRIPT",
        "JAVASCRIPT URI",
        "javascript:alert('qrguard-demo')",
        "BLOCKED",
        "Executable payload hard-rule demonstration.",
    ),
    SemanticSpec(
        "SEM-09-WIFI-OPEN",
        "OPEN WI-FI PAYLOAD",
        "WIFI:T:nopass;S:QRGuard_Demo_Open;;",
        "WARNING",
        "Non-URL payload with an open-network warning floor.",
    ),
    SemanticSpec(
        "SEM-10-WIFI-SECURE",
        "SECURE WI-FI PAYLOAD",
        "WIFI:T:WPA;S:QRGuard_Demo_Secure;P:DemoOnly123;;",
        "SAFE",
        "Recognised password-protected Wi-Fi payload; URL analysis is not applicable.",
    ),
    SemanticSpec(
        "SEM-11-PLAIN-TEXT",
        "PLAIN TEXT PAYLOAD",
        "QRGuard demo order 4471",
        "SAFE",
        "Harmless non-URL text; URL analysis is correctly not applicable.",
    ),
    SemanticSpec(
        "SEM-12-DUITNOW-DUMMY",
        "DUMMY DUITNOW P2P",
        (
            "00020201021126410014A000000615000101065016640209123456789"
            "520400005303458540510.005802MY5909AUSERNAME6005BANGI63043A23"
        ),
        "SAFE",
        "CRC-valid dummy DuitNow fixture; the payment app remains the confirmation boundary.",
    ),
)


QUICK_DEMO_ORDER = (
    "STR-CLN-NORMAL",
    "SEM-01-SAFE-HTTPS",
    "SEM-02-BRAND-PHISH",
    "STR-ADV-NORMAL",
    "STR-TMP-NORMAL",
    "SEM-03-RAW-IP",
    "SEM-04-PUNYCODE",
    "SEM-05-USERINFO",
    "SEM-09-WIFI-OPEN",
    "SEM-11-PLAIN-TEXT",
    "STR-CLN-GLARE",
    "STR-CLN-ANGLE",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = Path("C:/Windows/Fonts") / name
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return ImageFont.load_default()


def _accent(verdict: str) -> tuple[int, int, int]:
    if verdict == "SAFE":
        return (103, 211, 138)
    if verdict == "BLOCKED":
        return (255, 107, 107)
    return (242, 201, 76)


def _centred(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((WIDTH - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)


def _make_qr(payload: str) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def _decode(path: Path) -> str:
    image = cv2.imread(str(path))
    if image is None:
        return ""
    decoded, points, _ = cv2.QRCodeDetector().detectAndDecode(image)
    return decoded if points is not None else ""


def _build_card(
    qr_image: Image.Image,
    output: Path,
    *,
    case_id: str,
    title: str,
    expected: str,
    condition: str,
    note: str,
) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    accent = _accent(expected)
    selected_payload = ""
    for side in QR_SIDE_CANDIDATES:
        canvas = Image.new("RGB", (WIDTH, HEIGHT), (16, 13, 11))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (48, 48, WIDTH - 48, HEIGHT - 48),
            radius=38,
            fill=(26, 22, 19),
            outline=accent,
            width=5,
        )
        _centred(
            draw, "QRGuard · QR CODES DEMO", 82, _font(32, bold=True), (229, 154, 99)
        )
        _centred(draw, title, 140, _font(43, bold=True), (248, 238, 231))

        qr = qr_image.resize((side, side), Image.Resampling.NEAREST)
        qr_x = (WIDTH - side) // 2
        qr_y = 245 + (QR_AREA - side) // 2
        draw.rounded_rectangle(
            (qr_x - 22, qr_y - 22, qr_x + side + 22, qr_y + side + 22),
            radius=24,
            fill=(255, 255, 255),
        )
        canvas.paste(qr, (qr_x, qr_y))

        draw.rounded_rectangle((120, 1050, WIDTH - 120, 1148), radius=28, fill=accent)
        _centred(
            draw, f"INTENDED: {expected}", 1067, _font(41, bold=True), (17, 16, 15)
        )
        _centred(
            draw,
            f"SCAN CONDITION: {condition.upper()}",
            1174,
            _font(27, bold=True),
            (238, 220, 207),
        )
        _centred(draw, note[:66], 1215, _font(23), (174, 157, 145))
        _centred(draw, case_id, 1281, _font(23), (114, 81, 58))
        canvas.save(output, optimize=True)
        selected_payload = _decode(output)
        if selected_payload:
            return selected_payload
    raise RuntimeError(f"Generated card is not OpenCV-decodable: {output}")


def _safe_reset() -> None:
    resolved = OUTPUT.resolve()
    expected_parent = (ROOT / "ml_training/datasets").resolve()
    if resolved.parent != expected_parent or resolved.name != "qr_codes_demo":
        raise RuntimeError(f"Refusing to reset unexpected output path: {resolved}")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    STRUCTURAL_OUTPUT.mkdir(parents=True)
    SEMANTIC_OUTPUT.mkdir(parents=True)


def _structural_source_rows() -> dict[tuple[str, str], dict[str, str]]:
    if not STRUCTURAL_MANIFEST.exists():
        raise FileNotFoundError(
            "The private/local Structural dataset is required to rebuild the demo pack: "
            f"{STRUCTURAL_MANIFEST}"
        )
    with STRUCTURAL_MANIFEST.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    split_priority = {"runtime_holdout_test": 0, "validation": 1, "train": 2}
    allowed_labels = {label for label, _, _ in LABELS}
    candidates = sorted(
        (
            row
            for row in rows
            if row["is_exact_app_crop"] == "True"
            and row["image_source"] == "camera"
            and row["label"] in allowed_labels
        ),
        key=lambda row: (split_priority.get(row["split"], 9), row["path"]),
    )
    selected: dict[tuple[str, str], dict[str, str]] = {}
    for row in candidates:
        selected.setdefault((row["label"], row["quality_condition"]), row)
    return selected


def _structural_cases() -> list[DemoCase]:
    cases: list[DemoCase] = []
    source_rows = _structural_source_rows()
    for label, prefix, intended in LABELS:
        for condition, recorded_condition in CONDITIONS:
            row = source_rows.get((label, recorded_condition))
            if row is None:
                raise RuntimeError(
                    f"No exact camera app crop for {label}/{recorded_condition}"
                )
            source = ROOT / row["path"]
            output = STRUCTURAL_OUTPUT / f"STR-{prefix.upper()}-{condition.upper()}.png"
            decoded = _build_card(
                Image.open(source).convert("RGB"),
                output,
                case_id=output.stem,
                title=f"STRUCTURAL {label.upper()}",
                expected=intended,
                condition=condition,
                note="Recorded exact QRGuard app crop; scan the card normally.",
            )
            payload_hash = hashlib.sha256(decoded.encode("utf-8")).hexdigest()
            if payload_hash != row["payload_hash"]:
                raise RuntimeError(f"Payload contract changed for {row['session_id']}")
            cases.append(
                DemoCase(
                    case_id=output.stem,
                    category="structural",
                    title=f"Structural {label} / {condition}",
                    intended_verdict=intended,
                    note=(
                        "Embeds a recorded exact QRGuard camera crop with the named "
                        "condition; scan normally without adding another degradation."
                    ),
                    image_path=output.relative_to(OUTPUT).as_posix(),
                    image_sha256=_sha256(output),
                    payload_sha256=payload_hash,
                    decoded_payload=decoded,
                    structural_ground_truth=label,
                    scan_condition=condition,
                    source_path=source.relative_to(ROOT).as_posix(),
                    source_exposure=(
                        f"exact_app_crop/{row['split']}; exposed production dataset; "
                        "not independent"
                    ),
                )
            )
    return cases


def _semantic_cases() -> list[DemoCase]:
    cases: list[DemoCase] = []
    for spec in SEMANTIC_CASES:
        output = SEMANTIC_OUTPUT / f"{spec.case_id}.png"
        decoded = _build_card(
            _make_qr(spec.payload),
            output,
            case_id=spec.case_id,
            title=spec.title,
            expected=spec.intended_verdict,
            condition="normal",
            note=spec.note,
        )
        if decoded != spec.payload:
            raise RuntimeError(f"Decoded payload mismatch for {spec.case_id}")
        cases.append(
            DemoCase(
                case_id=spec.case_id,
                category="semantic_or_payload",
                title=spec.title,
                intended_verdict=spec.intended_verdict,
                note=spec.note,
                image_path=output.relative_to(OUTPUT).as_posix(),
                image_sha256=_sha256(output),
                payload_sha256=hashlib.sha256(spec.payload.encode("utf-8")).hexdigest(),
                decoded_payload=spec.payload,
                structural_ground_truth="clean",
                scan_condition="normal",
                source_path=None,
                source_exposure="post-production generated demo payload",
            )
        )
    return cases


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_docs(cases: list[DemoCase]) -> None:
    payload = {
        "schema_version": 1,
        "pack_id": "qr-codes-demo-2026-08-31-r01-r05",
        "model_lock": {
            "structural": "structural-2026.03-r01",
            "semantic": "semantic-2026.02",
            "decision": "decision-2026.03-r05",
        },
        "purpose": "post-training demonstration/evaluation; never model fitting",
        "independent_performance_claim": False,
        "case_count": len(cases),
        "cases": [asdict(case) for case in cases],
    }
    (OUTPUT / "MANIFEST.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    rows = [asdict(case) for case in cases]
    _write_csv(
        OUTPUT / "EXPECTED_RESULTS.csv",
        rows,
        [
            "case_id",
            "category",
            "title",
            "intended_verdict",
            "structural_ground_truth",
            "scan_condition",
            "image_path",
            "image_sha256",
            "payload_sha256",
            "source_exposure",
            "demo_role",
            "independent_evaluation",
            "note",
        ],
    )
    case_by_id = {case.case_id: case for case in cases}
    _write_csv(
        OUTPUT / "QUICK_DEMO_ORDER.csv",
        [
            {
                "order": index,
                "case_id": case_id,
                "image_path": case_by_id[case_id].image_path,
                "purpose": case_by_id[case_id].note,
            }
            for index, case_id in enumerate(QUICK_DEMO_ORDER, start=1)
        ],
        ["order", "case_id", "image_path", "purpose"],
    )
    _write_csv(
        OUTPUT / "ACTUAL_RESULTS.csv",
        [
            {
                "case_id": case.case_id,
                "local_gallery": "pending",
                "local_camera_simulation": "pending",
                "remote_gallery": "pending",
                "remote_camera_simulation": "pending",
                "live_camera": "pending",
                "screenshot": "pending",
                "notes": "",
            }
            for case in cases
        ],
        [
            "case_id",
            "local_gallery",
            "local_camera_simulation",
            "remote_gallery",
            "remote_camera_simulation",
            "live_camera",
            "screenshot",
            "notes",
        ],
    )
    readme = """# QRGuard QR Codes Demo

This pack demonstrates the already deployed QRGuard stack:

- Structural `structural-2026.03-r01`
- Semantic `semantic-2026.02`
- Decision `decision-2026.03-r05`

It is post-training demonstration/evaluation material. It is not an independent
training or deployment-accuracy dataset and must never be added to model fitting
or threshold calibration.

## Use with a supervisor

1. Follow `QUICK_DEMO_ORDER.csv` for the 12-case presentation sequence.
2. For Live Camera, display one card on another screen or print it. Structural
   cards already embed a recorded app crop with the named condition, so scan them
   normally; adding another degradation would create a different test.
3. For Gallery parity, import the same PNG directly into QRGuard.
4. Record the phone result and screenshot name in `ACTUAL_RESULTS.csv`.
5. Do not open decoded destinations. Network-style risk cases use reserved or
   documentation-only destinations, except the shortener card, which is scan-only.

`EXPECTED_RESULTS.csv` records intended behaviour. Run
`python scripts/validate_qr_codes_demo.py --target local` and then `--target remote`
to generate automated Gallery and Camera-simulation results. Camera simulation uses
the decoded payload plus a perspective-corrected QR crop; it is not a substitute for
the phone's physical Live Camera evidence. Structural cards are derived from the
recorded production dataset and therefore are not independent performance evidence.
Rebuilding them requires the local/private processed Structural dataset; the cards,
manifest and hashes are the public demonstration artefacts.

## 中文说明

这个资料包用于向 supervisor 展示已经部署的 QRGuard，不是新的训练集。
先按照 `QUICK_DEMO_ORDER.csv` 扫描 12 个核心案例。Live Camera 情况下，把图片
显示在另一个屏幕或打印出来。Structural 图片已经包含当时记录的 angle、glare、far
等情况，请正常扫描，不要再叠加一次环境变化。Gallery 可以使用同一张 PNG 做 parity
check。扫描后把结果和 screenshot 文件名填写进 `ACTUAL_RESULTS.csv`。不要打开 QR
内的 destination。
"""
    (OUTPUT / "README_中文_English.md").write_text(readme, encoding="utf-8")

    hashes = []
    for path in sorted(OUTPUT.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            hashes.append(f"{_sha256(path)} *{path.relative_to(OUTPUT).as_posix()}")
    (OUTPUT / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")


def main() -> None:
    _safe_reset()
    cases = _structural_cases() + _semantic_cases()
    _write_docs(cases)
    print(f"Built {len(cases)} QR_Codes_Demo cases in {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
