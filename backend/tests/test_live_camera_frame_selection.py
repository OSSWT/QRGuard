from __future__ import annotations

import hashlib
import io

from PIL import Image
from structural.image_quality import assess_image_quality

from scripts.analyze_live_camera_diagnostic import ValidatedFrame
from scripts.evaluate_live_camera_candidate import _rank_capture_frames


def _checker(low: int, high: int) -> bytes:
    image = Image.new("RGB", (300, 300))
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            value = high if (x // 8 + y // 8) % 2 else low
            pixels[x, y] = (value, value, value)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _frame(case_id: str, raw: bytes, index: int) -> ValidatedFrame:
    return ValidatedFrame(
        session_id=case_id.lower().ljust(24, "0")[:24],
        case_id=case_id,
        ground_truth="clean",
        distance="screen_80",
        repeat_index=1,
        frame_index=index,
        crop_name=f"{case_id}.png",
        crop_sha256=hashlib.sha256(raw).hexdigest(),
        crop_png=raw,
        crop_width=300,
        crop_height=300,
        frame_width=600,
        frame_height=600,
        corner_coordinates=(100, 100, 500, 100, 500, 500, 100, 500),
        qr_coverage=4 / 9,
        payload_sha256="0" * 64,
    )


def test_pixel_quality_rank_keeps_normal_frames_ahead_of_overexposed_frames() -> None:
    normal = _checker(0, 255)
    overexposed = _checker(100, 220)
    assert assess_image_quality(Image.open(io.BytesIO(normal))).status == "usable"
    assert assess_image_quality(Image.open(io.BytesIO(overexposed))).status == "marginal"
    frames = [
        _frame("marginal-1", overexposed, 0),
        _frame("normal-1", normal, 1),
        _frame("marginal-2", overexposed, 2),
        _frame("normal-2", normal, 3),
        _frame("marginal-3", overexposed, 4),
    ]

    ranked = _rank_capture_frames(frames)

    assert {row.case_id for row in ranked[:2]} == {"normal-1", "normal-2"}
    assert ranked[2].case_id.startswith("marginal")


def test_pixel_quality_rank_excludes_unusable_frames() -> None:
    normal = _checker(0, 255)
    flat = _checker(240, 240)

    ranked = _rank_capture_frames(
        [_frame("flat", flat, 0), _frame("normal", normal, 1)]
    )

    assert [row.case_id for row in ranked] == ["normal"]
