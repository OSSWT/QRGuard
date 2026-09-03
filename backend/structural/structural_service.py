"""Structural Analysis — calibrated three-class QR image inference.

Gallery and Live Camera use the same active ``training/artifacts/structural``
artifact. Production may set ``QRGUARD_UNIFIED_STRUCTURAL_ARTIFACTS`` to select
an explicitly validated artifact directory. Both paths return the same contract:

    clean (0) / adversarial (1) / tampered (2)
    p_structural = 1 − P(clean)     -> the Fusion Engine signal
    predicted_type                  -> shown to the user as a reason

Design notes:
- ONNX Runtime + PIL + NumPy only: no PyTorch at serving time. The preprocessing
  (resize 224×224, scale to [0,1], ImageNet normalisation) is reimplemented here
  and must stay byte-for-byte equivalent to training, or accuracy silently drops.
- The deployed export is FP32. `deploy_choice.json` records that decision. New
  Structural candidates remain versioned under ``ml_training/structural/runs``
  until their source-specific deployment gates pass.
- Temperature scaling from training is applied before deriving p_structural.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ARTIFACTS = _ROOT / "training" / "artifacts" / "structural"
_UNIFIED_CANDIDATE_VERSION_PREFIXES = (
    "structural-2026.03",
    "structural-2026.09",
    "structural-r07",
)
CLASS_NAMES = ("clean", "adversarial", "tampered")
IMG_SIZE = 224
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class ArtifactsNotFound(FileNotFoundError):
    """Raised when the exported CNN files are not present on disk."""


@dataclass(frozen=True)
class StructuralResult:
    p_structural: float  # 1 − P(clean) -> fusion signal
    predicted_type: str  # clean / adversarial / tampered -> UI
    probs: dict[str, float] = field(default_factory=dict)

    @property
    def is_manipulated(self) -> bool:
        return self.predicted_type != "clean"


class StructuralAnalyzer:
    """Calibrated 3-class manipulation detector for QR code images."""

    def __init__(self, artifacts_dir: Path | str | None = None) -> None:
        self.dir = Path(artifacts_dir or _DEFAULT_ARTIFACTS)
        self._session = None
        self._temperature = 1.0
        self._load()

    # -- setup ------------------------------------------------------------
    def _load(self) -> None:
        import onnxruntime as ort

        if not self.dir.is_dir():
            raise ArtifactsNotFound(
                f"Structural artifacts directory not found: {self.dir}\n"
                "Download MyDrive/FYP2/structural/artifacts/ into it."
            )

        self.version = ""
        self.camera_definitive_manipulation_floor: float | None = None
        metadata_path = self.dir / "model_metadata.json"
        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.version = str(metadata.get("version", ""))
            runtime_policy = metadata.get("runtime_policy", {})
            if not isinstance(runtime_policy, dict):
                raise ValueError("Structural runtime_policy metadata must be an object")
            floor = runtime_policy.get("camera_definitive_manipulation_floor")
            if floor is not None:
                floor = float(floor)
                if not 0.5 < floor < 1.0:
                    raise ValueError(
                        "camera_definitive_manipulation_floor must be between 0.5 and 1"
                    )
                self.camera_definitive_manipulation_floor = floor

        model_name = "structural_fp32.onnx"
        choice = self.dir / "deploy_choice.json"
        if choice.is_file():
            model_name = json.loads(choice.read_text()).get("deploy_model", model_name)
        model_path = self.dir / model_name
        if not model_path.is_file():
            raise ArtifactsNotFound(f"ONNX model not found: {model_path}")

        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(model_path), so, providers=["CPUExecutionProvider"]
        )
        self._input_name = self._session.get_inputs()[0].name

        temp_file = self.dir / "temperature.json"
        if temp_file.is_file():
            self._temperature = float(json.loads(temp_file.read_text())["temperature"])

        self.model_path = model_path

    # -- preprocessing ----------------------------------------------------
    @staticmethod
    def preprocess(image) -> np.ndarray:
        """PIL image -> normalised NCHW float32 tensor, matching training exactly."""
        from PIL import Image

        # torchvision.transforms.Resize uses bilinear interpolation for PIL
        # RGB inputs. Pillow's implicit default has changed across releases, so
        # spelling it out prevents a quiet train/serve preprocessing skew.
        img = image.convert("RGB").resize(
            (IMG_SIZE, IMG_SIZE), Image.Resampling.BILINEAR
        )
        arr = np.asarray(img, dtype=np.float32) / 255.0  # HWC, [0,1]
        arr = (arr - IMAGENET_MEAN) / IMAGENET_STD  # ImageNet norm
        return np.ascontiguousarray(arr.transpose(2, 0, 1)[None])  # 1CHW

    # -- inference --------------------------------------------------------
    def predict(self, image) -> StructuralResult:
        """Score one QR image (PIL Image or path)."""
        if isinstance(image, (str, Path)):
            from PIL import Image

            image = Image.open(image)

        logits = self._session.run(None, {self._input_name: self.preprocess(image)})[0][
            0
        ]
        probs = _softmax(logits / self._temperature)
        return StructuralResult(
            p_structural=float(1.0 - probs[0]),
            predicted_type=CLASS_NAMES[int(np.argmax(probs))],
            probs={name: float(probs[i]) for i, name in enumerate(CLASS_NAMES)},
        )

    @property
    def temperature(self) -> float:
        return self._temperature


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


@lru_cache(maxsize=2)
def load_analyzer(artifacts_dir: str | None = None) -> StructuralAnalyzer:
    """Process-wide cached analyzer for one artifact directory."""
    return StructuralAnalyzer(artifacts_dir)


def load_camera_analyzer() -> StructuralAnalyzer:
    """Return the same source-neutral analyzer used by Gallery."""
    return load_analyzer()


@lru_cache(maxsize=2)
def load_unified_candidate_analyzer(artifacts_dir: str) -> StructuralAnalyzer:
    """Load an explicitly selected unified candidate without changing defaults."""
    directory = Path(artifacts_dir)
    metadata_path = directory / "model_metadata.json"
    if not metadata_path.is_file():
        raise ArtifactsNotFound(f"Candidate metadata not found: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    version = str(metadata.get("version", ""))
    if not version.startswith(_UNIFIED_CANDIDATE_VERSION_PREFIXES):
        raise ValueError(
            "Unified candidate must identify a supported Structural artifact; "
            f"recorded version is {version!r}"
        )
    return load_analyzer(str(directory))


def predict_structural(image) -> StructuralResult:
    """Convenience wrapper used by the /scan route."""
    return load_analyzer().predict(image)
