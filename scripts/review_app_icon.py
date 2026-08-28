r"""Check the approved replacement icon against what Android renders.

A launcher never shows the flat master square. An adaptive icon is a 108 dp
foreground layer that the launcher masks with a shape of its own choosing, and
only the centre 66 dp circle is guaranteed to survive. This script applies
those masks, measures each layer against that circle, and writes the proof
sheets that the artwork was approved on.

It is a verification tool: it writes ONLY to ``data/app_icons`` and never
touches ``app/assets/icon`` or the Android mipmaps.

    .venv\Scripts\python.exe scripts\review_app_icon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from make_app_icon import (  # noqa: E402
    BACKGROUND,
    LAUNCHER_INSET,
    MASTER,
    build_launcher_assets,
)

OUT = ROOT / "data" / "app_icons"

# Android adaptive-icon geometry, as fractions of the 108 dp foreground layer.
VISIBLE = 72 / 108  # 0.667 - the largest area any mask can show
SAFE = 66 / 108  # 0.611 - the circle every mask is guaranteed to show

REVIEW_SIZES = (128, 64, 40, 28)


def as_rendered(layer: Image.Image) -> Image.Image:
    """Apply the `<inset android:inset="16%">` that the generated adaptive-icon
    XML wraps around the foreground and monochrome drawables.

    Measuring the source PNG instead of this is measuring the wrong thing: the
    source is not what Android composites.
    """
    size = layer.width
    inner = round(size * (1 - 2 * LAUNCHER_INSET))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = (size - inner) // 2
    out.paste(layer.resize((inner, inner), Image.Resampling.LANCZOS), (offset, offset))
    return out


def _font(size: int) -> ImageFont.ImageFont:
    """A real TTF. PIL's default bitmap font has no em dash, which is why an
    earlier review sheet read "A+ Pulse Lens<tofu>128px"."""
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


# --------------------------------------------------------------------------
# Launcher masks
# --------------------------------------------------------------------------
def _mask(shape: str, size: int) -> Image.Image:
    """Build one launcher mask at ``size``, covering the visible 72/108 area."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    inset = size * (1 - VISIBLE) / 2
    box = (inset, inset, size - inset, size - inset)
    if shape == "circle":
        draw.ellipse(box, fill=255)
    elif shape == "squircle":
        draw.rounded_rectangle(box, radius=size * VISIBLE * 0.42, fill=255)
    else:  # rounded square, the most generous common mask
        draw.rounded_rectangle(box, radius=size * VISIBLE * 0.22, fill=255)
    return mask


def _apply_mask(layer: Image.Image, shape: str, background: str) -> Image.Image:
    """Composite ``layer`` over the adaptive background, then mask it."""
    size = layer.width
    plate = Image.new("RGBA", (size, size), background)
    plate.alpha_composite(layer)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(plate, (0, 0), _mask(shape, size))
    return out


# --------------------------------------------------------------------------
# Measurement
# --------------------------------------------------------------------------
def content_radius(layer: Image.Image) -> float:
    """Diameter of the drawn MARK as a fraction of the layer width.

    Compare against SAFE (0.611): anything larger is clipped by some launcher.

    Both transparency and the brand background count as empty. Ignoring only
    transparency measured the wrong thing once: ``as_rendered`` leaves a
    transparent margin around an opaque master, so the dark plate itself
    registered as content and an inset square reported 0.956 instead of the
    0.714 its ember marks actually reach.
    """
    grid = 256
    small = layer.convert("RGBA").resize((grid, grid), Image.Resampling.LANCZOS)
    pixels = small.load()
    plate = ImageColor.getrgb(BACKGROUND)
    centre = grid / 2
    worst = 0.0
    for y in range(grid):
        for x in range(grid):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 40:
                continue  # transparent
            if max(abs(a - b) for a, b in zip((red, green, blue), plate)) < 40:
                continue  # the brand background, not part of the mark
            radius = ((x + 0.5 - centre) ** 2 + (y + 0.5 - centre) ** 2) ** 0.5
            worst = max(worst, radius)
    return 2 * worst / grid  # a radius of grid/2 means content spans the layer


# --------------------------------------------------------------------------
# Sheets
# --------------------------------------------------------------------------
def _sizes_strip(
    icon: Image.Image, label: str, *, sizes: tuple[int, ...] = REVIEW_SIZES
) -> Image.Image:
    panel, height = 300, 400
    sheet = Image.new("RGB", (panel * len(sizes), height), "#171310")
    draw = ImageDraw.Draw(sheet)
    title, small = _font(19), _font(15)
    draw.text((20, 14), label, fill="#FFF0DF", font=title)
    for index, target in enumerate(sizes):
        x = index * panel
        actual = icon.resize((target, target), Image.Resampling.LANCZOS)
        zoom = min(8, 224 // target)
        big = actual.resize((target * zoom, target * zoom), Image.Resampling.NEAREST)
        sheet.paste(
            big.convert("RGB"),
            (x + (panel - big.width) // 2, 60 + (232 - big.height) // 2),
        )
        draw.text((x + 20, 302), f"{target} px", fill="#AE9D91", font=small)
        sheet.paste(actual.convert("RGB"), (x + 100, 296))
    return sheet


def _mask_strip(layer: Image.Image, label: str, background: str) -> Image.Image:
    shapes = ("circle", "squircle", "rounded")
    panel, height = 300, 320
    sheet = Image.new("RGB", (panel * len(shapes), height), "#171310")
    draw = ImageDraw.Draw(sheet)
    title, small = _font(19), _font(15)
    draw.text((20, 14), label, fill="#FFF0DF", font=title)
    for index, shape in enumerate(shapes):
        masked = _apply_mask(layer, shape, background).resize(
            (216, 216), Image.Resampling.LANCZOS
        )
        plate = Image.new("RGB", (216, 216), "#171310")
        plate.paste(masked.convert("RGB"), (0, 0), masked.split()[3])
        sheet.paste(plate, (index * panel + (panel - 216) // 2, 56))
        draw.text(
            (index * panel + 20, 286), f"{shape} mask", fill="#AE9D91", font=small
        )
    return sheet


def _stack(parts: list[Image.Image], path: Path) -> None:
    width = max(part.width for part in parts)
    sheet = Image.new("RGB", (width, sum(part.height for part in parts)), "#171310")
    y = 0
    for part in parts:
        sheet.paste(part, (0, y))
        y += part.height
    sheet.save(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    assets = build_launcher_assets()
    square = assets["qrguard_icon.png"]
    # Everything below works on the drawables as Android composites them,
    # i.e. after the generated XML's 16% inset.
    foreground = as_rendered(assets["qrguard_icon_foreground.png"])
    monochrome = as_rendered(assets["qrguard_icon_monochrome.png"])

    # Compare the unsafe full square with the scaled foreground that ships.
    _stack(
        [
            _mask_strip(
                as_rendered(square),
                "full square as foreground - outside the guaranteed safe circle",
                BACKGROUND,
            ),
            _mask_strip(
                foreground,
                "shipped replacement foreground - fitted to the safe circle",
                BACKGROUND,
            ),
        ],
        OUT / "review_mask_clipping.png",
    )

    _stack(
        [
            _sizes_strip(square, "replacement artwork - legacy launcher and listing"),
            _sizes_strip(
                _apply_mask(foreground, "circle", BACKGROUND),
                "replacement artwork under an adaptive circle mask",
            ),
        ],
        OUT / "review_launcher_sizes.png",
    )

    mono_on_dark = Image.new("RGBA", (MASTER, MASTER), BACKGROUND)
    mono_on_dark.alpha_composite(monochrome)
    _stack(
        [
            _sizes_strip(
                mono_on_dark,
                "monochrome layer - themed icons and notifications",
                sizes=(64, 40, 28, 24),
            )
        ],
        OUT / "review_monochrome.png",
    )

    print("Review images written to", OUT)
    failures = 0
    for name, layer, must_fit in (
        ("square master", square, False),
        ("square as foreground", as_rendered(square), True),
        ("foreground, inset", foreground, True),
        ("monochrome, inset", monochrome, True),
    ):
        diameter = content_radius(layer)
        if not must_fit:
            note = "full bleed by design"
        elif diameter > SAFE:
            note = f"CLIPPED - {diameter / SAFE:.0%} of the safe circle"
            # The square-as-foreground row is the rejected option, kept as the
            # measurement the three-asset split was decided on.
            failures += name != "square as foreground"
        else:
            note = "safe"
        print(f"  {name:<21} content diameter {diameter:.3f} of layer  -> {note}")
    print(f"  (safe circle {SAFE:.3f}, largest visible area {VISIBLE:.3f})")
    print("Launcher assets were NOT changed by this script.")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
