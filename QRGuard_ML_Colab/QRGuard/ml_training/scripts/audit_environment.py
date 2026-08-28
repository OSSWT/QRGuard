"""Write a reproducible training-environment capability report."""

from __future__ import annotations

import importlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = [
    "torch",
    "torchvision",
    "onnxruntime",
    "transformers",
    "datasets",
    "sklearn",
    "pandas",
    "PIL",
    "cv2",
    "matplotlib",
    "seaborn",
]


def main() -> None:
    modules = {}
    import_failures = []
    for name in MODULES:
        try:
            imported = importlib.import_module(name)
            modules[name] = {
                "available": True,
                "version": getattr(imported, "__version__", "not_exposed"),
            }
        except Exception as exc:  # noqa: BLE001 - report binary/import conflicts
            modules[name] = {
                "available": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            import_failures.append(name)
    report = {
        "python": sys.version,
        "platform": platform.platform(),
        "modules": modules,
        "import_failures": import_failures,
    }
    try:
        import torch

        report["torch"] = {
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count(),
        }
    except Exception as exc:
        report["torch"] = {"error": str(exc)}
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        report["nvidia_smi"] = result.stdout.strip()
    except Exception as exc:
        report["nvidia_smi"] = f"unavailable: {exc}"

    output = ROOT / "ml_training/environment_audit.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
