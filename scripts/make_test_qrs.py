r"""Generate a set of labelled QR codes for manually testing the API.

Each file is named after what it should produce, so you can upload it at /docs and
immediately see whether the system agrees.

    python scripts\make_test_qrs.py

Output: data\test_qrs\  plus a README.md listing every case, its payload, and the
expected verdict.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "test_qrs"
IMG_SIZE = 224
SEED = 7

# (id, payload, image_treatment, expected_verdict, what it demonstrates)
CASES = [
    ("01_safe_google", "https://www.google.com/maps",
     "clean", "SAFE", "Clean image, well-known domain - the only genuinely safe case"),
    ("02_safe_youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
     "clean", "SAFE", "Clean image, another well-known domain"),
    ("03_safe_utar", "https://www.utar.edu.my/",
     "clean", "SAFE", "Clean image, a real university site"),

    ("04_phish_maybank", "http://maybank2u-verify.xyz/login/update.php",
     "clean", "BLOCKED", "IMAGE IS CLEAN - only the semantic branch catches this"),
    ("05_phish_paypal", "http://paypal-secure-verify.top/login/update.php",
     "clean", "BLOCKED", "Brand impersonation on an abused TLD"),
    ("06_phish_ip_host", "http://203.0.113.7/account/confirm",
     "clean", "BLOCKED", "Raw IP address instead of a domain name"),

    ("07_tampered_sticker", "https://www.google.com/maps",
     "sticker", "BLOCKED", "LINK IS SAFE - only the structural branch catches this"),
    ("08_tampered_occlusion", "https://www.youtube.com/",
     "occlusion", "BLOCKED", "A corner is covered - structural branch"),
    ("09_tampered_finder", "https://www.google.com/",
     "finder", "BLOCKED", "Finder pattern destroyed - structural branch"),
    ("10_tampered_blur", "https://www.google.com/maps",
     "blur", "SAFE", "Blur is capture distortion, not attacker tampering in the deployed RUN 5 model"),

    ("11_both_bad", "http://free-gift-card.win/claim?id=123",
     "sticker", "BLOCKED", "Both branches fire together"),

    ("12_shortened_link", "https://bit.ly/3xYzAb",
     "clean", "WARNING or BLOCKED", "Shortened link - try /deep-check on this one"),
    ("13_punycode", "http://xn--pypal-4ve.com/signin",
     "clean", "WARNING or BLOCKED", "Look-alike domain using punycode"),
    ("14_userinfo_trick", "http://www.paypal.com@evil-site.tk/login",
     "clean", "BLOCKED", "The '@' trick - real host is evil-site.tk"),
    ("15_deep_subdomains", "http://login.secure.account.verify.random-host.cf/auth",
     "clean", "WARNING or BLOCKED", "Excessive subdomain nesting"),

    ("16_wifi_open", "WIFI:T:nopass;S:FreeCafeWifi;;",
     "clean", "WARNING", "Non-URL payload - semantic branch abstains, rule fires"),
    ("17_wifi_secure", "WIFI:T:WPA;S:HomeNetwork;P:secret123;;",
     "clean", "SAFE", "Non-URL payload with proper encryption"),
    ("18_javascript_uri", "javascript:alert(document.cookie)",
     "clean", "BLOCKED", "Executable payload - hard override rule"),
    ("19_plain_text", "Table 12 - Order Number 4471",
     "clean", "SAFE", "Harmless text payload"),
    ("20_adversarial", "https://www.google.com/maps",
     "adversarial", "BLOCKED", "Invisible pixel noise - looks normal to you"),
]


def make_qr(content: str) -> Image.Image:
    import qrcode

    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data(content)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB").resize(
        (IMG_SIZE, IMG_SIZE)
    )


def apply_treatment(img: Image.Image, treatment: str, rng: random.Random) -> Image.Image:
    import cv2
    import numpy as np

    if treatment == "clean":
        return img

    if treatment == "adversarial":
        # Real FGSM noise against a ResNet-18 victim, as used in training.
        import torch
        import torchattacks
        from torchvision import models, transforms
        import torch.nn as nn

        victim = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1).eval()

        class NormModel(nn.Module):
            def __init__(self, m):
                super().__init__()
                self.m = m
                self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
                self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

            def forward(self, x):
                return self.m((x - self.mean) / self.std)

        wrapped = NormModel(victim).eval()
        x = transforms.ToTensor()(img).unsqueeze(0)
        with torch.no_grad():
            y = wrapped(x).argmax(1)
        adv = torchattacks.FGSM(wrapped, eps=0.03)(x, y)[0].detach().numpy()
        return Image.fromarray((np.clip(adv, 0, 1) * 255).astype(np.uint8).transpose(1, 2, 0))

    arr = np.array(img)
    h, w = arr.shape[:2]
    if treatment == "sticker":
        arr[70:140, 70:140] = (220, 40, 40)
    elif treatment == "occlusion":
        arr[10:70, 120:210] = 0
    elif treatment == "finder":
        arr[0:56, 0:56] = np.random.randint(0, 256, (56, 56, 3), dtype=np.uint8)
    elif treatment == "blur":
        arr = cv2.GaussianBlur(arr, (9, 9), 0)
    return Image.fromarray(arr)


def main() -> None:
    rng = random.Random(SEED)
    import numpy as np

    np.random.seed(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Test QR Codes",
        "",
        "Generated by `scripts\\make_test_qrs.py`. Upload any of these at "
        "http://127.0.0.1:8000/docs -> `POST /scan` -> **Try it out**.",
        "",
        "`/scan` needs BOTH fields: `payload` (the text below) and `image` (the PNG).",
        "The payload is what a real scanner would decode from that image.",
        "",
        "| File | Payload | Expected | What it demonstrates |",
        "|---|---|---|---|",
    ]

    for case_id, payload, treatment, expected, note in CASES:
        img = apply_treatment(make_qr(payload), treatment, rng)
        img.save(OUT / f"{case_id}.png")
        short = payload if len(payload) <= 46 else payload[:43] + "..."
        lines.append(f"| `{case_id}.png` | `{short}` | **{expected}** | {note} |")
        print(f"  {case_id}.png  ({treatment:<11}) -> expect {expected}")

    lines += [
        "",
        "## The two cases that prove the design",
        "",
        "- **04_phish_maybank** - the image is perfectly clean, so an image-only system",
        "  would let it through. Only the semantic branch catches it.",
        "- **07_tampered_sticker** - the link is `google.com`, so a link-only system would",
        "  let it through. Only the structural branch catches it.",
        "",
        "## Quick tips",
        "",
        "- `POST /analyze-url` needs only the payload (no image) - fastest way to test links.",
        "- `POST /deep-check` runs the LLM. Try it on `12_shortened_link`.",
        "- Scans without an image return `partial_analysis: true`.",
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{len(CASES)} test QR codes written to {OUT}")
    print(f"See {OUT / 'README.md'} for payloads and expected verdicts.")


if __name__ == "__main__":
    main()
