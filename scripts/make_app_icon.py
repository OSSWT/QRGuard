r"""Build launcher assets from the user-approved QRGuard artwork.

The source artwork is kept verbatim at:

    app/assets/icon/qrguard_icon_source.png

Android still needs three masters. The legacy icon uses the complete artwork.
The adaptive foreground is scaled so all four scan corners survive the centre
66/108 safe circle after ``flutter_launcher_icons`` adds its 16% inset. The
monochrome layer derives an alpha mask from the same artwork for themed icons.

    assets/icon/qrguard_icon.png             complete legacy artwork
    assets/icon/qrguard_icon_foreground.png  safe adaptive foreground
    assets/icon/qrguard_icon_monochrome.png  themed-icon alpha mask

Run this, review it, and then regenerate Android mipmaps:

    .venv\Scripts\python.exe scripts\make_app_icon.py
    .venv\Scripts\python.exe scripts\review_app_icon.py
    cd app && dart run flutter_launcher_icons
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "app_icons"
ICONS = ROOT / "app" / "assets" / "icon"
SOURCE = ICONS / "qrguard_icon_source.png"
MASTER = 1024

# Match the source image's outer pixels so an opaque seam cannot appear around
# the adaptive foreground when Android applies its launcher mask.
BACKGROUND = "#000000"

# `flutter_launcher_icons` adds `<inset android:inset="16%">` around adaptive
# foreground and monochrome layers. At 0.85 source scale, the new artwork lands
# just inside Android's guaranteed 66/108 safe circle after that inset.
LAUNCHER_INSET = 0.16
FOREGROUND_SCALE = 0.85
MONOCHROME_THRESHOLD = 24


def load_square_source(size: int = MASTER) -> Image.Image:
    """Load the approved source without cropping or changing its aspect ratio."""
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Approved icon source is missing: {SOURCE}")

    source = Image.open(SOURCE).convert("RGBA")
    side = max(source.size)
    square = Image.new("RGBA", (side, side), BACKGROUND)
    offset = ((side - source.width) // 2, (side - source.height) // 2)
    square.alpha_composite(source, offset)
    return square.resize((size, size), Image.Resampling.LANCZOS)


def scaled_layer(image: Image.Image, scale: float) -> Image.Image:
    """Centre ``image`` on a transparent master at the requested scale."""
    target = round(image.width * scale)
    resized = image.resize((target, target), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    offset = ((image.width - target) // 2, (image.height - target) // 2)
    layer.alpha_composite(resized, offset)
    return layer


def render_monochrome(foreground: Image.Image) -> Image.Image:
    """Convert bright artwork details into a one-colour Android alpha mask."""
    red, green, blue, _ = foreground.split()
    brightest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    ramp = [
        0 if value <= MONOCHROME_THRESHOLD else min(255, (value - 20) * 2)
        for value in range(256)
    ]
    alpha = brightest.point(ramp)
    monochrome = Image.new("RGBA", foreground.size, "#FFFFFF")
    monochrome.putalpha(alpha)
    return monochrome


def build_launcher_assets() -> dict[str, Image.Image]:
    """Return the three masters consumed by ``flutter_launcher_icons``."""
    square = load_square_source()
    foreground = scaled_layer(square, FOREGROUND_SCALE)
    return {
        "qrguard_icon.png": square,
        "qrguard_icon_foreground.png": foreground,
        "qrguard_icon_monochrome.png": render_monochrome(foreground),
    }


def _proof(icon: Image.Image, target: int, zoom: int = 6) -> Image.Image:
    actual = icon.resize((target, target), Image.Resampling.LANCZOS)
    return actual.resize((target * zoom, target * zoom), Image.Resampling.NEAREST)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)

    assets = build_launcher_assets()
    for name, image in assets.items():
        image.save(ICONS / name)

    icon = assets["qrguard_icon.png"]
    icon.save(OUT / "replacement_icon_master_1024.png")
    for size in (128, 64, 40, 28):
        icon.resize((size, size), Image.Resampling.LANCZOS).save(
            OUT / f"replacement_icon_{size}.png"
        )
        _proof(icon, size).save(OUT / f"replacement_icon_{size}_proof.png")

    print(f"Source artwork: {SOURCE}")
    print(f"Launcher masters written to {ICONS}")
    for name in assets:
        print(" ", name)
    print(f"Size previews written to {OUT}")
    print("Now run:  cd app && dart run flutter_launcher_icons")


if __name__ == "__main__":
    main()
