r"""Build clearly labelled, one-QR-per-photo cards for Android Gallery testing.

The original ``data/test_qrs`` set also contains intentionally undecodable
backend-only structural cases. Those files are useful for POST /scan with an
explicit payload, but they are misleading in Android Gallery because the phone
must decode a QR before QRGuard can analyse it. This script publishes only the
Gallery-compatible subset and labels cases that share the same domain.

Run from the repository root:

    .venv\Scripts\python.exe scripts\make_gallery_qrs.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import textwrap

import cv2
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "test_qrs"
GALLERY_ROOT = ROOT / "data" / "app_gallery"
OUTPUT = GALLERY_ROOT / "QRGuard_Test_QRs"
REAL_PHOTOS = GALLERY_ROOT / "QRGuard_Real_Photos"
WIDTH, HEIGHT = 1080, 1350
QR_AREA = 760
QR_SIDE_CANDIDATES = (760, 672, 560, 448, 336, 224)


@dataclass(frozen=True)
class GalleryCase:
    filename: str
    title: str
    expected: str
    note: str

    @property
    def output_filename(self) -> str:
        """Use a fresh, descriptive name so Android cannot reuse stale thumbnails."""
        number, _, slug = Path(self.filename).stem.partition("_")
        for prefix in ("safe_", "phish_", "tampered_"):
            if slug.startswith(prefix):
                slug = slug.removeprefix(prefix)
                break
        result = self.expected.replace(" / ", "_").replace(" ", "_")
        return f"QRG_{number}_{result}_{slug}.png"


CASES = [
    GalleryCase("01_safe_google.png", "CLEAN GOOGLE URL", "SAFE", "Normal clean-image control"),
    GalleryCase("02_safe_youtube.png", "CLEAN YOUTUBE URL", "SAFE", "Normal clean-image control"),
    GalleryCase("03_safe_utar.png", "CLEAN UTAR URL", "SAFE", "Normal clean-image control"),
    GalleryCase("04_phish_maybank.png", "MAYBANK LOOK-ALIKE", "BLOCKED", "Semantic phishing test"),
    GalleryCase("05_phish_paypal.png", "PAYPAL LOOK-ALIKE", "BLOCKED", "Semantic phishing test"),
    GalleryCase("06_phish_ip_host.png", "RAW IP DESTINATION", "BLOCKED", "Semantic URL-rule test"),
    GalleryCase("10_tampered_blur.png", "BLURRED GOOGLE CAPTURE", "SAFE", "Blur is capture distortion in RUN 5"),
    GalleryCase("12_shortened_link.png", "SHORTENED URL", "BLOCKED", "Current deployed-model result"),
    GalleryCase("13_punycode.png", "PUNYCODE LOOK-ALIKE", "WARNING", "Current deployed-model result"),
    GalleryCase("14_userinfo_trick.png", "USER-INFO URL TRICK", "BLOCKED", "The host is not paypal.com"),
    GalleryCase("15_deep_subdomains.png", "DEEP SUBDOMAINS", "BLOCKED", "Current deployed-model result"),
    GalleryCase("16_wifi_open.png", "OPEN WI-FI PAYLOAD", "PARTIAL / WARNING", "Semantic model abstains on non-URL content"),
    GalleryCase("17_wifi_secure.png", "SECURE WI-FI PAYLOAD", "PARTIAL / WARNING", "Unknown/partial never displays Safe"),
    GalleryCase("18_javascript_uri.png", "JAVASCRIPT PAYLOAD", "BLOCKED", "Hard safety rule; Blocked is never downgraded"),
    GalleryCase("19_plain_text.png", "PLAIN TEXT PAYLOAD", "PARTIAL / WARNING", "Unknown/partial never displays Safe"),
    GalleryCase("20_adversarial.png", "ADVERSARIAL GOOGLE QR", "BLOCKED", "Google payload; image attack drives the verdict"),
    GalleryCase("21_duitnow_ooi_sze_shou.png", "DUITNOW: OOI SZE SHOU", "PARTIAL / WARNING", "Verify recipient and amount inside the payment app"),
]


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = Path(r"C:\Windows\Fonts") / name
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return ImageFont.load_default()


def _colour(expected: str) -> tuple[int, int, int]:
    if expected == "SAFE":
        return (103, 211, 138)
    if expected == "BLOCKED":
        return (255, 107, 107)
    return (242, 201, 76)


def _extract_single_qr(path: Path) -> Image.Image:
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    decoded, points, _ = cv2.QRCodeDetector().detectAndDecode(image)
    if not decoded or points is None:
        raise RuntimeError(f"{path.name} is not Gallery-decodable")

    if path.name != "21_duitnow_ooi_sze_shou.png":
        return Image.open(path).convert("RGB")

    # The supplied DuitNow file is a full branded poster. Extract its one QR so
    # the generated card remains visually consistent and easy to select.
    corners = points[0]
    left, top = corners.min(axis=0)
    right, bottom = corners.max(axis=0)
    side = max(right - left, bottom - top) * 1.30
    centre_x = (left + right) / 2
    centre_y = (top + bottom) / 2
    x0 = max(0, int(round(centre_x - side / 2)))
    y0 = max(0, int(round(centre_y - side / 2)))
    x1 = min(image.shape[1], int(round(centre_x + side / 2)))
    y1 = min(image.shape[0], int(round(centre_y + side / 2)))
    rgb = cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _centred(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((WIDTH - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)


def _make_card(case: GalleryCase, qr_side: int) -> Image.Image:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), (16, 13, 11))
    draw = ImageDraw.Draw(canvas)
    accent = _colour(case.expected)

    draw.rounded_rectangle((48, 48, WIDTH - 48, HEIGHT - 48), radius=38,
                           fill=(26, 22, 19), outline=accent, width=5)
    _centred(draw, "QRGuard · GALLERY TEST", 86, _font(34, bold=True), (229, 154, 99))
    _centred(draw, case.title, 145, _font(48, bold=True), (248, 238, 231))

    qr = _extract_single_qr(SOURCE / case.filename)
    qr = qr.resize((qr_side, qr_side), Image.Resampling.NEAREST)
    qr_x = (WIDTH - qr.width) // 2
    qr_y = 250 + (QR_AREA - qr.height) // 2
    draw.rounded_rectangle((qr_x - 22, qr_y - 22, qr_x + qr.width + 22,
                            qr_y + qr.height + 22), radius=24, fill=(255, 255, 255))
    canvas.paste(qr, (qr_x, qr_y))

    draw.rounded_rectangle((120, 1055, WIDTH - 120, 1155), radius=28,
                           fill=accent)
    _centred(draw, f"EXPECTED: {case.expected}", 1071, _font(43, bold=True), (17, 16, 15))
    note_lines = textwrap.wrap(case.note, width=54)
    for index, line in enumerate(note_lines[:2]):
        _centred(draw, line, 1190 + index * 38, _font(28), (174, 157, 145))
    _centred(draw, case.output_filename, 1283, _font(23), (114, 81, 58))
    return canvas


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Reserve this directory without ever clearing it: future real-world QR
    # photographs belong here and must survive regeneration of the test cards.
    REAL_PHOTOS.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT.glob("*.png"):
        old.unlink()

    lines = [
        "# QRGuard Gallery Test Cards",
        "",
        "Each PNG contains exactly one QR and a visible expected-result label.",
        "The backend-only undecodable cases 07, 08, 09 and 11 are deliberately excluded.",
        "",
    ]
    detector = cv2.QRCodeDetector()
    for case in CASES:
        output = OUTPUT / case.output_filename
        selected_side = None
        for qr_side in QR_SIDE_CANDIDATES:
            _make_card(case, qr_side).save(output, optimize=True)
            decoded, points, _ = detector.detectAndDecode(cv2.imread(str(output)))
            if decoded and points is not None:
                selected_side = qr_side
                break
        if selected_side is None:
            raise RuntimeError(f"Generated card is not decodable: {case.output_filename}")
        lines.append(
            f"- `{case.output_filename}` — **{case.expected}** — {case.note}"
        )
        print(
            f"  {case.output_filename:<46} -> "
            f"{case.expected:<17} QR {selected_side}px"
        )

    (OUTPUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{len(CASES)} one-QR Gallery cards written to {OUTPUT}")
    if any(REAL_PHOTOS.iterdir()):
        print(f"Existing real-world photos preserved in {REAL_PHOTOS}")
    else:
        print(f"Empty real-world photo folder ready at {REAL_PHOTOS}")


if __name__ == "__main__":
    main()
