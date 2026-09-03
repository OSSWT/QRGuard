"""Build a focused Colab hand-off for Structural attack calibration."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
OUTPUT = DIST / "QRGuard_Attack_Calibration_Colab"
REPOSITORY = OUTPUT / "QRGuard"
NOTEBOOK_NAME = "Structural_Attack_Calibration_Colab.ipynb"
ZIP_PATH = DIST / "QRGuard_Attack_Calibration_Colab.zip"
ZIP_ENTRY_TIME = (1980, 1, 1, 0, 0, 0)
VICTIM_SHA256 = "f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec"

SOURCE_FILES = (
    "scripts/build_qr_codes_demo.py",
    "scripts/prepare_scoped_capture_references.py",
    "scripts/build_structural_coverage_development_pack.py",
    "scripts/build_structural_attack_calibration_pack.py",
)


def _markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(True)}


def _code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(True),
    }


def notebook() -> dict:
    cells = [
        _markdown(
            "# QRGuard Structural attack calibration\n\n"
            "This notebook generates development-only screen-camera attack cards. "
            "It does not train, score or promote a QRGuard model. Use a T4 GPU and "
            "run every phase in order."
        ),
        _markdown("## Phase 0 — Mount Drive and open the source bundle"),
        _code(
            r"""from google.colab import drive
drive.mount('/content/drive')

from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys, zipfile

BUNDLE = Path('/content/drive/MyDrive/QRGuard_Attack_Calibration_Colab.zip')
WORK = Path('/content/qrguard_attack_calibration')
if not BUNDLE.is_file():
    raise FileNotFoundError(f'Upload the exact bundle to {BUNDLE}')
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir(parents=True)
with zipfile.ZipFile(BUNDLE) as archive:
    archive.extractall(WORK)
REPO = WORK / 'QRGuard_Attack_Calibration_Colab' / 'QRGuard'
assert (REPO / 'scripts/build_structural_attack_calibration_pack.py').is_file()
os.chdir(REPO)
sys.path.insert(0, str(REPO))
print('Bundle SHA-256:', hashlib.sha256(BUNDLE.read_bytes()).hexdigest())
print('Source root:', REPO)
"""
        ),
        _markdown("## Phase 1 — Verify GPU and dependencies"),
        _code(
            rf"""subprocess.check_call([
    sys.executable, '-m', 'pip', 'install', '-q',
    'opencv-python-headless', 'qrcode[pil]', 'pillow', 'numpy',
])

import torch, torchvision
if not torch.cuda.is_available():
    raise RuntimeError('Enable a T4 GPU before continuing.')
print('GPU:', torch.cuda.get_device_name(0))

checkpoint = (
    Path(torch.hub.get_dir()) / 'checkpoints' / 'resnet18-f37072fd.pth'
)
checkpoint.parent.mkdir(parents=True, exist_ok=True)
if not checkpoint.is_file():
    torch.hub.download_url_to_file(
        'https://download.pytorch.org/models/resnet18-f37072fd.pth',
        checkpoint,
        hash_prefix='f37072fd',
        progress=True,
    )
victim_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
assert victim_hash == '{VICTIM_SHA256}', victim_hash
print('Victim checkpoint verified:', victim_hash)
"""
        ),
        _markdown("## Phase 2 — Generate the balanced calibration pack"),
        _code(
            r"""generation_root = WORK / 'generated'
expanded = generation_root / 'Structural_Attack_Calibration_v1'
archive_path = generation_root / 'Structural_Attack_Calibration_v1.zip'
plan_path = generation_root / 'structural_attack_calibration_plan.json'
generation_root.mkdir(parents=True, exist_ok=True)

command = [
    sys.executable, '-u', '-m',
    'scripts.build_structural_attack_calibration_pack',
    '--output', str(expanded),
    '--app-plan', str(plan_path),
    '--archive', str(archive_path),
    '--victim-checkpoint', str(checkpoint),
]
print('>', ' '.join(command), flush=True)
process = subprocess.Popen(
    command,
    cwd=REPO,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)
assert process.stdout is not None
for line in process.stdout:
    print(line, end='', flush=True)
returncode = process.wait()
if returncode:
    raise RuntimeError(f'Calibration generation failed with code {returncode}')

manifest = json.loads((expanded / 'MANIFEST.json').read_text(encoding='utf-8'))
assert manifest['case_count'] == 72
assert manifest['base_identity_count'] == 24
assert manifest['victim_checkpoint_sha256'] == victim_hash
profiles = {
    row.get('attack_profile')
    for row in manifest['cases']
    if row['label'] == 'adversarial'
}
assert profiles == {
    'screen_camera_robust_v2_function',
    'screen_camera_robust_v2_alternate',
}
assert all(
    row.get('generation_device', '').startswith('cuda')
    for row in manifest['cases']
    if row['label'] == 'adversarial'
)
print('Generation contract passed:', manifest['case_count'], 'cases')
"""
        ),
        _markdown("## Phase 3 — Save the verified hand-off to Drive"),
        _code(
            r"""drive_output = Path(
    '/content/drive/MyDrive/QRGuard_Attack_Calibration_Output'
)
drive_output.mkdir(parents=True, exist_ok=True)

outputs = {
    'Structural_Attack_Calibration_v1.zip': archive_path,
    'structural_attack_calibration_plan.json': plan_path,
}
for name, source in outputs.items():
    temporary = drive_output / f'{name}.partial'
    shutil.copy2(source, temporary)
    temporary.replace(drive_output / name)

handoff = {
    'schema_version': 1,
    'evidence_role': 'physical_attack_development_only',
    'case_count': 72,
    'base_identity_count': 24,
    'victim_checkpoint_sha256': victim_hash,
    'archive_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    'capture_plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
    'model_training_performed': False,
    'candidate_scoring_performed': False,
    'production_mutation_performed': False,
}
manifest_path = drive_output / 'OUTPUT_MANIFEST.json'
manifest_path.write_text(
    json.dumps(handoff, indent=2, sort_keys=True) + '\n', encoding='utf-8'
)
print(json.dumps(handoff, indent=2))
print('Saved to:', drive_output)
"""
        ),
    ]
    return {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"name": "QRGuard Structural Attack Calibration", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _zip_tree(source: Path, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source.parent).as_posix()
            info = zipfile.ZipInfo(relative, ZIP_ENTRY_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    temporary.replace(destination)


def build(
    output: Path = OUTPUT,
    zip_path: Path = ZIP_PATH,
) -> dict[str, str | int]:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    REPO = output / "QRGuard"
    REPO.mkdir(parents=True)
    for relative in SOURCE_FILES:
        source = ROOT / relative
        destination = REPO / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    notebook_path = output / NOTEBOOK_NAME
    notebook_path.write_text(
        json.dumps(notebook(), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        "# QRGuard attack calibration Colab hand-off\n\n"
        "Upload the sibling ZIP to the root of MyDrive. Open the notebook, "
        "select a T4 GPU, and run all phases. The output is development-only; "
        "it does not train or promote a model.\n",
        encoding="utf-8",
    )
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    _zip_tree(output, zip_path)
    return {
        "files": len([path for path in output.rglob("*") if path.is_file()]),
        "archive": str(zip_path),
        "archive_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        "notebook": str(notebook_path),
        "notebook_sha256": hashlib.sha256(notebook_path.read_bytes()).hexdigest(),
    }


def main() -> None:
    print(json.dumps(build(), indent=2))


if __name__ == "__main__":
    main()
