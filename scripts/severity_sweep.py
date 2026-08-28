r"""Measure the structural branch's DETECTION LIMIT, not just its accuracy.

WHY THIS EXISTS. A single recall figure answers "does it work?" with a number
that is either near 1.0 and unfalsifiable, or low and unexplained. The honest
question is "how small an attack can it still catch?", and that has an answer
with a shape: recall against attack strength. Attacks near the limit pull recall
down for a reason you can state and defend, instead of leaving a bare 1.0000
that a reader has no way to interrogate.

It also separates two things the headline number conflates: attacks are easier
to spot on a pristine render than through a camera, so every level is measured
both ways.

    python scripts\severity_sweep.py            # ~40 codes per cell
    python scripts\severity_sweep.py --n 100    # tighter, slower

Runs against whatever model is installed in training/artifacts/structural/.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import cv2
import numpy as np
import qrcode
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

IMG_SIZE = 224
NB = ROOT / "training" / "structural_efficientnet_3class.ipynb"

# Fraction of the code's AREA covered by the sticker. The low end is deliberately
# below anything the training set contains.
STICKER_AREA = [0.002, 0.005, 0.01, 0.02, 0.04, 0.08, 0.16, 0.30]
# Perturbation budget. 0.05 is the top of the training range; 0.0005 is far below.
ADV_EPS = [0.0005, 0.001, 0.002, 0.004, 0.01, 0.02, 0.05]


def load_simulate_capture():
    """Reuse the notebook's own camera simulation, so this measures the same
    transformation the model was trained against rather than an approximation."""
    nb = json.loads(NB.read_text(encoding="utf-8"))
    src = "".join(nb["cells"][5]["source"])
    code = src[src.index("# ---- camera simulation"):src.index("# ---- build the 3-class dataset")]
    g = {"np": np, "cv2": cv2, "math": math, "Image": Image, "random": random,
         "nprng": np.random.RandomState(0)}
    exec(compile(code, "<sim>", "exec"), g)
    return g["simulate_capture"]


def clean_codes(n: int, rng: random.Random) -> list[Image.Image]:
    out = []
    for i in range(n):
        qr = qrcode.QRCode(
            error_correction=rng.choice([
                qrcode.constants.ERROR_CORRECT_L, qrcode.constants.ERROR_CORRECT_M,
                qrcode.constants.ERROR_CORRECT_Q, qrcode.constants.ERROR_CORRECT_H]),
            box_size=rng.randint(6, 12), border=rng.randint(1, 6))
        qr.add_data(f"https://sweep{i}.example.com/{rng.randint(1000, 99999)}")
        qr.make(fit=True)
        out.append(qr.make_image(fill_color="black", back_color="white")
                   .convert("RGB").resize((IMG_SIZE, IMG_SIZE)))
    return out


def sticker(img: Image.Image, area: float, rng: random.Random) -> Image.Image:
    """Opaque patch covering `area` of the code, placed off-centre like a real one."""
    im = np.array(img).copy()
    H, W = im.shape[:2]
    side = max(2, int(round(math.sqrt(area * W * H))))
    x, y = rng.randint(0, W - side), rng.randint(0, H - side)
    im[y:y+side, x:x+side] = rng.choice([(255, 255, 255), (0, 0, 0),
                                         (220, 40, 40), (40, 120, 220)])
    return Image.fromarray(im)


def adversarial_maker():
    """FGSM/PGD against a ResNet-18, the same construction the notebook uses."""
    try:
        import torch
        import torchattacks
        from torchvision import models, transforms
    except ImportError as exc:
        print(f"  (adversarial sweep skipped: {exc})")
        return None

    import torch.nn as nn
    try:
        victim = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1).eval()
    except Exception as exc:                      # no cached weights, no network
        print(f"  (adversarial sweep skipped: could not load ResNet-18 - {exc})")
        return None

    mean, std = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]

    class Norm(nn.Module):
        def __init__(s, m):
            super().__init__(); s.m = m
            s.register_buffer("mean", torch.tensor(mean).view(1, 3, 1, 1))
            s.register_buffer("std", torch.tensor(std).view(1, 3, 1, 1))
        def forward(s, x):
            return s.m((x - s.mean) / s.std)

    net = Norm(victim).eval()
    to_tensor = transforms.ToTensor()

    def make(img: Image.Image, eps: float, rng: random.Random) -> Image.Image:
        x = to_tensor(img).unsqueeze(0)
        with torch.no_grad():
            y = net(x).argmax(1)
        atk = (torchattacks.FGSM(net, eps=eps) if rng.random() < 0.5
               else torchattacks.PGD(net, eps=eps, alpha=eps / 4, steps=20))
        adv = atk(x, y)[0].detach().numpy()
        return Image.fromarray((np.clip(adv, 0, 1) * 255).astype(np.uint8).transpose(1, 2, 0))

    return make


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=40, help="codes per severity level")
    args = ap.parse_args()

    from structural.structural_service import predict_structural

    simulate_capture = load_simulate_capture()
    rng = random.Random(17)
    base = clean_codes(args.n, rng)

    def recall(images, want_attacked=True):
        """Share judged attacked (p_structural >= 0.5)."""
        hits = sum((predict_structural(im).p_structural >= 0.5) == want_attacked
                   for im in images)
        return hits / len(images)

    results = {"n_per_level": args.n, "sticker": [], "adversarial": []}

    print(f"Model: {json.loads((ROOT / 'training/artifacts/structural/temperature.json').read_text())['temperature']:.4f} "
          f"temperature | {args.n} codes per level\n")

    # Reference row: clean codes must NOT be flagged, either way.
    fp_pristine = 1 - recall(base, want_attacked=False)
    shot = [simulate_capture(im, rng) for im in base]
    fp_camera = 1 - recall(shot, want_attacked=False)
    print(f"clean codes wrongly flagged:  pristine {fp_pristine:.3f}   camera {fp_camera:.3f}\n")
    results["clean_false_positive"] = {"pristine": fp_pristine, "camera": fp_camera}

    print("STICKER  (fraction of the code's area covered)")
    print(f"{'area':>8}{'side':>8}{'pristine':>11}{'camera':>9}")
    for area in STICKER_AREA:
        atk = [sticker(im, area, rng) for im in base]
        r_p = recall(atk)
        r_c = recall([simulate_capture(im, rng) for im in atk])
        side = int(round(math.sqrt(area * IMG_SIZE * IMG_SIZE)))
        print(f"{area*100:>7.1f}%{side:>7}px{r_p:>11.3f}{r_c:>9.3f}")
        results["sticker"].append({"area": area, "pristine": r_p, "camera": r_c})

    make_adv = adversarial_maker()
    if make_adv:
        print("\nADVERSARIAL  (FGSM/PGD perturbation budget)")
        print(f"{'eps':>8}{'pristine':>11}{'camera':>9}")
        for eps in ADV_EPS:
            atk = [make_adv(im, eps, rng) for im in base]
            r_p = recall(atk)
            r_c = recall([simulate_capture(im, rng) for im in atk])
            print(f"{eps:>8.4f}{r_p:>11.3f}{r_c:>9.3f}")
            results["adversarial"].append({"eps": eps, "pristine": r_p, "camera": r_c})

    def limit(rows, key, field):
        """Smallest severity still caught at >= 95%."""
        ok = [r[key] for r in rows if r[field] >= 0.95]
        return min(ok) if ok else None

    print("\nDETECTION LIMIT  (smallest attack still caught at >= 95%)")
    for name, rows, key, unit in (("sticker", results["sticker"], "area", "of area"),
                                  ("adversarial", results["adversarial"], "eps", "eps")):
        if not rows:
            continue
        for field in ("pristine", "camera"):
            v = limit(rows, key, field)
            shown = "not reached" if v is None else (
                f"{v*100:.1f}% {unit}" if key == "area" else f"{v:.4f} {unit}")
            print(f"  {name:<12} {field:<9} {shown}")

    out = ROOT / "data" / "severity_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\nwrote", out)


if __name__ == "__main__":
    main()
