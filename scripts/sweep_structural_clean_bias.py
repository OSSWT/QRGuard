"""Screen a clean-logit calibration bias on locked Structural evidence.

The sweep is diagnostic: it never changes a runtime artifact.  It evaluates the
same checkpoint on the grouped synthetic test, exact app-camera holdout, and a
development capture archive so a class-boundary correction cannot hide lost
attack recall or SEM-11/exposure regressions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.metrics import f1_score
from torch import nn
from torchvision import models, transforms

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

try:
    from scripts.analyze_live_camera_diagnostic import ValidatedFrame, validate_archive
except ModuleNotFoundError:
    from analyze_live_camera_diagnostic import ValidatedFrame, validate_archive

CLASS_NAMES = ("clean", "adversarial", "tampered")
IMAGE_SIZE = 224
PREPROCESS = transforms.Compose(
    [
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225),
        ),
    ]
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model(checkpoint: Path) -> nn.Module:
    model = models.resnet18(weights=None)
    model.fc = nn.Sequential(nn.Dropout(0.20), nn.Linear(model.fc.in_features, 3))
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    model.eval()
    return model


def _batched_logits(model: nn.Module, images: Iterable[Image.Image], batch_size: int) -> np.ndarray:
    tensors: list[torch.Tensor] = []
    batches: list[np.ndarray] = []
    with torch.inference_mode():
        for image in images:
            tensors.append(PREPROCESS(image.convert("RGB")))
            if len(tensors) == batch_size:
                batches.append(model(torch.stack(tensors)).numpy())
                tensors.clear()
        if tensors:
            batches.append(model(torch.stack(tensors)).numpy())
    return np.concatenate(batches, axis=0)


def _manifest_logits(
    model: nn.Module, frame: pd.DataFrame, batch_size: int
) -> np.ndarray:
    def images() -> Iterable[Image.Image]:
        for relative in frame.path:
            with Image.open(ROOT / str(relative)) as image:
                yield image.copy()

    return _batched_logits(model, images(), batch_size)


def _archive_logits(
    model: nn.Module, frames: list[ValidatedFrame], batch_size: int
) -> np.ndarray:
    def images() -> Iterable[Image.Image]:
        for frame in frames:
            with Image.open(io.BytesIO(frame.crop_png)) as image:
                yield image.copy()

    return _batched_logits(model, images(), batch_size)


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponent = np.exp(shifted)
    return exponent / exponent.sum(axis=1, keepdims=True)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _linear_quantile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _score(
    *,
    bias: float,
    temperature: float,
    test_frame: pd.DataFrame,
    test_logits: np.ndarray,
    runtime_frame: pd.DataFrame,
    runtime_logits: np.ndarray,
    capture_frames: list[ValidatedFrame],
    capture_logits: np.ndarray,
) -> dict[str, float | int | None]:
    correction = np.array([bias, 0.0, 0.0], dtype=np.float32)

    test_probs = _softmax((test_logits + correction) / temperature)
    test_predictions = test_probs.argmax(axis=1)
    test_truth = test_frame.class_id.to_numpy(dtype=np.int64)

    runtime_probs = _softmax((runtime_logits + correction) / temperature)
    runtime_predictions = runtime_probs.argmax(axis=1)
    runtime_truth = runtime_frame.class_id.to_numpy(dtype=np.int64)
    runtime_camera = runtime_frame.source.eq("qrguard_runtime_v3_camera").to_numpy()
    runtime_clean = runtime_camera & (runtime_truth == 0)
    runtime_attack = runtime_camera & (runtime_truth != 0)

    capture_probs = _softmax((capture_logits + correction) / temperature)
    capture_predictions = capture_probs.argmax(axis=1)
    capture_structural = 1.0 - capture_probs[:, 0]
    capture_clean = np.array([frame.ground_truth == "clean" for frame in capture_frames])
    capture_attack = ~capture_clean
    capture_sem11 = np.array(
        [frame.case_id == "SEM-11-PLAIN-TEXT" for frame in capture_frames]
    )

    medians: dict[tuple[str, str], list[float]] = defaultdict(list)
    for frame, probability in zip(capture_frames, capture_structural, strict=True):
        if frame.ground_truth == "clean":
            medians[(frame.case_id, frame.distance)].append(float(probability))
    spans_by_case: dict[str, list[float]] = defaultdict(list)
    for (case_id, _distance), values in medians.items():
        spans_by_case[case_id].append(float(np.median(values)))
    spans = [max(values) - min(values) for values in spans_by_case.values()]

    sem11_sessions: dict[str, list[int]] = defaultdict(list)
    for frame, prediction in zip(capture_frames, capture_predictions, strict=True):
        if frame.case_id == "SEM-11-PLAIN-TEXT":
            sem11_sessions[frame.session_id].append(int(prediction != 0))

    return {
        "clean_logit_bias": bias,
        "temperature": temperature,
        "synthetic_macro_f1": float(
            f1_score(test_truth, test_predictions, average="macro")
        ),
        "synthetic_clean_recall": _rate(
            int(((test_predictions == 0) & (test_truth == 0)).sum()),
            int((test_truth == 0).sum()),
        ),
        "synthetic_adversarial_recall": _rate(
            int(((test_predictions == 1) & (test_truth == 1)).sum()),
            int((test_truth == 1).sum()),
        ),
        "synthetic_tampered_recall": _rate(
            int(((test_predictions == 2) & (test_truth == 2)).sum()),
            int((test_truth == 2).sum()),
        ),
        "runtime_camera_clean_fpr": _rate(
            int((runtime_predictions[runtime_clean] != 0).sum()),
            int(runtime_clean.sum()),
        ),
        "runtime_camera_attack_recall": _rate(
            int((runtime_predictions[runtime_attack] != 0).sum()),
            int(runtime_attack.sum()),
        ),
        "development_clean_fpr": _rate(
            int((capture_predictions[capture_clean] != 0).sum()),
            int(capture_clean.sum()),
        ),
        "development_attack_recall": _rate(
            int((capture_predictions[capture_attack] != 0).sum()),
            int(capture_attack.sum()),
        ),
        "development_clean_fpr_at_camera_floor": _rate(
            int(
                (
                    (capture_predictions[capture_clean] != 0)
                    & (capture_structural[capture_clean] >= 0.7)
                ).sum()
            ),
            int(capture_clean.sum()),
        ),
        "development_clean_exposure_span_p95": _linear_quantile(spans, 0.95),
        "sem11_false_positive_frames": int(
            (capture_predictions[capture_sem11] != 0).sum()
        ),
        "sem11_false_positive_sessions": sum(
            sum(values) > len(values) / 2 for values in sem11_sessions.values()
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--temperature", type=float, required=True)
    parser.add_argument("--bias-start", type=float, default=0.0)
    parser.add_argument("--bias-stop", type=float, default=4.0)
    parser.add_argument("--bias-step", type=float, default=0.1)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    torch.set_num_threads(min(6, max(1, torch.get_num_threads())))
    checkpoint = args.checkpoint.resolve(strict=True)
    manifest = args.manifest.resolve(strict=True)
    archive = args.archive.resolve(strict=True)
    plan = args.plan.resolve(strict=True)
    model = _model(checkpoint)

    frame = pd.read_csv(manifest)
    test_frame = frame[frame.split == "test"].reset_index(drop=True)
    runtime_frame = frame[frame.split == "runtime_holdout_test"].reset_index(drop=True)
    capture_frames = validate_archive(archive, plan)
    print(
        f"Scoring {len(test_frame)} grouped-test, {len(runtime_frame)} runtime, "
        f"and {len(capture_frames)} development frames"
    )
    test_logits = _manifest_logits(model, test_frame, args.batch_size)
    runtime_logits = _manifest_logits(model, runtime_frame, args.batch_size)
    capture_logits = _archive_logits(model, capture_frames, args.batch_size)

    count = round((args.bias_stop - args.bias_start) / args.bias_step)
    biases = [args.bias_start + index * args.bias_step for index in range(count + 1)]
    rows = [
        _score(
            bias=bias,
            temperature=args.temperature,
            test_frame=test_frame,
            test_logits=test_logits,
            runtime_frame=runtime_frame,
            runtime_logits=runtime_logits,
            capture_frames=capture_frames,
            capture_logits=capture_logits,
        )
        for bias in biases
    ]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "CLEAN_LOGIT_BIAS_SWEEP.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "schema_version": 1,
        "checkpoint_sha256": _sha256(checkpoint),
        "manifest_sha256": _sha256(manifest),
        "archive_sha256": _sha256(archive),
        "temperature": args.temperature,
        "rows": rows,
    }
    (output / "CLEAN_LOGIT_BIAS_SWEEP.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    feasible = [
        row
        for row in rows
        if row["synthetic_macro_f1"] >= 0.85
        and row["runtime_camera_clean_fpr"] <= 0.05
        and row["development_clean_fpr"] <= 0.05
        and row["development_attack_recall"] >= 0.80
        and row["sem11_false_positive_frames"] == 0
    ]
    print(json.dumps({"feasible_count": len(feasible), "feasible": feasible}, indent=2))
    print(f"wrote {len(rows)} bias candidates to {output}")


if __name__ == "__main__":
    main()
