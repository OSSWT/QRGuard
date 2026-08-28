"""Verify the Gemini API key works, without ever printing it.

Reads the key from (first match wins):
    .env                     GEMINI_API_KEY=...
    GEMINI_API_KEY.env.txt   GEMINI_API_KEY=...  (or a bare key on its own line)
    environment variable     GEMINI_API_KEY

Then makes one tiny real request. The prefix of a key does not tell you whether it is
valid -- only the API does -- so this is the ground truth check.

    python scripts\\check_gemini_key.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_FILES = (".env", "GEMINI_API_KEY.env.txt", "GEMINI_API_KEY.env", ".env.txt")

# Tried in order until one works. Free-tier availability varies by model and by how
# the project was created, so a 429 with "limit: 0" on one model does not mean the key
# is unusable -- another model may still have quota.
CANDIDATE_MODELS = (
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
)


def load_key() -> tuple[str, str]:
    """Return (key, where_it_came_from). Accepts KEY=value lines or a bare key."""
    for name in CANDIDATE_FILES:
        path = ROOT / name
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip().upper() == "GEMINI_API_KEY" and v.strip():
                    return v.strip().strip('"').strip("'"), name
            elif len(line) > 20:  # a bare key on its own line
                return line, f"{name} (bare line - add 'GEMINI_API_KEY=' prefix)"

    import os

    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"], "environment variable"

    sys.exit(
        "No key found. Put this in QRGuard\\.env or GEMINI_API_KEY.env.txt:\n"
        "    GEMINI_API_KEY=your_key_here"
    )


def _request(url: str, key: str, body: bytes | None = None):
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _error_message(e: urllib.error.HTTPError) -> str:
    detail = e.read().decode(errors="replace")
    try:
        return json.loads(detail)["error"]["message"].split("\n")[0]
    except Exception:
        return detail[:200]


def list_models(key: str) -> list[str]:
    """Which models does this key actually have access to?"""
    try:
        data = _request(
            "https://generativelanguage.googleapis.com/v1beta/models", key
        )
    except urllib.error.HTTPError as e:
        print(f"  could not list models: HTTP {e.code} - {_error_message(e)}")
        return []
    except Exception as e:  # noqa: BLE001
        print(f"  could not list models: {type(e).__name__}")
        return []

    names = [
        m["name"].removeprefix("models/")
        for m in data.get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    return names


def try_model(key: str, model: str) -> tuple[bool, str]:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent")
    body = json.dumps({
        "contents": [{"parts": [{"text": "Reply with exactly: OK"}]}],
        # Generous budget on purpose: current Gemini models spend "thinking" tokens
        # before emitting text, so a tight limit finishes with MAX_TOKENS and an
        # empty response even though the call itself succeeded.
        "generationConfig": {"temperature": 0, "maxOutputTokens": 256},
    }).encode()
    try:
        data = _request(url, key, body)
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {_error_message(e)}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"

    candidate = (data.get("candidates") or [{}])[0]
    parts = candidate.get("content", {}).get("parts")
    if not parts:
        return False, (f"empty response (finishReason="
                       f"{candidate.get('finishReason')}) - raise maxOutputTokens")
    return True, "".join(p.get("text", "") for p in parts).strip()


def main() -> None:
    key, source = load_key()
    print(f"Key loaded from : {source}")
    print("Key value       : loaded successfully and not displayed\n")

    available = list_models(key)
    if available:
        print(f"Models this key can see ({len(available)}):")
        for name in available[:12]:
            print(f"  - {name}")
        if len(available) > 12:
            print(f"  ... and {len(available) - 12} more")
        print("  (listing them proves AUTHENTICATION works)\n")

    # Prefer models the key can actually see, keeping our preference order.
    order = [m for m in CANDIDATE_MODELS if not available or m in available]
    order += [m for m in available if m not in order and "flash" in m][:3]

    print("Trying a real generateContent call:")
    for model in order:
        ok, detail = try_model(key, model)
        print(f"  {model:<28} {'OK  -> ' + repr(detail) if ok else detail}")
        if ok:
            print(f"\nSUCCESS - use model '{model}'. Method 2 (/deep-check) can use this key.")
            return

    print("\nNo model accepted the request.")
    print("If every model returned 429 with 'limit: 0', the key authenticates but the")
    print("project has no free-tier quota. Fixes, easiest first:")
    print("  1. Create the key in AI Studio (aistudio.google.com/app/apikey) against")
    print("     its 'Default Gemini Project' - Cloud Console projects often get 0 quota.")
    print("  2. Or enable billing on the project (pay-as-you-go is cents for this use).")
    print("  3. Or use a different provider - Method 2 is provider-agnostic.")
    sys.exit(1)


if __name__ == "__main__":
    main()
