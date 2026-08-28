"""Calibrated lightweight Semantic Training inference service.

The candidate model is a character n-gram linear classifier. It is intentionally
CPU-friendly and keeps deterministic URL parsing identical between training and
serving. The legacy DomURLs_BERT service remains available for rollback.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Sequence

import joblib
import numpy as np

from semantic.semantic_features import enrich_url, make_vectorizer


_DEFAULT_ARTIFACTS = (
    Path(__file__).resolve().parents[2] / "training" / "artifacts" / "semantic"
)


class ArtifactsNotFound(FileNotFoundError):
    """Raised when approved Semantic artifacts are unavailable."""


@dataclass(frozen=True)
class SemanticResult:
    p_url: float
    p_uncalibrated: float


def _sigmoid(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-clipped))


class SemanticAnalyzer:
    def __init__(self, artifacts_dir: Path | str | None = None) -> None:
        self.dir = Path(artifacts_dir or _DEFAULT_ARTIFACTS)
        self.model_path = self.dir / "semantic_model.joblib"
        if not self.model_path.is_file():
            raise ArtifactsNotFound(
                f"Semantic artifacts not found: {self.model_path}. "
                "A candidate must pass every Semantic gate before promotion."
            )
        blob = joblib.load(self.model_path)
        self._model = blob["classifier"]
        self._calibration_scale = float(blob["calibration_scale"])
        self._calibration_intercept = float(blob["calibration_intercept"])
        self.metadata = blob.get("metadata", {})
        self._vectorizer = make_vectorizer()
        metadata_path = self.dir / "model_metadata.json"
        if metadata_path.is_file():
            self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    def _decision(self, urls: Sequence[str]) -> np.ndarray:
        features = self._vectorizer.transform([enrich_url(url) for url in urls])
        return np.asarray(self._model.decision_function(features), dtype=float)

    def predict(self, url: str) -> SemanticResult:
        if not url or not url.strip():
            return SemanticResult(0.5, 0.5)
        decision = self._decision([url])
        raw = _sigmoid(decision)[0]
        calibrated = _sigmoid(
            decision * self._calibration_scale + self._calibration_intercept
        )[0]
        return SemanticResult(float(calibrated), float(raw))

    def predict_batch(self, urls: Sequence[str]) -> list[SemanticResult]:
        if not urls:
            return []
        decision = self._decision(urls)
        raw = _sigmoid(decision)
        calibrated = _sigmoid(
            decision * self._calibration_scale + self._calibration_intercept
        )
        return [
            SemanticResult(float(probability), float(uncalibrated))
            for probability, uncalibrated in zip(calibrated, raw, strict=True)
        ]


@lru_cache(maxsize=1)
def load_analyzer(artifacts_dir: Optional[str] = None) -> SemanticAnalyzer:
    return SemanticAnalyzer(artifacts_dir)


def predict_url(url: str) -> float:
    return load_analyzer().predict(url).p_url
