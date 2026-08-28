"""Generate or verify the public research-evidence SHA-256 manifest."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "research_evidence"
MANIFEST = ROOT / "SNAPSHOT_MANIFEST.sha256"


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def render_manifest() -> str:
    files = sorted(
        (
            path
            for path in ROOT.rglob("*")
            if path.is_file() and path != MANIFEST and path.suffix.lower() != ".pdf"
        ),
        key=lambda path: path.relative_to(ROOT).as_posix().casefold(),
    )
    return "".join(
        f"{digest(path)} *{path.relative_to(ROOT).as_posix()}\n" for path in files
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the existing manifest instead of updating it",
    )
    args = parser.parse_args()
    expected = render_manifest()

    if args.check:
        actual = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
        if actual != expected:
            print("Research-evidence manifest is stale.")
            return 1
        print("Research-evidence manifest is current.")
        return 0

    MANIFEST.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Updated {MANIFEST.relative_to(ROOT.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
