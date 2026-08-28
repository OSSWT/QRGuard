"""Index QR-DN1.0 with its official QR-identity train/test separation."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
RAW_CANDIDATES = (
    ROOT / "ml_training/datasets/structural/raw/qrdn",
    ROOT / "ml_training/structural/raw/qrdn",
)
RAW = next((path for path in RAW_CANDIDATES if path.exists()), RAW_CANDIDATES[0])
OUTPUT = ROOT / "ml_training/datasets/structural/processed/qrdn"
MANIFEST = OUTPUT / "manifest.csv"
METHODS = ("extracted One", "extracted Quad", "extracted Voted")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    invalid: list[dict] = []
    seen_paths: set[Path] = set()
    for method in METHODS:
        for official_split, expected_count in (("train", 1500), ("test", 750)):
            directory = RAW / method / official_split
            paths = sorted(directory.glob("*.jpg"), key=lambda path: int(path.stem))
            if len(paths) != expected_count:
                raise ValueError(
                    f"{directory}: expected {expected_count} JPEGs, found {len(paths)}"
                )
            for path in paths:
                numeric_id = int(path.stem)
                qr_identity = numeric_id // 30
                capture_index = numeric_id % 30
                expected_split = "train" if qr_identity < 50 else "test"
                if official_split != expected_split:
                    raise ValueError(
                        f"official split/identity mismatch for {path}: QR {qr_identity}"
                    )
                try:
                    with Image.open(path) as image:
                        image.verify()
                    with Image.open(path) as image:
                        width, height = image.size
                except Exception as exc:  # noqa: BLE001 - audit every corrupt image
                    invalid.append({"path": path.as_posix(), "error": str(exc)})
                    continue
                if path in seen_paths:
                    raise ValueError(f"duplicate manifest path: {path}")
                seen_paths.add(path)
                rows.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "label": "clean",
                        "class_id": 0,
                        "split": (
                            "auxiliary_train" if official_split == "train" else "external_holdout_test"
                        ),
                        "official_split": official_split,
                        "group_id": f"qrdn:qr_identity:{qr_identity:02d}",
                        "qr_identity": qr_identity,
                        "capture_index": capture_index,
                        "extraction_method": method.removeprefix("extracted ").lower(),
                        "source": "QR-DN1.0",
                        "capture_kind": "real_screen_camera_watermark_extraction",
                        "is_exact_app_crop": False,
                        "licence": "CC-BY-4.0",
                        "width": width,
                        "height": height,
                        "sha256": _sha256(path),
                    }
                )
    if invalid:
        raise ValueError(f"QR-DN contains {len(invalid)} invalid images; see audit")
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    groups_by_split = {
        split: sorted({row["group_id"] for row in rows if row["official_split"] == split})
        for split in ("train", "test")
    }
    if set(groups_by_split["train"]) & set(groups_by_split["test"]):
        raise AssertionError("QR identity leakage between official train and test")
    audit = {
        "source": "https://data.mendeley.com/datasets/t2bdr663ms/2",
        "doi": "10.17632/t2bdr663ms.2",
        "licence": "CC-BY-4.0",
        "manifest_rows": len(rows),
        "rows_by_split": dict(Counter(row["official_split"] for row in rows)),
        "rows_by_method": dict(Counter(row["extraction_method"] for row in rows)),
        "qr_identities_by_split": {
            key: len(value) for key, value in groups_by_split.items()
        },
        "invalid_images": invalid,
        "leakage_control": (
            "Official train uses 50 QR identities (30 captures each); official test uses "
            "25 disjoint QR identities. The same identity/capture across extraction methods "
            "always remains in the same split."
        ),
        "label_scope": (
            "All rows are clean Structural examples with genuine acquisition/extraction "
            "noise; noise, lighting and reconstruction artefacts are capture conditions, "
            "not adversarial or physical-tampering labels."
        ),
    }
    (OUTPUT / "preparation_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
