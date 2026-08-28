r"""Show exactly how the Fusion Engine combines the two branches.

Prints the per-feature contribution table behind a verdict, so the "combine" step is
visible rather than a black box.

    python scripts\show_fusion.py                                   # built-in examples
    python scripts\show_fusion.py --url http://some-site.xyz/login  # any URL
    python scripts\show_fusion.py --url ... --image path\to\qr.png  # with an image
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fusion.engine import load_engine  # noqa: E402
from fusion.features import FEATURE_NAMES, BranchInputs, build_feature_vector  # noqa: E402
from semantic.domain_reputation import domain_unknown  # noqa: E402
from semantic.method1 import load_analyzer as load_method1  # noqa: E402
from semantic.payload_router import route_payload  # noqa: E402
from semantic.rule_engine import check_url  # noqa: E402

LINE = "-" * 66


def show(title: str, inputs: BranchInputs) -> None:
    engine = load_engine()
    x = build_feature_vector(inputs)

    print(f"\n{'=' * 66}\n{title}\n{'=' * 66}")
    print("  BRANCH OUTPUTS (the two things being combined)")
    print(f"    structural : p_structural = "
          f"{'abstained' if inputs.p_structural is None else f'{inputs.p_structural:.5f}'}")
    print(f"    semantic   : p_url        = "
          f"{'abstained' if inputs.p_url is None else f'{inputs.p_url:.5f}'}")
    print(f"                 domain_unknown = {inputs.domain_unknown}")
    print(f"                 rule_flags     = {list(inputs.rule_flags) or 'none'}")

    print(f"\n  FUSION: z = sum(weight x feature) + intercept\n  {LINE}")
    print(f"  {'feature':<28}{'value':>8}{'weight':>10}{'contribution':>15}")
    print(f"  {LINE}")
    total = 0.0
    for name, weight, value in zip(FEATURE_NAMES, engine.coef, x):
        contribution = float(weight * value)
        if abs(contribution) < 1e-9 and abs(value) < 1e-9:
            continue  # feature not present and carries no weight
        total += contribution
        print(f"  {name:<28}{value:>8.4f}{weight:>10.3f}{contribution:>15.3f}")
    print(f"  {'intercept':<28}{'':>8}{engine.intercept:>10.3f}{engine.intercept:>15.3f}")
    print(f"  {LINE}")

    z = total + engine.intercept
    p_fraud = 1.0 / (1.0 + np.exp(-z))
    result = engine.predict(inputs)
    print(f"  {'z':<28}{'':>18}{z:>15.3f}")
    print(f"  p_fraud = sigmoid(z) = {p_fraud:.4f}  ->  risk_score = {result.risk_score}")
    print(f"  tiers: safe < {engine.safe_max} <= warning < {engine.blocked_min} <= blocked"
          f"   ==>  {result.verdict.upper()}")
    if result.reasons:
        print("  reasons:")
        for reason in result.reasons:
            print(f"    - {reason}")


def signals_for(url: str, image_path: str | None):
    info = route_payload(url)
    flags = [f.flag for f in check_url(info)]
    p_url = None
    unknown = None
    if info.is_url and info.scheme in ("http", "https"):
        p_url = load_method1().predict(info.normalized_url or url).p_url
        unknown = domain_unknown(info.registered_domain)

    p_structural = None
    if image_path:
        from PIL import Image
        from structural.structural_service import load_analyzer as load_structural

        p_structural = load_structural().predict(Image.open(image_path)).p_structural

    return BranchInputs(p_structural=p_structural, p_url=p_url,
                        rule_flags=flags, domain_unknown=unknown)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", help="analyse this URL instead of the examples")
    ap.add_argument("--image", help="optional QR image for the structural branch")
    args = ap.parse_args()

    if args.url:
        show(f"{args.url}", signals_for(args.url, args.image))
        return

    # Built-in contrasts: each cell of the design, with one branch silent.
    show("1. Clean image + safe link  (both branches agree it is fine)",
         BranchInputs(p_structural=0.0001, p_url=0.0143, domain_unknown=0.0))

    show("2. Clean image + PHISHING link  (structural sees nothing; semantic carries it)",
         BranchInputs(p_structural=0.00005, p_url=0.9913, domain_unknown=1.0,
                      rule_flags=["non_https", "suspicious_tld"]))

    show("3. TAMPERED image + safe link  (semantic sees nothing; structural carries it)",
         BranchInputs(p_structural=0.9989, p_url=0.0143, domain_unknown=0.0))

    show("4. TAMPERED image, link undecodable  (semantic abstains entirely)",
         BranchInputs(p_structural=0.9989, p_url=None, domain_unknown=None))

    print(f"\n{'=' * 66}")
    print("Cases 2 and 3 are the point of the design: in each, ONE branch's number")
    print("is near zero, and the verdict rests entirely on the other. A single-branch")
    print("system would return SAFE for one of them.")
    print("=" * 66)


if __name__ == "__main__":
    main()
