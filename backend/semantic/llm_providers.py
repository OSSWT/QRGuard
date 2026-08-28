"""LLM providers for Method 2.

`method2.analyze()` takes an injected `llm_call(system_prompt, user_message) -> str`,
so the analyzer itself stays provider-agnostic and fully testable offline. This module
supplies the real implementations.

Gemini notes learned from probing the API:
- Current Gemini models spend "thinking" tokens before emitting any text. With a small
  `maxOutputTokens` the call succeeds but returns a candidate with **no parts** and
  `finishReason: MAX_TOKENS`. The budget here is therefore generous.
- Free-tier quota is granted per model, not per project: `gemini-2.0-flash` can return
  429 `limit: 0` while `gemini-flash-latest` works on the same key. `MODEL` defaults to
  the latter and is overridable via `QRGUARD_GEMINI_MODEL`.
- The key is read from `.env` / `GEMINI_API_KEY.env.txt` / the environment. It is never
  logged, and never included in an error message returned to the caller.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[2]
_KEY_FILES = (".env", "GEMINI_API_KEY.env.txt", "GEMINI_API_KEY.env", ".env.txt")

# flash-lite over flash: measured on this task, `gemini-flash-latest` spends ~330
# thinking tokens and takes ~7 s, while `gemini-flash-lite-latest` answers in ~1 s with
# no thinking phase and the same verdict. A deep check is user-initiated, so a 7 s wait
# would be felt directly. (`thinkingBudget: 0` is rejected with HTTP 400 on these
# models, so model choice is the lever, not configuration.)
DEFAULT_MODEL = "gemini-flash-lite-latest"
MAX_OUTPUT_TOKENS = 1024   # headroom for any thinking phase plus the JSON verdict
TIMEOUT_S = 20.0


class LLMUnavailable(RuntimeError):
    """Raised when no usable LLM credential is configured."""


@lru_cache(maxsize=1)
def load_api_key() -> Optional[str]:
    """Find GEMINI_API_KEY in the environment or a local key file. Never logged."""
    if os.environ.get("GEMINI_API_KEY", "").strip():
        return os.environ["GEMINI_API_KEY"].strip()

    for name in _KEY_FILES:
        path = _ROOT / name
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip().upper() == "GEMINI_API_KEY" and value.strip():
                return value.strip().strip('"').strip("'")
    return None


def is_configured() -> bool:
    """True when a deep check can actually be performed."""
    return bool(load_api_key())


def gemini_llm_call(system_prompt: str, user_message: str) -> str:
    """Call Gemini and return the model's raw text. Raises on failure.

    `method2.analyze()` catches every exception and degrades to a cautious
    "suspicious" verdict, so raising here is the correct behaviour.
    """
    api_key = load_api_key()
    if not api_key:
        raise LLMUnavailable(
            "No GEMINI_API_KEY found. Add it to QRGuard/.env as GEMINI_API_KEY=..."
        )

    model = os.environ.get("QRGUARD_GEMINI_MODEL", DEFAULT_MODEL)
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent")
    payload = {
        # Gemini takes the system prompt separately from the conversation turns.
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {
            "temperature": 0,           # reproducible verdicts
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            message = json.loads(detail)["error"]["message"].split("\n")[0]
        except Exception:
            message = detail[:200]
        raise RuntimeError(f"Gemini HTTP {exc.code}: {message}") from None

    candidate = (data.get("candidates") or [{}])[0]
    parts = candidate.get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError(
            f"Gemini returned no text (finishReason={candidate.get('finishReason')})"
        )
    return text


def get_default_call():
    """The provider the API should use, or None when nothing is configured."""
    return gemini_llm_call if is_configured() else None
