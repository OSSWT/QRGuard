r"""Build a printable sheet of QR codes, then score real photographs of them.

WHY. Every structural number so far is measured on images this project generated
itself. RUN 1 scored 99.91% that way and still rejected the first real photograph
it ever saw. Simulation has now been wrong twice about how hard a real capture
is - too gentle without background, too harsh with it - so the only way to know
where the model really stands is to photograph printed codes and score those.

    python scripts\real_photo_eval.py sheet     # make sheets to print
    python scripts\real_photo_eval.py score     # score the photos you took

Photograph workflow:
  1. Print the sheets in data\photo_sheets\ (plain paper is fine, no scaling).
  2. Photograph EACH code on its own, filling most of the frame, with your
     phone. Vary angle, distance and lighting - that is the point.
  3. Drop the files into, by what the printed caption says:
        data\real_photos\clean\
        data\real_photos\tampered\
        data\real_photos\adversarial\
     Filenames do not matter; the folder is the label.
  4. Run the score command.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

TEST_QRS = ROOT / "data" / "test_qrs"
SHEET_DIR = ROOT / "data" / "photo_sheets"
PHOTO_DIR = ROOT / "data" / "real_photos"
CLASSES = ("clean", "adversarial", "tampered")

# Structural class of each bundled test code. Note this is the IMAGE class, not
# the URL verdict: 04_phish_maybank is a structurally clean image of a phishing
# link, so it belongs in 'clean' here.
STRUCTURAL_CLASS = {
    "01_safe_google": "clean", "02_safe_youtube": "clean", "03_safe_utar": "clean",
    "04_phish_maybank": "clean", "05_phish_paypal": "clean", "06_phish_ip_host": "clean",
    "12_shortened_link": "clean", "13_punycode": "clean", "14_userinfo_trick": "clean",
    "15_deep_subdomains": "clean", "16_wifi_open": "clean", "17_wifi_secure": "clean",
    "18_javascript_uri": "clean", "19_plain_text": "clean",
    "07_tampered_sticker": "tampered", "08_tampered_occlusion": "tampered",
    "09_tampered_finder": "tampered", "11_both_bad": "tampered",
    # 10_tampered_blur was built as an attack under the RUN 1 spec. Blur is no
    # longer treated as tampering - it describes how a code was captured, not
    # what was done to it - so from RUN 2 onwards this is a clean code that was
    # captured badly, and calling it clean is the correct answer, not an error.
    "10_tampered_blur": "clean",
    "20_adversarial": "adversarial",
}

# Matches app/lib/services/qr_cropper.dart, so the test measures the pipeline
# that actually runs on the phone rather than a kinder version of it.
QUIET_ZONE = 0.15


def _caption(name: str) -> str:
    """Drop the leading `NN_` index from a code name for display."""
    head, sep, tail = name.partition("_")
    return tail if sep and head.isdigit() else name


def build_sheets() -> None:
    """Four codes per card, in a 2x2 grid, grouped so a card holds ONE class.

    Grouping by class is what makes the folder work as the label: the scorer
    splits each photo into quadrants, and every code it finds inherits the class
    of the folder the photo sits in. Mixing classes on a card would make that
    impossible without tracking which corner held what.
    """
    SHEET_DIR.mkdir(parents=True, exist_ok=True)
    names = sorted(STRUCTURAL_CLASS)
    missing = [n for n in names if not (TEST_QRS / f"{n}.png").exists()]
    if missing:
        raise SystemExit(
            f"missing {len(missing)} codes in {TEST_QRS} (run scripts\\make_test_qrs.py first): "
            + ", ".join(missing[:5])
        )

    CODE, MARGIN, CAPTION, GAP = 520, 50, 60, 60
    W = 2 * CODE + 2 * MARGIN + GAP
    H = 2 * (CODE + CAPTION) + 2 * MARGIN + GAP
    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except OSError:
        font = ImageFont.load_default()

    written = 0
    for cls in CLASSES:
        members = [n for n in names if STRUCTURAL_CLASS[n] == cls]
        for card_i in range(0, len(members), 4):
            chunk = members[card_i:card_i + 4]
            card = Image.new("RGB", (W, H), "white")
            draw = ImageDraw.Draw(card)
            for k, name in enumerate(chunk):
                r, c = divmod(k, 2)
                x = MARGIN + c * (CODE + GAP)
                y = MARGIN + r * (CODE + CAPTION + GAP)
                code = Image.open(TEST_QRS / f"{name}.png").convert("RGB").resize(
                    (CODE, CODE), Image.NEAREST)   # NEAREST keeps modules crisp
                card.paste(code, (x, y))
                # The leading index orders the files on disk; it means nothing
                # once the code is printed, so keep the caption to the name.
                draw.text((x, y + CODE + 14), _caption(name), fill="black", font=font)
            out = SHEET_DIR / f"{cls}_{card_i // 4 + 1}.png"
            card.save(out, dpi=(150, 150))
            written += 1

    for cls in CLASSES:
        (PHOTO_DIR / cls).mkdir(parents=True, exist_ok=True)
    counts = {c: sum(v == c for v in STRUCTURAL_CLASS.values()) for c in CLASSES}
    print(f"wrote {written} cards to {SHEET_DIR}")
    print("  " + "  ".join(f"{c}={n} codes" for c, n in counts.items()))
    print(f"""
Each card holds one class. Print or display a card, photograph the WHOLE card so
it fills the frame and is roughly square-on, then put the photo in
{PHOTO_DIR}\\<class>\\ - the card's filename tells you which.

Take SEVERAL photos of each card at different angles, distances and lighting.
Every photo yields up to 4 samples, so 3 shots per card is already ~70 samples,
and more samples is what turns a bare 1.0000 into a tight confidence interval.

Then:  python scripts\\real_photo_eval.py score""")


def _order_corners(corners: np.ndarray) -> np.ndarray | None:
    """Return TL, TR, BR, BL or None for a degenerate quadrilateral."""
    points = np.asarray(corners, dtype=np.float32).reshape(-1, 2)
    if len(points) != 4 or not np.isfinite(points).all():
        return None
    total = points.sum(axis=1)
    difference = points[:, 0] - points[:, 1]
    indices = [
        int(np.argmin(total)),
        int(np.argmax(difference)),
        int(np.argmax(total)),
        int(np.argmin(difference)),
    ]
    if len(set(indices)) != 4:
        return None
    return points[indices]


def _correct_global_camera_cast(bgr: np.ndarray) -> np.ndarray:
    """Match qr_cropper.dart's neutral-paper colour correction."""
    work = bgr.astype(np.float32)
    luminance = 0.114 * work[:, :, 0] + 0.587 * work[:, :, 1] + 0.299 * work[:, :, 2]
    bright = luminance >= 160
    if int(bright.sum()) < max(16, bgr.shape[0] * bgr.shape[1] // 20):
        return bgr

    means_bgr = work[bright].mean(axis=0)
    if np.any(means_bgr < 1):
        return bgr
    neutral = float(means_bgr.mean())
    gains_bgr = np.clip(neutral / means_bgr, 0.70, 1.45)
    return np.clip(work * gains_bgr[None, None, :], 0, 255).round().astype(np.uint8)


def crop_to_code(bgr: np.ndarray) -> tuple[np.ndarray | None, str]:
    """Perspective-rectify a detected QR exactly as the app does.

    There is deliberately no centre-crop fallback. The live app only receives
    image evidence after ML Kit detects/decodes a QR and supplies four corners;
    scoring a guessed region would evaluate data that can never reach runtime.
    """
    ok, corners = False, None
    try:
        ok, points = cv2.QRCodeDetector().detect(bgr)
        if ok and points is not None:
            corners = points.reshape(-1, 2)
    except cv2.error:
        ok = False

    if not ok or corners is None:
        return None, "not-detected"

    ordered = _order_corners(corners)
    if ordered is None:
        return None, "invalid-corners"

    edges = np.linalg.norm(ordered - np.roll(ordered, -1, axis=0), axis=1)
    shortest, longest = float(edges.min()), float(edges.max())
    if shortest < 24 or longest / shortest > 3.5:
        return None, "invalid-geometry"

    height, width = bgr.shape[:2]
    centre = ordered.mean(axis=0)
    expansion = 1 + 2 * QUIET_ZONE
    expanded = centre + (ordered - centre) * expansion
    expanded[:, 0] = np.clip(expanded[:, 0], 0, width - 1)
    expanded[:, 1] = np.clip(expanded[:, 1], 0, height - 1)
    output_side = min(round(float(edges.mean()) * expansion), height, width)
    if output_side < 24:
        return None, "invalid-geometry"

    destination = np.float32(
        [
            [0, 0],
            [output_side - 1, 0],
            [output_side - 1, output_side - 1],
            [0, output_side - 1],
        ]
    )
    transform = cv2.getPerspectiveTransform(expanded.astype(np.float32), destination)
    rectified = cv2.warpPerspective(
        bgr,
        transform,
        (output_side, output_side),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return _correct_global_camera_cast(rectified), "detected+rectified"


def quadrants(bgr: np.ndarray) -> list[np.ndarray]:
    """Split a photo of a 2x2 card into its four cells.

    Cells that hold no code - the last card of a class is rarely full - come
    back nearly uniform, and are dropped rather than scored as blank paper.
    """
    h, w = bgr.shape[:2]
    cells = []
    for r in range(2):
        for c in range(2):
            cell = bgr[r*h//2:(r+1)*h//2, c*w//2:(c+1)*w//2]
            if cell.std() > 12:          # a code has strong black/white contrast
                cells.append(cell)
    return cells


def score_photos() -> None:
    from structural.structural_service import predict_structural

    photos = [(cls, p) for cls in CLASSES
              for p in sorted((PHOTO_DIR / cls).glob("*"))
              if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic", ".webp"}]
    if not photos:
        raise SystemExit(
            f"no photos under {PHOTO_DIR}. Run 'sheet' first, print, photograph, "
            "then put the files in the class folders."
        )

    rows, per_class = [], {c: [] for c in CLASSES}
    rejected = {c: 0 for c in CLASSES}
    print(f"{'file':<34} {'true':<12} {'p_struct':>9}  {'predicted':<12} how")
    print("-" * 92)
    for cls, path in photos:
        data = np.fromfile(path, dtype=np.uint8)          # handles non-ASCII paths
        bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if bgr is None:
            print(f"{path.name:<34} {cls:<12} {'-':>9}  unreadable")
            continue
        for q, cell in enumerate(quadrants(bgr), start=1):
            crop, how = crop_to_code(cell)
            if crop is None:
                rejected[cls] += 1
                label = f"{path.name}#{q}"
                rows.append(
                    {
                        "file": label,
                        "true": cls,
                        "p_structural": None,
                        "predicted": None,
                        "crop": how,
                        "correct": None,
                    }
                )
                print(f"{label:<34} {cls:<12} {'-':>9}  not scored   {how}")
                continue
            result = predict_structural(Image.fromarray(crop[:, :, ::-1]))
            correct = result.predicted_type == cls
            per_class[cls].append(correct)
            label = f"{path.name}#{q}"
            rows.append({"file": label, "true": cls, "p_structural": result.p_structural,
                         "predicted": result.predicted_type, "crop": how,
                         "correct": correct})
            mark = " " if correct else "  <-- WRONG"
            print(f"{label:<34} {cls:<12} {result.p_structural:>9.4f}  "
                  f"{result.predicted_type:<12} {how}{mark}")

    print("\nper class:")
    for cls, hits in per_class.items():
        if hits:
            attempted = len(hits) + rejected[cls]
            print(
                f"  {cls:<12} {sum(hits)}/{len(hits)} = {sum(hits)/len(hits):.3f}"
                f"  | runtime-detectable {len(hits)}/{attempted}"
            )

    clean = [r for r in rows if r["true"] == "clean"]
    if clean:
        fp = sum(not r["correct"] for r in clean)
        # Rule of three gives a usable upper bound when the count is zero, which
        # is far more honest in a report than writing 0.0000.
        ci_hi = 3 / len(clean) if fp == 0 else None
        line = f"\nclean codes wrongly flagged: {fp}/{len(clean)}"
        if ci_hi is not None:
            line += f"  (95% CI upper bound {ci_hi:.3f}, rule of three)"
        print(line)

    out = ROOT / "data" / "real_photos" / "results.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["sheet", "score"])
    {"sheet": build_sheets, "score": score_photos}[ap.parse_args().command]()
