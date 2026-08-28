"""Method 1 — String-Level Semantic Analyzer (DomURLs_BERT inference).

Runs the fine-tuned DomURLs_BERT model exported from Colab (RUN 3) on a single URL
string and returns a **calibrated** phishing probability `p_url` ∈ [0, 1].

Design notes:
- Uses ONNX Runtime + the `tokenizers` library only — deliberately no PyTorch or
  `transformers` at serving time, so the backend stays light and starts fast.
- Temperature scaling from training is applied here (`p = softmax(logits / T)[1]`),
  because the Fusion Engine consumes this number as an honest probability.
- The model is loaded lazily and cached: the first call pays the load cost, every
  later call reuses the session.
- Artifacts live outside git (`training/artifacts/method1/`). If they are missing,
  `load_analyzer()` raises a clear error naming the expected path — callers that
  must degrade gracefully should catch `ArtifactsNotFound`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

# Repo root = .../QRGuard ; artifacts are two levels up from backend/semantic/
_DEFAULT_ARTIFACTS = Path(__file__).resolve().parents[2] / "training" / "artifacts" / "method1"

MAX_LENGTH = 128  # must match the fine-tuning configuration


class ArtifactsNotFound(FileNotFoundError):
    """Raised when the exported model files are not present on disk."""


@dataclass(frozen=True)
class Method1Result:
    p_url: float          # calibrated phishing probability -> fusion
    p_uncalibrated: float # raw softmax, kept for debugging / report comparison


class Method1Analyzer:
    """Calibrated phishing-probability scorer for URL strings."""

    def __init__(self, artifacts_dir: Path | str | None = None) -> None:
        self.dir = Path(artifacts_dir or _DEFAULT_ARTIFACTS)
        self._session = None
        self._tokenizer = None
        self._temperature = 1.0
        self._input_names: set[str] = set()
        self._load()

    # -- setup ------------------------------------------------------------
    def _load(self) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        if not self.dir.is_dir():
            raise ArtifactsNotFound(
                f"Method 1 artifacts directory not found: {self.dir}\n"
                "Download MyDrive/FYP2/method1/run3_augmented/artifacts/ into it."
            )

        # deploy_choice.json records which export passed the quantization policy
        model_name = "model_quant.onnx"
        choice = self.dir / "deploy_choice.json"
        if choice.is_file():
            model_name = json.loads(choice.read_text()).get("deploy_model", model_name)
        model_path = self.dir / model_name
        if not model_path.is_file():  # FP32 fallback export lives in a subfolder
            alt = self.dir / "onnx_fp32" / "model.onnx"
            if not alt.is_file():
                raise ArtifactsNotFound(f"ONNX model not found: {model_path}")
            model_path = alt

        tok_path = self.dir / "tokenizer.json"
        if not tok_path.is_file():
            raise ArtifactsNotFound(f"tokenizer.json not found in {self.dir}")

        so = ort.SessionOptions()
        so.intra_op_num_threads = 1  # single URL at a time; avoids thread thrash
        self._session = ort.InferenceSession(
            str(model_path), so, providers=["CPUExecutionProvider"]
        )
        self._input_names = {i.name for i in self._session.get_inputs()}

        self._tokenizer = Tokenizer.from_file(str(tok_path))
        self._tokenizer.enable_truncation(max_length=MAX_LENGTH)

        temp_file = self.dir / "temperature.json"
        if temp_file.is_file():
            self._temperature = float(json.loads(temp_file.read_text())["temperature"])

        self.model_path = model_path

    # -- inference --------------------------------------------------------
    def _logits(self, urls: Sequence[str]) -> np.ndarray:
        encodings = [self._tokenizer.encode(u) for u in urls]
        width = max(len(e.ids) for e in encodings)
        ids = np.zeros((len(encodings), width), dtype=np.int64)
        mask = np.zeros_like(ids)
        types = np.zeros_like(ids)
        for row, enc in enumerate(encodings):
            n = len(enc.ids)
            ids[row, :n] = enc.ids
            mask[row, :n] = enc.attention_mask
            types[row, :n] = enc.type_ids

        feed = {"input_ids": ids, "attention_mask": mask, "token_type_ids": types}
        feed = {k: v for k, v in feed.items() if k in self._input_names}
        return self._session.run(None, feed)[0]

    def predict(self, url: str) -> Method1Result:
        """Score one URL. Empty input is treated as maximally uncertain (0.5)."""
        if not url or not url.strip():
            return Method1Result(p_url=0.5, p_uncalibrated=0.5)
        logits = self._logits([url])[0]
        return Method1Result(
            p_url=float(_softmax(logits / self._temperature)[1]),
            p_uncalibrated=float(_softmax(logits)[1]),
        )

    def predict_batch(self, urls: Sequence[str]) -> list[Method1Result]:
        """Score several URLs in one forward pass (used by evaluation scripts)."""
        if not urls:
            return []
        logits = self._logits(list(urls))
        return [
            Method1Result(
                p_url=float(_softmax(row / self._temperature)[1]),
                p_uncalibrated=float(_softmax(row)[1]),
            )
            for row in logits
        ]

    @property
    def temperature(self) -> float:
        return self._temperature


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


@lru_cache(maxsize=1)
def load_analyzer(artifacts_dir: Optional[str] = None) -> Method1Analyzer:
    """Process-wide cached analyzer. FastAPI calls this once at startup."""
    return Method1Analyzer(artifacts_dir)


def predict_url(url: str) -> float:
    """Convenience wrapper returning just `p_url` — the fusion signal."""
    return load_analyzer().predict(url).p_url
