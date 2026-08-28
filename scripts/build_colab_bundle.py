"""Build the self-contained QRGuard Google Colab training hand-off folder."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "QRGuard_ML_Colab"
REPO = OUTPUT / "QRGuard"
ZIP_PATH = ROOT / "QRGuard_ML_Colab.zip"


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


def _notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"name": "QRGuard ML Training", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


COMMON_SETUP = r"""# Mount Drive and unpack the exact source bundle.
from google.colab import drive
drive.mount('/content/drive')

from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys, zipfile

BUNDLE_ZIP = Path('/content/drive/MyDrive/QRGuard_ML_Colab.zip')
WORK = Path('/content/qrguard_ml')
if not BUNDLE_ZIP.is_file():
    raise FileNotFoundError(
        f'Upload QRGuard_ML_Colab.zip to {BUNDLE_ZIP} before Run all.'
    )
print('Bundle SHA-256:', hashlib.sha256(BUNDLE_ZIP.read_bytes()).hexdigest().upper())
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir(parents=True)
with zipfile.ZipFile(BUNDLE_ZIP) as archive:
    archive.extractall(WORK)
REPO = WORK / 'QRGuard_ML_Colab' / 'QRGuard'
assert (REPO / 'ml_training/requirements.txt').is_file(), REPO
os.chdir(REPO)
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'backend'))
print('Training source:', REPO)
"""

INSTALL = r"""# Install QRGuard dependencies without replacing Colab's matched
# CUDA-enabled torch/torchvision wheels. Re-resolving only one side of that pair
# can make torchvision fail during import even though `import torch` still works.
def torch_runtime_smoke_test(stage):
    try:
        import torch, torchvision
        from torchvision import models, transforms
        probe = models.resnet18(weights=None)
        assert probe.fc.in_features == 512 and transforms.ToTensor is not None
    except Exception as exc:
        raise RuntimeError(
            f'Colab torch/torchvision is inconsistent {stage}: {exc}\n'
            'Choose Runtime > Disconnect and delete runtime, reconnect with a T4 GPU, '
            'then run this updated notebook from Phase 0.'
        ) from exc
    print(
        f'PyTorch runtime {stage}: torch={torch.__version__}, '
        f'torchvision={torchvision.__version__}, CUDA={torch.cuda.is_available()}'
    )

torch_runtime_smoke_test('before dependency install')
requirements = REPO / 'ml_training/requirements.txt'
colab_requirements = Path('/tmp/qrguard_colab_requirements.txt')
protected = {'torch', 'torchvision'}
lines = []
for line in requirements.read_text(encoding='utf-8').splitlines():
    package = line.split(';', 1)[0].split('[', 1)[0]
    package = package.split('=', 1)[0].split('<', 1)[0].split('>', 1)[0].strip().lower()
    if package not in protected:
        lines.append(line)
colab_requirements.write_text('\n'.join(lines) + '\n', encoding='utf-8')
subprocess.check_call([
    sys.executable, '-m', 'pip', 'install', '-q',
    '-r', str(colab_requirements),
])
torch_runtime_smoke_test('after dependency install')

def run_module(module, *arguments, check=True):
    # Colab can suppress output inherited by subprocess.run. Merge and stream
    # both channels explicitly so the real child traceback is never replaced by
    # an unhelpful outer CalledProcessError.
    command = [sys.executable, '-u', '-m', module, *map(str, arguments)]
    print('>', ' '.join(command), flush=True)
    environment = os.environ.copy()
    environment['PYTHONUNBUFFERED'] = '1'
    process = subprocess.Popen(
        command,
        cwd=REPO,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output = []
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end='', flush=True)
        output.append(line)
    returncode = process.wait()
    result = subprocess.CompletedProcess(
        command, returncode, stdout=''.join(output), stderr=None
    )
    if check and returncode:
        raise RuntimeError(
            f'{module} failed with return code {returncode}; '
            'the complete child output is printed immediately above.'
        )
    return result

run_module('ml_training.scripts.audit_environment')
"""


def structural_notebook() -> dict:
    return _notebook(
        [
            _markdown(
                "# QRGuard Structural Training — complete Google Colab run\n\n"
                "Trains the RGB image branch (`clean`, `adversarial`, `tampered`), "
                "calibrates it, evaluates grouped synthetic, public camera-derived "
                "and exact QRGuard app-camera holdouts, exports ONNX, and produces "
                "the full Structural performance bundle. Use **Runtime → Change "
                "runtime type → T4 GPU**, then **Run all**."
            ),
            _markdown("## Phase 0 — Reproducible workspace and Drive mount"),
            _code(COMMON_SETUP),
            _markdown("## Phase 1 — Environment, GPU and dependency audit"),
            _code(
                INSTALL
                + "\nimport torch\nprint('PyTorch:', torch.__version__)\nprint('CUDA:', torch.cuda.is_available())\nif not torch.cuda.is_available():\n    raise RuntimeError('Enable a T4 GPU for Structural Training.')\nprint('GPU:', torch.cuda.get_device_name(0))\n"
            ),
            _markdown(
                "## Phase 2 — Verify and prepare public Structural sources\n\n"
                "Place the two official archives in `MyDrive/QRGuard_ML_Data/structural/` "
                "using the exact filenames below. SHA-256 and byte-size checks run before extraction."
            ),
            _code(
                r"""DATA_DRIVE = Path('/content/drive/MyDrive/QRGuard_ML_Data/structural')
downloads = REPO / 'ml_training/datasets/structural/downloads'
archives = {
    DATA_DRIVE / 'QR-DN1.0.zip': downloads / 'qrdn/QR-DN1.0.zip',
    DATA_DRIVE / 'qr_codes_in_surfaces.zip': downloads / 'qr_surfaces/qr_codes_in_surfaces.zip',
}
for source, destination in archives.items():
    if not source.is_file():
        raise FileNotFoundError(f'Missing official archive: {source}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file() or destination.stat().st_size != source.stat().st_size:
        shutil.copy2(source, destination)
run_module('ml_training.scripts.verify_datasets')

raw_qrdn = REPO / 'ml_training/datasets/structural/raw/qrdn'
raw_surfaces = REPO / 'ml_training/datasets/structural/raw/qr_surfaces'
for archive, destination in (
    (archives[DATA_DRIVE / 'QR-DN1.0.zip'], raw_qrdn),
    (archives[DATA_DRIVE / 'qr_codes_in_surfaces.zip'], raw_surfaces),
):
    if not destination.exists():
        destination.mkdir(parents=True)
        with zipfile.ZipFile(archive) as package:
            package.extractall(destination)
run_module('ml_training.structural.src.prepare_qrdn')
run_module('ml_training.structural.src.prepare_qr_surfaces')
"""
            ),
            _markdown(
                "## Phase 3 — Audit exact QRGuard app-camera sessions\n\n"
                "Optional files go in `MyDrive/QRGuard_ML_Data/structural/runtime_captures/`. "
                "They are required for deployment approval: at least 100 sessions per class "
                "and 20 independent test payload groups per class. Training may still produce "
                "a research candidate when this gate is incomplete."
            ),
            _code(
                r"""drive_captures = DATA_DRIVE / 'runtime_captures'
local_captures = REPO / 'data/runtime_captures'
if drive_captures.exists():
    shutil.copytree(drive_captures, local_captures, dirs_exist_ok=True)
capture_audit = run_module(
    'ml_training.structural.src.prepare_runtime_captures',
    local_captures,
    '--strict',
    check=False,
)
print('Exact camera gate:', 'READY' if capture_audit.returncode == 0 else 'NOT READY — candidate only')
"""
            ),
            _markdown(
                "## Phase 4 — Generate grouped RGB clean/adversarial/tampered data\n\n"
                "This creates coloured and black/white QR identities, physical tampering, "
                "FGSM/PGD digital attacks, camera augmentation, and exact app crops without "
                "allowing a payload/physical identity to cross splits."
            ),
            _code(
                r"""recipe_source = (
    REPO / 'ml_training/structural/src/structural_recipes.py'
).read_text(encoding='utf-8')
cuda_device_fix = 'model = Normalized(victim).to(device).eval()'
if cuda_device_fix not in recipe_source:
    raise RuntimeError(
        'Stale QRGuard_ML_Colab.zip detected: the Structural CUDA buffer fix is '
        'missing. Delete the old exact-name ZIP in MyDrive, upload the latest '
        'QRGuard_ML_Colab.zip, then rerun from Phase 0.'
    )
run_module(
    'ml_training.structural.src.train_local',
    '--prepare-only',
    '--rebuild-data',
)
"""
            ),
            _markdown("## Phase 5 — Dataset composition, leakage and RGB audit"),
            _code(
                r"""import pandas as pd
manifest = pd.read_csv(REPO / 'ml_training/datasets/structural/processed/structural-2026.02/manifest.csv')
display(pd.crosstab(manifest.split, [manifest.label, manifest.source]))
groups = {name: set(part.group_id) for name, part in manifest.groupby('split')}
overlaps = {
    f'{left}/{right}': len(groups[left] & groups[right])
    for index, left in enumerate(groups)
    for right in list(groups)[index + 1:]
}
assert not any(overlaps.values()), overlaps
print('Rows:', len(manifest), 'Groups:', manifest.group_id.nunique())
print('Exact app-crop rows:', int(manifest.is_exact_app_crop.astype(str).str.lower().eq('true').sum()))
print('Colour contract: RGB 224x224, ImageNet mean/std; see ml_training/COLOR_PIPELINE.md')
"""
            ),
            _markdown(
                "## Phase 6 — Train, calibrate, evaluate and export\n\n"
                "Head training and layer-4 fine-tuning use the T4. A non-zero return code "
                "means a deployment gate failed; the performance report is still retained."
            ),
            _code(
                r"""training = run_module('ml_training.structural.src.train_local', check=False)
print('Training return code:', training.returncode)
"""
            ),
            _markdown("## Phase 7 — Display every Structural performance output"),
            _code(
                r"""from IPython.display import Image as DisplayImage, Markdown, display
import pandas as pd

PERF = REPO / 'ml_training/structural/performance/structural-2026.02'
metrics_path = PERF / 'metrics.json'
if not metrics_path.is_file():
    raise RuntimeError('Performance output is missing. Complete Phase 6 first.')
metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
grouped = metrics['synthetic_grouped_test']
external = metrics['qrdn_external_clean_holdout']
onnx = metrics['onnx']

def metric_row(name, value, target, passed, unit='score'):
    if value is None:
        displayed_value = 'not evaluated'
    elif unit == 'ms':
        displayed_value = f'{value:.2f} ms'
    elif unit == 'count':
        displayed_value = f'{int(value):,}'
    else:
        displayed_value = f'{value:.4f}'
    return {
        'Core metric': name,
        'Result': displayed_value,
        'Target': target,
        'Status': 'INFO' if passed is None else ('PASS' if passed else 'FAIL'),
    }

core_metrics = pd.DataFrame([
    metric_row('Grouped test accuracy', grouped['accuracy'], 'reported', None),
    metric_row('Grouped test macro-F1', grouped['macro_f1'], '>= 0.85', grouped['macro_f1'] >= 0.85),
    metric_row(
        'Adversarial recall',
        grouped['per_class']['adversarial']['recall'],
        '>= 0.75',
        grouped['per_class']['adversarial']['recall'] >= 0.75,
    ),
    metric_row(
        'Tampered recall',
        grouped['per_class']['tampered']['recall'],
        '>= 0.90',
        grouped['per_class']['tampered']['recall'] >= 0.90,
    ),
    metric_row('ECE', grouped['ece'], '<= 0.05', grouped['ece'] <= 0.05),
    metric_row(
        'QR-DN clean false-positive rate',
        external['false_positive_rate_at_0_5'],
        '<= 0.05',
        external['false_positive_rate_at_0_5'] <= 0.05,
    ),
    metric_row(
        'ONNX P95 latency',
        onnx['latency_p95_ms'],
        '<= 100 ms',
        onnx['latency_p95_ms'] <= 100,
        unit='ms',
    ),
    metric_row(
        'Exact app-camera test frames',
        metrics['exact_app_runtime_holdout']['n'],
        'required for deployment',
        None,
        unit='count',
    ),
])
display(Markdown('## Core performance metrics'))
display(core_metrics)

gate_summary = pd.DataFrame([
    {
        'Gate': 'Research gates',
        'Status': 'PASS' if metrics['research_gates_passed'] else 'FAIL',
        'Failures': '; '.join(metrics['research_gate_failures']) or 'none',
    },
    {
        'Gate': 'Deployment gates',
        'Status': 'PASS' if metrics['deployment_gates_passed'] else 'CANDIDATE ONLY',
        'Failures': '; '.join(metrics['deployment_gate_failures']) or 'none',
    },
])
display(Markdown('## Gate status'))
display(gate_summary)
display(Markdown((PERF / 'STRUCTURAL_PERFORMANCE.md').read_text(encoding='utf-8')))

display(Markdown('## Performance charts'))
for name in ('training_curves.png', 'confusion_matrix.png', 'roc_pr_curves.png',
             'calibration_curve.png', 'qrdn_clean_distribution.png'):
    chart = PERF / name
    display(Markdown(f'### {name}'))
    if chart.is_file():
        display(DisplayImage(filename=str(chart)))
    else:
        print('Missing chart:', chart)

display(Markdown('## Detailed performance tables'))
for name in ('metrics.csv', 'dataset_composition.csv', 'per_source_results.csv',
             'per_device_results.csv', 'gallery_camera_consistency.csv',
             'misclassified_samples.csv', 'training_history.csv'):
    table = PERF / name
    display(Markdown(f'### {name}'))
    if table.is_file():
        display(pd.read_csv(table).head(30))
    else:
        print('Missing table:', table)
"""
            ),
            _markdown("## Phase 8 — Validate completeness and save to Drive"),
            _code(
                r"""validation = run_module(
    'ml_training.scripts.validate_performance_bundle',
    '--branch', 'structural',
    check=False,
)
if validation.returncode:
    raise RuntimeError('Structural report bundle is incomplete; inspect the phase above.')
destination = Path('/content/drive/MyDrive/QRGuard_ML_Results/structural-2026.02')
destination.mkdir(parents=True, exist_ok=True)
shutil.copytree(PERF, destination / 'performance', dirs_exist_ok=True)
shutil.copytree(
    REPO / 'ml_training/structural/runs/structural-2026.02/artifacts',
    destination / 'artifacts',
    dirs_exist_ok=True,
)
shutil.copy2(REPO / 'ml_training/PERFORMANCE_VALIDATION.json', destination)
archive = shutil.make_archive(str(destination), 'zip', root_dir=destination)
print('Saved:', destination)
print('Archive:', archive)
"""
            ),
        ]
    )


def semantic_notebook() -> dict:
    return _notebook(
        [
            _markdown(
                "# QRGuard Semantic Training — complete Google Colab run\n\n"
                "Acquires and freezes URL corpora, removes conflicts, creates a registrable-"
                "domain-disjoint holdout, trains the serving-compatible calibrated character "
                "3–5 gram model, runs behavioural gates, and exports every Semantic performance "
                "artifact. A GPU is not required for this sparse linear model."
            ),
            _markdown("## Phase 0 — Reproducible workspace and Drive mount"),
            _code(COMMON_SETUP),
            _markdown("## Phase 1 — Environment and dependency audit"),
            _code(INSTALL),
            _markdown(
                "## Phase 2 — Acquire, standardise and freeze Semantic sources\n\n"
                "PhiUSIIL is fetched from UCI, Malicious URLs through KaggleHub, and a dated "
                "Tranco list through the Tranco client. Prepared data is cached in Drive."
            ),
            _code(
                r"""SEMANTIC_DRIVE = Path('/content/drive/MyDrive/QRGuard_ML_Data/semantic')
LOCAL_DATA = REPO / 'data/method1'
if (SEMANTIC_DRIVE / 'provenance.json').is_file():
    shutil.copytree(SEMANTIC_DRIVE, LOCAL_DATA, dirs_exist_ok=True)
    print('Restored prepared Semantic data from Drive')
else:
    run_module('ml_training.semantic.src.prepare_colab_data')
    SEMANTIC_DRIVE.mkdir(parents=True, exist_ok=True)
    shutil.copytree(LOCAL_DATA, SEMANTIC_DRIVE, dirs_exist_ok=True)
provenance = json.loads((LOCAL_DATA / 'provenance.json').read_text())
display(provenance)
"""
            ),
            _markdown(
                "## Phase 3 — Provenance, labels and domain-disjoint holdout audit"
            ),
            _code(
                r"""import pandas as pd
heldout = pd.read_parquet(LOCAL_DATA / 'heldout_test.parquet')
print('Held-out rows:', len(heldout))
print('Held-out registrable domains:', heldout.domain.nunique())
display(heldout.groupby(['source', 'label']).size().rename('rows').reset_index())
assert heldout.domain.notna().all()
assert set(heldout.label.unique()).issubset({0, 1})
"""
            ),
            _markdown(
                "## Phase 4 — Clean conflicts, grouped split, train and calibrate\n\n"
                "The runtime-compatible model uses the same URL enrichment and hashing "
                "contract as the backend. Validation fits calibration; test data is not used "
                "to train parameters."
            ),
            _code(
                r"""training = run_module('ml_training.semantic.src.train_local', check=False)
print('Training return code:', training.returncode)
"""
            ),
            _markdown("## Phase 5 — Display every Semantic performance output"),
            _code(
                r"""from IPython.display import Image as DisplayImage, Markdown, display
PERF = REPO / 'ml_training/semantic/performance/semantic-2026.02'
metrics = json.loads((PERF / 'metrics.json').read_text())
display(Markdown((PERF / 'SEMANTIC_PERFORMANCE.md').read_text()))
display(metrics)
for name in ('training_curves.png', 'confusion_matrix.png', 'roc_pr_curves.png',
             'calibration_curve.png'):
    display(Markdown(f'### {name}'))
    display(DisplayImage(filename=str(PERF / name)))
for name in ('metrics.csv', 'dataset_composition.csv', 'threshold_analysis.csv',
             'per_source_results.csv', 'hard_benign_results.csv',
             'behavioural_acceptance.csv'):
    print('\n', name)
    display(pd.read_csv(PERF / name).head(50))
"""
            ),
            _markdown(
                "## Phase 6 — Validate serving parity, gates and report completeness"
            ),
            _code(
                r"""validation = run_module(
    'ml_training.scripts.validate_performance_bundle',
    '--branch', 'semantic',
    check=False,
)
if validation.returncode:
    raise RuntimeError('Semantic report bundle is incomplete; inspect the phase above.')
summary = json.loads((REPO / 'ml_training/PERFORMANCE_VALIDATION.json').read_text())
display(summary)
"""
            ),
            _markdown("## Phase 7 — Save model and all performance outputs to Drive"),
            _code(
                r"""destination = Path('/content/drive/MyDrive/QRGuard_ML_Results/semantic-2026.02')
destination.mkdir(parents=True, exist_ok=True)
shutil.copytree(PERF, destination / 'performance', dirs_exist_ok=True)
shutil.copytree(
    REPO / 'ml_training/semantic/runs/semantic-2026.02/artifacts',
    destination / 'artifacts',
    dirs_exist_ok=True,
)
shutil.copy2(REPO / 'ml_training/PERFORMANCE_VALIDATION.json', destination)
archive = shutil.make_archive(str(destination), 'zip', root_dir=destination)
print('Saved:', destination)
print('Archive:', archive)
"""
            ),
        ]
    )


README = """# QRGuard complete Google Colab ML package

This folder is the self-contained hand-off for both trained QRGuard branches.
It contains the canonical training/evaluation/export source, dataset contracts,
licences and references, the current reference performance, and two Run-all
Google Colab notebooks.

The existing measured baseline/candidate numbers are summarised in
`REFERENCE_RESULTS.md` and their original figures/JSON/CSV files are under
`reference_performance/`. A fresh notebook run writes a new complete bundle to Drive.

## Start here

1. Upload `QRGuard_ML_Colab.zip` to `MyDrive/QRGuard_ML_Colab.zip`.
2. For Structural, download the official QR-DN1.0 v2 and QR Codes in Surfaces
   v1 archives and place them at:
   - `MyDrive/QRGuard_ML_Data/structural/QR-DN1.0.zip`
   - `MyDrive/QRGuard_ML_Data/structural/qr_codes_in_surfaces.zip`
3. If available, copy labelled exact app captures to
   `MyDrive/QRGuard_ML_Data/structural/runtime_captures/`.
4. Open `01_Structural_Training_Colab.ipynb`, select a T4 GPU, and Run all.
5. Open `02_Semantic_Training_Colab.ipynb` and Run all. Kaggle may ask you to
   authenticate/accept the Malicious URLs dataset terms on first acquisition.
6. Complete outputs are copied to `MyDrive/QRGuard_ML_Results/`.

Raw third-party datasets are not redistributed in this source package because
they are large and governed by their source terms. Official URLs, DOI/licence,
expected byte sizes, SHA-256 hashes and acquisition code are included. That is
the reproducibility material; the notebooks fetch or verify the actual data.

## Honest camera gate

A QR can decode successfully while the image-integrity model cannot safely use
the camera frames. Decoding and Structural classification are different tasks.
Synthetic camera augmentation cannot prove performance on QRGuard's exact crop
pipeline, so Structural deployment remains `CANDIDATE ONLY` until the labelled
app-camera gate passes. The notebook still produces all tables and figures and
states exactly which gate is missing.

## Colour contract

Structural Training uses RGB, 224×224, `[0,1]` scaling and ImageNet RGB
normalisation. It does not use CMYK or Lab. See
`QRGuard/ml_training/COLOR_PIPELINE.md` for the exact coloured-QR generation,
camera colour-correction and serving parity contract.
"""


REFERENCE_RESULTS = """# Existing measured Structural and Semantic performance

These are the checked-in `2026.02` reference results, not invented notebook
output. Run the two Colab notebooks to reproduce fresh artifacts in your own
Google Drive.

| Branch / metric | Existing measured result |
|---|---:|
| Structural grouped test accuracy | 0.8907 |
| Structural grouped macro-F1 | 0.8892 |
| Structural adversarial recall | 0.9611 |
| Structural tampered recall | 0.9222 |
| Structural ECE | 0.0126 |
| Structural QR-DN clean false-positive rate | 0.0000 |
| Structural ONNX P95 latency (reference machine) | 44.63 ms |
| Semantic test accuracy | 0.8983 |
| Semantic precision | 0.9089 |
| Semantic recall | 0.8853 |
| Semantic F1 | 0.8969 |
| Semantic ROC-AUC | 0.9566 |
| Semantic PR-AUC | 0.9617 |
| Semantic ECE | 0.0202 |
| Semantic behavioural benign FPR | 0.0400 |
| Semantic behavioural phishing recall | 1.0000 |

Semantic `semantic-2026.02` passed its recorded gates. Structural
`structural-2026.02` passed its research gates but is **candidate only**, because
the recorded exact QRGuard app-camera audit has zero labelled sessions. The
Colab pipeline keeps that limitation explicit and cannot approve deployment
until the real-camera sample/session gates and class-specific performance gates
pass.
"""


DATA_REQUIREMENTS = """# Data requirements and Drive layout

```text
MyDrive/
  QRGuard_ML_Colab.zip
  QRGuard_ML_Data/
    structural/
      QR-DN1.0.zip
      qr_codes_in_surfaces.zip
      runtime_captures/          # optional for training, mandatory to approve deployment
    semantic/                    # generated cache; no manual copy required normally
  QRGuard_ML_Results/            # generated by the notebooks
```

Structural archive hashes are verified against
`QRGuard/ml_training/datasets/download_verification.json`. Runtime capture
folders must follow the schema documented by
`prepare_runtime_captures.py`: 3–5 distinct exact PNG crops plus anonymised
metadata per labelled session. Raw QR payloads are never required or stored.
"""


def _copy_file(relative: str) -> None:
    source = ROOT / relative
    destination = REPO / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_tree(relative: str, *, patterns: tuple[str, ...] | None = None) -> None:
    source = ROOT / relative
    destination = REPO / relative
    if patterns is None:
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".ipynb_checkpoints"),
        )
        return
    destination.mkdir(parents=True, exist_ok=True)
    for pattern in patterns:
        for path in source.rglob(pattern):
            if path.is_file():
                target = destination / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)


def build() -> None:
    resolved_root = ROOT.resolve()
    resolved_output = OUTPUT.resolve()
    if (
        resolved_output.parent != resolved_root
        or resolved_output.name != "QRGuard_ML_Colab"
    ):
        raise RuntimeError(f"refusing to clean unexpected package path: {resolved_output}")
    if OUTPUT.exists():
        # OUTPUT is fully generated. Cleaning it prevents stale files (including
        # an accidentally nested prior package) from accumulating across builds.
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPO.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "README.md").write_text(README, encoding="utf-8")
    (OUTPUT / "DATA_REQUIREMENTS.md").write_text(DATA_REQUIREMENTS, encoding="utf-8")
    (OUTPUT / "REFERENCE_RESULTS.md").write_text(
        REFERENCE_RESULTS, encoding="utf-8"
    )
    structural_json = json.dumps(structural_notebook(), indent=1)
    semantic_json = json.dumps(semantic_notebook(), indent=1)
    (OUTPUT / "01_Structural_Training_Colab.ipynb").write_text(
        structural_json, encoding="utf-8"
    )
    (OUTPUT / "02_Semantic_Training_Colab.ipynb").write_text(
        semantic_json, encoding="utf-8"
    )
    (ROOT / "ml_training/structural/notebooks/structural_training_v2.ipynb").write_text(
        structural_json, encoding="utf-8"
    )
    (ROOT / "ml_training/semantic/notebooks/semantic_training_v2.ipynb").write_text(
        semantic_json, encoding="utf-8"
    )

    for relative in (
        "ml_training/__init__.py",
        "ml_training/README.md",
        "ml_training/COLOR_PIPELINE.md",
        "ml_training/EXECUTION_PLAN.md",
        "ml_training/RESULTS_INDEX.md",
        "ml_training/requirements.txt",
    ):
        _copy_file(relative)
    for relative in (
        "ml_training/configs",
        "ml_training/references",
        "ml_training/scripts",
        "ml_training/structural/src",
        "ml_training/semantic/src",
    ):
        _copy_tree(relative)
    for relative in (
        "ml_training/datasets/README.md",
        "ml_training/datasets/download_verification.json",
        "ml_training/datasets/manifests/structural.template.csv",
        "ml_training/datasets/manifests/semantic.template.csv",
        "ml_training/structural/README.md",
        "ml_training/semantic/README.md",
        "backend/semantic/__init__.py",
        "backend/semantic/semantic_features.py",
        "backend/semantic/semantic_service.py",
        "data/runtime_captures/audit.json",
    ):
        _copy_file(relative)
    _copy_tree(
        "ml_training/structural/performance/structural-2026.02",
    )
    _copy_tree(
        "ml_training/semantic/performance/semantic-2026.02",
    )
    # Preserve existing results as read-only context; fresh notebook outputs use
    # the canonical performance directories above and replace them phase by phase.
    reference = OUTPUT / "reference_performance"
    shutil.copytree(
        ROOT / "ml_training/structural/performance/structural-2026.02",
        reference / "structural-2026.02",
        dirs_exist_ok=True,
    )
    shutil.copytree(
        ROOT / "ml_training/semantic/performance/semantic-2026.02",
        reference / "semantic-2026.02",
        dirs_exist_ok=True,
    )

    files = sorted(
        path
        for path in OUTPUT.rglob("*")
        if path.is_file() and path.name != "PACKAGE_MANIFEST.json"
    )
    manifest = {
        "package": "QRGuard_ML_Colab",
        "files": [
            {
                "path": path.relative_to(OUTPUT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in files
        ],
    }
    (OUTPUT / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in OUTPUT.rglob("*") if p.is_file()):
            archive.write(path, Path(OUTPUT.name) / path.relative_to(OUTPUT))
    print(f"Built {OUTPUT}")
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
