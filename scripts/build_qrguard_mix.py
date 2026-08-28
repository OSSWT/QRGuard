"""Build QRGuard-Mix v2 — the ground-truth set for Fusion training/evaluation.

Covers image manipulation crossed with the payload families the app really sees:

                    benign URL        phishing URL
    gallery clean       -> SAFE           -> dangerous
    gallery tampered    -> dangerous      -> dangerous
    gallery adversarial -> dangerous      -> dangerous
    camera clean consensus / uncertain abstention / tampered consensus

    benign URL / phishing URL / open Wi-Fi / secure Wi-Fi / text / executable URI

Open Wi-Fi is intentionally a Warning target, not fraud. Earlier mixes contained
only URLs, leaving ``open_wifi_network`` unidentifiable and forcing a manual floor.
The v2 manifest carries a fractional ``risk_target`` for fitting and an explicit
``target_tier`` for per-cell deployment gates. Image manipulation or executable /
phishing content remains Blocked; clean secure Wi-Fi and plain text remain Safe.

The manipulation code is copied verbatim from the structural training notebook so the CNN
sees the same distribution it was trained on.

URL SOURCE AND LEAKAGE
Method 1 was trained on domains from PhiUSIIL + malicious_phish + Tranco. If QRGuard-Mix
reused those domains, p_url would be optimistic and the fusion weights would over-trust the
semantic branch. Preference order:
  1. data/method1/heldout_test.parquet|csv  -- Method 1's own held-out test split (best)
  2. fallback: sample from the local CSVs, marking leakage_risk="unknown" in the manifest

Usage:
    python scripts/build_qrguard_mix.py                 # 150 per cell = 5400 samples
    python scripts/build_qrguard_mix.py --per-cell 50   # report run = 1800 samples
"""

from __future__ import annotations

import argparse
import hashlib
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_DIR = DATA / "qrguard_mix_v2"
IMG_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

EVIDENCE_MODES = (
    "gallery_clean",
    "gallery_tampered",
    "gallery_adversarial",
    "camera_clean_consensus",
    "camera_uncertain_abstain",
    "camera_tampered_consensus",
)
PAYLOAD_KINDS = (
    "benign_url",
    "phishing_url",
    "wifi_open",
    "wifi_secure",
    "plain_text",
    "executable_uri",
)
SEED = 42


# ---------------------------------------------------------------------------
# URL sourcing
# ---------------------------------------------------------------------------

def load_url_pool() -> tuple[pd.DataFrame, str]:
    """Return (dataframe with url+label, leakage_risk tag)."""
    for name in ("heldout_test.parquet", "heldout_test.csv"):
        path = DATA / "method1" / name
        if path.is_file():
            df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
            print(f"URL source: {name} (Method 1 held-out test split -- no leakage)")
            return df[["url", "label"]].dropna(), "none"

    print(
        "WARNING: Method 1 held-out test split not found.\n"
        "         Falling back to the full local CSVs. Some URLs may have been seen\n"
        "         during Method 1 training, which makes p_url optimistic on those rows.\n"
        "         To fix: download run3_augmented/splits/test.parquet from Drive to\n"
        "         data/method1/heldout_test.parquet and re-run.",
        file=sys.stderr,
    )
    frames = []
    phi = DATA / "method1" / "phiusiil.csv"
    if phi.is_file():
        frames.append(pd.read_csv(phi)[["url", "label"]])
    mal = DATA / "method1" / "malicious_phish.csv"
    if mal.is_file():
        m = pd.read_csv(mal)
        m["label"] = (m["type"] != "benign").astype(int)
        frames.append(m[["url", "label"]])
    if not frames:
        sys.exit("No URL datasets found in data/method1/. See data/method1/README.md.")
    return pd.concat(frames, ignore_index=True).dropna(), "unknown"


# ---------------------------------------------------------------------------
# Image generation (must match the structural training notebook)
# ---------------------------------------------------------------------------

def make_qr(content: str) -> Image.Image:
    import qrcode

    stable_seed = int.from_bytes(hashlib.sha256(content.encode()).digest()[:8], "big")
    rng = random.Random(stable_seed)
    qr = qrcode.QRCode(
        version=None,
        error_correction=rng.choice(
            [
                qrcode.constants.ERROR_CORRECT_L,
                qrcode.constants.ERROR_CORRECT_M,
                qrcode.constants.ERROR_CORRECT_Q,
                qrcode.constants.ERROR_CORRECT_H,
            ]
        ),
        box_size=rng.randint(6, 12),
        border=rng.randint(2, 5),
    )
    qr.add_data(content)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB").resize(
        (IMG_SIZE, IMG_SIZE)
    )


def make_tampered(img: Image.Image, rng: random.Random) -> Image.Image:
    """Synthetic physical tampering -- identical recipe to structural training.

    `blur` was dropped here to follow the structural specification: blur
    describes how a code was captured, not what an attacker did to it. Leaving it
    in produced a measurable defect rather than a merely inconsistent one -- the
    mix contained blur-only images labelled dangerous, the retrained CNN
    correctly called them clean, and fusion counted that as a missed attack. Four
    of the seven samples that leaked into the Safe tier were exactly this.

    Sticker sizes also start smaller, matching the severity range the CNN now
    trains on, so the mix contains attacks near the detection limit instead of
    only obvious ones.
    """
    import cv2

    im = np.array(img.resize((IMG_SIZE, IMG_SIZE)).convert("RGB"))
    H, W = im.shape[:2]
    for op in rng.sample(["sticker", "occlude", "finder", "scratch"],
                         k=rng.randint(1, 2)):
        if op == "sticker":
            w, h = rng.randint(W // 12, W // 3), rng.randint(H // 12, H // 3)
            x, y = rng.randint(0, W - w), rng.randint(0, H - h)
            im[y:y + h, x:x + w] = rng.choice(
                [(255, 255, 255), (0, 0, 0), (220, 40, 40), (40, 120, 220)]
            )
        elif op == "occlude":
            w, h = rng.randint(W // 10, W // 2), rng.randint(H // 12, H // 4)
            x, y = rng.randint(0, W - w), rng.randint(0, H - h)
            im[y:y + h, x:x + w] = rng.choice([0, 255])
        elif op == "finder":
            cy, cx = rng.choice([(0, 0), (0, W - W // 4), (H - H // 4, 0)])
            s = W // 4
            patch = im[cy:cy + s, cx:cx + s]
            patch[:] = np.random.randint(0, 256, patch.shape, dtype=np.uint8)
        elif op == "scratch":
            for _ in range(rng.randint(1, 5)):
                cv2.line(
                    im,
                    (rng.randint(0, W), rng.randint(0, H)),
                    (rng.randint(0, W), rng.randint(0, H)),
                    rng.choice([0, 255]),
                    rng.randint(2, 5),
                )
    return Image.fromarray(im)


class AdversarialMaker:
    """FGSM / PGD generator against a ResNet-18 victim -- the FYP1 method."""

    def __init__(self) -> None:
        import torch
        import torch.nn as nn
        from torchvision import models, transforms

        self.torch = torch
        self.to_tensor = transforms.ToTensor()

        victim = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1).eval()

        class NormModel(nn.Module):
            def __init__(self, m, mean, std):
                super().__init__()
                self.m = m
                self.register_buffer("mean", torch.tensor(mean).view(1, 3, 1, 1))
                self.register_buffer("std", torch.tensor(std).view(1, 3, 1, 1))

            def forward(self, x):
                return self.m((x - self.mean) / self.std)

        self.norm_victim = NormModel(victim, IMAGENET_MEAN, IMAGENET_STD).eval()

    def __call__(self, img: Image.Image, rng: random.Random) -> Image.Image:
        import torchattacks

        x = self.to_tensor(img.resize((IMG_SIZE, IMG_SIZE)).convert("RGB")).unsqueeze(0)
        with self.torch.no_grad():
            y = self.norm_victim(x).argmax(1)
        eps = rng.uniform(0.01, 0.05)
        atk = (
            torchattacks.FGSM(self.norm_victim, eps=eps)
            if rng.random() < 0.5
            else torchattacks.PGD(self.norm_victim, eps=eps, alpha=0.005, steps=40)
        )
        adv = atk(x, y)[0].detach().numpy()
        return Image.fromarray(
            (np.clip(adv, 0, 1) * 255).astype(np.uint8).transpose(1, 2, 0)
        )


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def _payload(kind: str, index: int, benign: list[str], phish: list[str]) -> str:
    if kind == "benign_url":
        return benign[index]
    if kind == "phishing_url":
        return phish[index]
    if kind == "wifi_open":
        return f"WIFI:T:nopass;S:QRGuard-Cafe-{index:04d};;"
    if kind == "wifi_secure":
        return (
            f"WIFI:T:WPA;S:QRGuard-Office-{index:04d};"
            f"P:TrainingOnly-{index:04d};;"
        )
    if kind == "plain_text":
        return f"QRGuard non-URL receipt reference {index:06d}"
    if kind == "executable_uri":
        return f"javascript:location='https://account-check-{index:04d}.test/'"
    raise ValueError(f"unsupported payload kind: {kind}")


def _target(evidence_mode: str, payload_kind: str) -> tuple[float, str, int]:
    manipulated = evidence_mode in {
        "tampered",  # legacy caller compatibility
        "adversarial",
        "gallery_tampered",
        "gallery_adversarial",
        "camera_tampered_consensus",
    }
    if manipulated or payload_kind in {"phishing_url", "executable_uri"}:
        return 0.98, "blocked", 1
    if payload_kind == "wifi_open":
        return 0.40, "warning", 0
    return 0.02, "safe", 0


def build(per_cell: int) -> None:
    rng = random.Random(SEED)
    np.random.seed(SEED)

    pool, leakage = load_url_pool()
    benign = pool[pool.label == 0]["url"].astype(str)
    phish = pool[pool.label == 1]["url"].astype(str)
    need = per_cell * len(EVIDENCE_MODES)
    if len(benign) < need or len(phish) < need:
        sys.exit(f"URL pool too small: need {need} of each, have "
                 f"{len(benign)} benign / {len(phish)} phishing.")

    benign = benign.sample(need, random_state=SEED).tolist()
    phish = phish.sample(need, random_state=SEED).tolist()

    img_dir = OUT_DIR / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    adversarial = AdversarialMaker()  # loads ResNet-18 once

    rows = []
    idx = 0
    for evidence_index, evidence_mode in enumerate(EVIDENCE_MODES):
        benign_chunk = benign[evidence_index * per_cell :][:per_cell]
        phish_chunk = phish[evidence_index * per_cell :][:per_cell]
        image_class = (
            "tampered"
            if "tampered" in evidence_mode
            else "adversarial"
            if "adversarial" in evidence_mode
            else "clean"
        )
        for payload_kind in PAYLOAD_KINDS:
            for sample_index in range(per_cell):
                content = _payload(
                    payload_kind,
                    sample_index,
                    benign_chunk,
                    phish_chunk,
                )
                img = make_qr(content[:2000])  # QR capacity guard
                if image_class == "tampered":
                    img = make_tampered(img, rng)
                elif image_class == "adversarial":
                    img = adversarial(img, rng)

                name = f"{idx:05d}_{evidence_mode}_{payload_kind}.png"
                img.save(img_dir / name)
                risk_target, target_tier, dangerous = _target(
                    evidence_mode, payload_kind
                )
                rows.append(
                    {
                        "filename": name,
                        "payload": content,
                        # Retained for older analysis notebooks; it is the full
                        # payload now, not necessarily a URL.
                        "url": content,
                        "payload_kind": payload_kind,
                        "url_label": int(payload_kind == "phishing_url"),
                        "image_class": image_class,      # clean / tampered / adversarial
                        "evidence_mode": evidence_mode,
                        "image_manipulated": int(
                            evidence_mode
                            in {
                                "gallery_tampered",
                                "gallery_adversarial",
                                "camera_tampered_consensus",
                            }
                        ),
                        "risk_target": risk_target,
                        "target_tier": target_tier,
                        "dangerous": dangerous,
                        "cell": f"{evidence_mode}_{payload_kind}",
                        "image_source": (
                            "camera" if evidence_mode.startswith("camera_") else "gallery"
                        ),
                        "leakage_risk": (
                            leakage if payload_kind.endswith("url") else "none"
                        ),
                    }
                )
                idx += 1
            print(f"  {evidence_mode:<28} {payload_kind:<15} {per_cell} images")

    manifest = pd.DataFrame(rows)
    manifest.to_csv(OUT_DIR / "manifest.csv", index=False)

    # A previous schema used shorter filenames in the same generated directory.
    # Keep the dataset self-contained: files not named by this run's manifest are
    # stale build products and must not affect counts or fingerprints.
    expected_images = set(manifest["filename"].astype(str))
    for stale_path in img_dir.glob("*.png"):
        if stale_path.name not in expected_images:
            stale_path.unlink()

    print(f"\nQRGuard-Mix written to {OUT_DIR}")
    print(f"  images   : {len(manifest)}")
    print(
        f"  blocked truth: {manifest.dangerous.sum()}  "
        f"non-blocked: {(1 - manifest.dangerous).sum()}"
    )
    print(f"  leakage  : {leakage}")
    print("\nPer-cell counts:")
    print(manifest.groupby("cell").size().to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-cell", type=int, default=150,
                    help="samples per combination (18 cells total)")
    build(ap.parse_args().per_cell)
