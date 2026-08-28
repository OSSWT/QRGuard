r"""Hands-on demo of every finished QRGuard component.

Run from the repo root:
    python scripts\demo.py

Shows, for a few example scans, what each module produces and how the Fusion Engine
turns those signals into a Safe / Warning / Blocked verdict.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image, ImageDraw  # noqa: E402

from fusion.engine import load_engine  # noqa: E402
from fusion.features import BranchInputs  # noqa: E402
from semantic.method1 import load_analyzer as load_method1  # noqa: E402
from semantic.payload_router import route_payload  # noqa: E402
from semantic.rule_engine import check_url  # noqa: E402
from structural.structural_service import load_analyzer as load_structural  # noqa: E402

LINE = "=" * 72


def make_qr(content: str) -> Image.Image:
    import qrcode

    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data(content)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB").resize(
        (224, 224)
    )


def add_sticker(img: Image.Image) -> Image.Image:
    """Simulate the classic sticker-overlay QR fraud."""
    out = img.copy()
    ImageDraw.Draw(out).rectangle([60, 60, 130, 130], fill=(220, 40, 40))
    return out


def scan(url: str, image: Image.Image, label: str, structural, method1, fusion) -> None:
    print(f"\n{LINE}\n{label}\n  payload: {url}\n{LINE}")

    # --- Structural branch: looks at the IMAGE ---
    s = structural.predict(image)
    print(f"  [structural]  p_structural={s.p_structural:.4f}  type={s.predicted_type}")

    # --- Semantic branch: looks at the DECODED TEXT ---
    info = route_payload(url)
    flags = check_url(info)
    p_url = method1.predict(info.normalized_url or url).p_url
    print(f"  [method 1  ]  p_url={p_url:.4f}   domain={info.registered_domain}")
    if flags:
        for f in flags:
            print(f"  [rule      ]  {f.flag}: {f.evidence}")
    else:
        print("  [rule      ]  no flags")

    # --- Fusion: combine into one verdict ---
    result = fusion.predict(
        BranchInputs(
            p_structural=s.p_structural,
            p_url=p_url,
            rule_flags=[f.flag for f in flags],
        )
    )
    icon = {"safe": "[SAFE]", "warning": "[WARNING]", "blocked": "[BLOCKED]"}[result.verdict]
    print(f"\n  ==> {icon}  risk score {result.risk_score}/100")
    for reason in result.reasons:
        print(f"       - {reason}")


def main() -> None:
    print("Loading models (first call pays the load cost)...")
    structural = load_structural()
    method1 = load_method1()
    fusion = load_engine()
    print(f"  structural : {structural.model_path.name}")
    print(f"  method 1   : {method1.model_path.name}")
    print(f"  fusion     : safe<{fusion.safe_max}  warning<{fusion.blocked_min}  blocked>=")

    benign = "https://www.google.com/maps"
    phishing = "http://maybank2u-verify.xyz/login/update.php"

    # 1. clean image + benign link -> the only genuinely safe combination
    scan(benign, make_qr(benign), "1. Clean QR, safe link",
         structural, method1, fusion)

    # 2. clean image + phishing link -> the structural branch sees nothing wrong;
    #    only the semantic branch catches this
    scan(phishing, make_qr(phishing), "2. Clean QR, PHISHING link "
         "(image looks fine - semantic branch catches it)",
         structural, method1, fusion)

    # 3. sticker-covered image + benign link -> the semantic branch sees nothing
    #    wrong; only the structural branch catches this
    scan(benign, add_sticker(make_qr(benign)), "3. STICKER-COVERED QR, safe link "
         "(link looks fine - structural branch catches it)",
         structural, method1, fusion)

    print(f"\n{LINE}")
    print("Cases 2 and 3 are why the system needs BOTH branches:")
    print("  - an image-only system would let case 2 through")
    print("  - a link-only system would let case 3 through")
    print(LINE)


if __name__ == "__main__":
    main()
