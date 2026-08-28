"""Download only the QR-relevant portions of Dynamsoft's official dataset repo."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOWNLOADS = ROOT / "ml_training/datasets/holdout/downloads"
OUTPUT = ROOT / "ml_training/datasets/holdout/raw/dynamsoft"
RAW_BASE = "https://raw.githubusercontent.com/Dynamsoft/datasets-from-dynamsoft/main"


def git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()


def selected() -> list[dict]:
    specs = []
    for tree_name, prefix in (
        ("dynamsoft_challenging_tree.json", "challenging-images"),
        ("dynamsoft_video_tree.json", "video-based-testing"),
    ):
        tree = json.loads((DOWNLOADS / tree_name).read_text(encoding="utf-8"))["tree"]
        for item in tree:
            if item["type"] != "blob":
                continue
            path = item["path"]
            if prefix == "video-based-testing" and "qrcode" not in path.lower():
                continue
            specs.append({**item, "prefix": prefix})
    return specs


def download(item: dict) -> dict:
    relative = Path(item["prefix"]) / Path(item["path"])
    destination = OUTPUT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if (
        destination.is_file()
        and destination.stat().st_size == item["size"]
        and git_blob_sha(destination) == item["sha"]
    ):
        return {"path": relative.as_posix(), "status": "verified_cached", "bytes": item["size"]}

    url_path = "/".join(urllib.parse.quote(part) for part in relative.parts)
    request = urllib.request.Request(
        f"{RAW_BASE}/{url_path}", headers={"User-Agent": "QRGuard-Research"}
    )
    temporary = destination.with_suffix(destination.suffix + ".part")
    last_error = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                temporary.write_bytes(response.read())
            if temporary.stat().st_size != item["size"]:
                raise ValueError(
                    f"size {temporary.stat().st_size} != expected {item['size']}"
                )
            if git_blob_sha(temporary) != item["sha"]:
                raise ValueError("Git blob SHA mismatch")
            temporary.replace(destination)
            return {"path": relative.as_posix(), "status": "downloaded", "bytes": item["size"]}
        except Exception as exc:  # retry transient GitHub/network failures
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"failed {relative}: {last_error}")


def main() -> None:
    files = selected()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(download, files))
    manifest = {
        "source": "https://github.com/Dynamsoft/datasets-from-dynamsoft",
        "selection": "all challenging-images blobs plus QR-named video blobs",
        "files": results,
        "total_files": len(results),
        "total_bytes": sum(item["bytes"] for item in results),
        "licence_status": "quarantined_pending_per-folder_terms",
        "training_use": False,
        "holdout_use": True,
    }
    (OUTPUT / "acquisition_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in manifest.items() if key != "files"}, indent=2))


if __name__ == "__main__":
    main()
