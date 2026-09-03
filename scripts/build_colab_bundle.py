"""Build the self-contained QRGuard Google Colab training hand-off folder."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
OUTPUT = DIST / "QRGuard_ML_Colab"
REPO = OUTPUT / "QRGuard"
ZIP_PATH = DIST / "QRGuard_ML_Colab.zip"
DETERMINISTIC_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


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


def structural_v3_notebook() -> dict:
    install_when_needed = (
        "if RUN_MODE == 'report_only':\n"
        "    print('report_only: dependency installation and GPU checks skipped')\n"
        "else:\n"
        + "".join(f"    {line}" for line in INSTALL.splitlines(keepends=True))
        + "    import torch\n"
        + "    if not torch.cuda.is_available():\n"
        + "        raise RuntimeError('Enable a T4 GPU for training/evaluation.')\n"
        + "    print('GPU:', torch.cuda.get_device_name(0))\n"
    )
    return _notebook(
        [
            _markdown(
                "# QRGuard Structural r07 corrective candidate\n\n"
                "`structural-r07-corrective-v1` starts from the locked r07 best checkpoint "
                "and trains one ResNet-18 artifact for Gallery and Camera. It retains the "
                "exposure hard negatives and expands to 2,560 grouped clean counterfactuals "
                "across Versions 3-20, all eight masks, four error-correction levels, "
                "and controlled screen moire. Its consistency graph is one connected cycle "
                "across every mask and condition. It retains 80 consumed clean M8 crops and "
                "adds only the 10 attack crops whose screen/camera survival was independently "
                "verified; all are permanently non-promoting development evidence. Weighted "
                "calibration, exposure consistency and feasibility-first selection remain enabled. "
                "Capture conditions remain "
                "nuisance/quality slices, not malicious labels. The notebook never "
                "promotes or deploys the candidate automatically."
            ),
            _markdown("## Phase 0 - Choose exactly one run mode"),
            _code(
                r"""RUN_MODE = 'fresh'  # fresh | resume | evaluate_only | report_only
RUN_ID = 'r07-corrective-v1'
VERSION = 'structural-r07-corrective-v1'
DATASET_VERSION = 'structural-r07-corrective-v1'  # locked 14,240-row evidence
VALID_MODES = {'fresh', 'resume', 'evaluate_only', 'report_only'}
if RUN_MODE not in VALID_MODES:
    raise ValueError(f'RUN_MODE must be one of {sorted(VALID_MODES)}')
print('Mode:', RUN_MODE, '| Version:', VERSION, '| Run ID:', RUN_ID)
"""
            ),
            _markdown("## Phase 1 - Reproducible source bundle and Drive"),
            _code(COMMON_SETUP),
            _code(
                r"""DRIVE_ML = Path('/content/drive/MyDrive/QRGuard_ML')
DRIVE_RUN = DRIVE_ML / 'runs' / VERSION / RUN_ID
CHECKPOINT_DIR = DRIVE_RUN / 'checkpoints'
OUTPUT_DRIVE = DRIVE_RUN / 'outputs'
CACHE_DRIVE = DRIVE_ML / 'cache' / VERSION
BASE_CACHE_DRIVE = DRIVE_ML / 'cache' / 'structural-2026.09-r07'
DATA_DRIVE = Path('/content/drive/MyDrive/QRGuard_ML_Data/structural')
PERF = REPO / 'ml_training/structural/performance' / VERSION
ARTIFACTS = REPO / 'ml_training/structural/runs' / VERSION / 'artifacts'
PROCESSED_ROOT = REPO / 'ml_training/datasets/structural/processed'
os.environ['QRGUARD_STRUCTURAL_VERSION'] = VERSION
os.environ['QRGUARD_STRUCTURAL_DATASET_VERSION'] = DATASET_VERSION
for directory in (DRIVE_RUN, CHECKPOINT_DIR, OUTPUT_DRIVE, CACHE_DRIVE):
    directory.mkdir(parents=True, exist_ok=True)
print('Persistent run:', DRIVE_RUN)
"""
            ),
            _markdown("## Phase 2 - Install only when inference or training is needed"),
            _code(install_when_needed),
            _markdown(
                "## Phase 3 - Restore report, or prepare a version-locked dataset\n\n"
                "Prepared public data is cached in Drive. The combined manifest is "
                "rebuilt only when the v3 capture manifest or config changes."
            ),
            _code(
                r"""if RUN_MODE == 'report_only':
    saved_performance = OUTPUT_DRIVE / 'performance'
    if saved_performance.is_dir():
        shutil.copytree(saved_performance, PERF, dirs_exist_ok=True)
        print('Restored saved Drive performance; no model training/evaluation ran.')
    elif (PERF / 'metrics.json').is_file():
        print(
            'No saved Drive report yet; displaying the bundled 2026-08-30 '
            'local CPU reference. This is not a Colab run or deployment evidence.'
        )
    else:
        raise FileNotFoundError(f'No saved or bundled report at {saved_performance}')
else:
    print('Phase 3 started: validating Drive cache and required raw data.', flush=True)
    cached_processed = CACHE_DRIVE / 'processed'

    def copy_tree_with_progress(source, destination, label):
        files = sorted(path for path in source.rglob('*') if path.is_file())
        print(f'{label}: {len(files):,} files', flush=True)
        report_every = max(1, len(files) // 10)
        for index, source_path in enumerate(files, start=1):
            relative = source_path.relative_to(source)
            destination_path = destination / relative
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            if index == len(files) or index % report_every == 0:
                print(f'  {index:,}/{len(files):,} files', flush=True)

    def copy_file_with_progress(source, destination, label):
        total = source.stat().st_size
        copied = 0
        next_report = 0.1
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(f'{label}: {total / (1024 ** 3):.2f} GiB', flush=True)
        with source.open('rb') as input_handle, destination.open('wb') as output_handle:
            while True:
                chunk = input_handle.read(16 * 1024 * 1024)
                if not chunk:
                    break
                output_handle.write(chunk)
                copied += len(chunk)
                fraction = copied / total if total else 1.0
                if fraction >= next_report or copied == total:
                    print(f'  {fraction:.0%}', flush=True)
                    next_report += 0.1
        shutil.copystat(source, destination)

    def extract_zip_with_progress(archive_path, destination, label):
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path) as package:
            members = package.infolist()
            print(f'{label}: {len(members):,} ZIP members', flush=True)
            report_every = max(1, len(members) // 10)
            for index, member in enumerate(members, start=1):
                package.extract(member, destination)
                if index == len(members) or index % report_every == 0:
                    print(f'  {index:,}/{len(members):,} members', flush=True)

    # Public manifests and QR-surface crops are small enough to restore directly.
    # The large combined version is restored only after its identity is verified.
    for public_name in ('qrdn', 'qr_surfaces'):
        primary_public_cache = cached_processed / public_name
        fallback_public_cache = BASE_CACHE_DRIVE / 'processed' / public_name
        public_cache = (
            primary_public_cache
            if primary_public_cache.is_dir()
            else fallback_public_cache
        )
        if public_cache.is_dir():
            copy_tree_with_progress(
                public_cache,
                PROCESSED_ROOT / public_name,
                f'Phase 3: restoring cached {public_name} metadata/crops',
            )

    downloads = REPO / 'ml_training/datasets/structural/downloads'
    archives = {
        DATA_DRIVE / 'QR-DN1.0.zip': downloads / 'qrdn/QR-DN1.0.zip',
        DATA_DRIVE / 'qr_codes_in_surfaces.zip': downloads / 'qr_surfaces/qr_codes_in_surfaces.zip',
    }
    raw_sentinels = {
        'qrdn': (
            REPO / 'ml_training/datasets/structural/raw/qrdn/'
            'extracted One/train/0.jpg'
        ),
        'qr_surfaces': (
            REPO / 'ml_training/datasets/structural/raw/qr_surfaces/'
            'flat/images/IMG_20191225_202803.jpg'
        ),
    }
    public_manifests_ready = all(
        (PROCESSED_ROOT / name / 'manifest.csv').is_file()
        for name in ('qrdn', 'qr_surfaces')
    )
    raw_ready = all(path.is_file() for path in raw_sentinels.values())
    if not raw_ready:
        print('Phase 3: restoring official raw datasets from Drive ZIPs.', flush=True)
        for source, destination in archives.items():
            if not source.is_file():
                raise FileNotFoundError(f'Missing official archive: {source}')
            copy_file_with_progress(
                source, destination, f'Copying {source.name} from Drive'
            )
        print('Phase 3: verifying official archive size and SHA-256.', flush=True)
        run_module('ml_training.scripts.verify_datasets')
        for archive, destination in (
            (archives[DATA_DRIVE / 'QR-DN1.0.zip'], REPO / 'ml_training/datasets/structural/raw/qrdn'),
            (archives[DATA_DRIVE / 'qr_codes_in_surfaces.zip'], REPO / 'ml_training/datasets/structural/raw/qr_surfaces'),
        ):
            extract_zip_with_progress(
                archive, destination, f'Extracting {archive.name}'
            )
        missing_raw = [name for name, path in raw_sentinels.items() if not path.is_file()]
        if missing_raw:
            raise FileNotFoundError(
                f'Official raw extraction incomplete; missing sentinels: {missing_raw}'
            )
    else:
        print('Phase 3: official raw dataset sentinels are present.', flush=True)

    if not public_manifests_ready:
        print('Phase 3: preparing public dataset manifests/crops.', flush=True)
        run_module('ml_training.structural.src.prepare_qrdn')
        run_module('ml_training.structural.src.prepare_qr_surfaces')
    else:
        print('Phase 3: cached public manifests/crops are present.', flush=True)

    drive_captures = DATA_DRIVE / 'runtime_captures'
    local_captures = REPO / 'data/runtime_captures'
    local_captures.mkdir(parents=True, exist_ok=True)
    if drive_captures.is_dir():
        copy_tree_with_progress(
            drive_captures,
            local_captures,
            'Phase 3: restoring exact QRGuard app-camera captures',
        )
    capture_audit = run_module(
        'ml_training.structural.src.prepare_structural_v3_captures',
        local_captures, '--strict', check=False,
    )
    print('Real paired capture gate:',
          'READY' if capture_audit.returncode == 0 else 'NOT READY - candidate only')

    capture_manifest = local_captures / 'manifest_v3.csv'
    config_path = REPO / 'ml_training/configs' / f'{VERSION}.json'
    cache_contract_path = CACHE_DRIVE / 'cache_contract.json'
    expected_contract = {
        'version': VERSION,
        'dataset_version': DATASET_VERSION,
        'config_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
        'capture_manifest_sha256': hashlib.sha256(capture_manifest.read_bytes()).hexdigest(),
        'coverage_development_sha256': hashlib.sha256(
            (REPO / 'data/structural_coverage_development/2026-09-r01/manifest.csv').read_bytes()
        ).hexdigest(),
        'physical_attack_development_sha256': hashlib.sha256(
            (REPO / 'data/structural_physical_attack_development/2026-09-r02/manifest.csv').read_bytes()
        ).hexdigest(),
        'prepared_gallery_reference_sha256': hashlib.sha256(
            (REPO / 'data/prepared_gallery_references/structural-2026.03-r01/manifest.csv').read_bytes()
        ).hexdigest(),
        'acquisition_quality_development_sha256': hashlib.sha256(
            (REPO / 'data/acquisition_quality_development/2026-09-r02/manifest.csv').read_bytes()
        ).hexdigest(),
        'consumed_blind_clean_development_sha256': hashlib.sha256(
            (REPO / 'data/structural_consumed_blind_development/2026-09-r01/manifest.csv').read_bytes()
        ).hexdigest(),
        'consumed_blind_verified_attack_development_sha256': hashlib.sha256(
            (REPO / 'data/structural_consumed_blind_attack_development/r07-corrective-v1/manifest.csv').read_bytes()
        ).hexdigest(),
    }
    recorded_contract = (
        json.loads(cache_contract_path.read_text())
        if cache_contract_path.is_file() else None
    )
    combined_manifest = PROCESSED_ROOT / DATASET_VERSION / 'manifest.csv'
    combined_cache_archive = CACHE_DRIVE / f'processed-{DATASET_VERSION}.zip'
    recorded_identity = (
        {key: recorded_contract.get(key) for key in expected_contract}
        if isinstance(recorded_contract, dict) else None
    )
    archive_sha256 = (
        recorded_contract.get('prepared_archive_sha256')
        if isinstance(recorded_contract, dict) else None
    )
    cache_matches = recorded_identity == expected_contract
    if cache_matches and combined_cache_archive.is_file() and archive_sha256:
        local_cache_archive = Path('/tmp') / combined_cache_archive.name
        copy_file_with_progress(
            combined_cache_archive,
            local_cache_archive,
            'Phase 3: restoring locked 14,240-row prepared cache',
        )
        actual_archive_sha256 = hashlib.sha256(local_cache_archive.read_bytes()).hexdigest()
        if actual_archive_sha256 != archive_sha256:
            raise ValueError(
                'Prepared cache archive SHA-256 mismatch: '
                f'{actual_archive_sha256} != {archive_sha256}'
            )
        extract_zip_with_progress(
            local_cache_archive,
            PROCESSED_ROOT,
            'Extracting locked prepared cache',
        )
        run_module(
            'ml_training.structural.src.train_local',
            '--mode', RUN_MODE,
            '--prepare-only',
        )
        print('Phase 3: locked cache identity and candidate manifest passed.', flush=True)
    else:
        print(
            'Phase 3: combined cache is absent/stale; rebuilding the locked dataset.',
            flush=True,
        )
        base_contract_path = BASE_CACHE_DRIVE / 'cache_contract.json'
        base_archive = (
            BASE_CACHE_DRIVE / 'processed-structural-2026.09-r07.zip'
        )
        if not base_contract_path.is_file() or not base_archive.is_file():
            raise FileNotFoundError(
                'The locked r07 base cache is required for the corrective run.'
            )
        if base_contract_path.is_file() and base_archive.is_file():
            base_contract = json.loads(base_contract_path.read_text())
            base_archive_sha256 = base_contract.get('prepared_archive_sha256')
            if (
                base_contract.get('version') == 'structural-2026.09-r07'
                and base_contract.get('dataset_version')
                == 'structural-2026.09-r07'
                and base_archive_sha256
            ):
                local_base_archive = Path('/tmp') / base_archive.name
                copy_file_with_progress(
                    base_archive,
                    local_base_archive,
                    'Phase 3: restoring verified r07 base image cache',
                )
                actual_base_sha256 = hashlib.sha256(
                    local_base_archive.read_bytes()
                ).hexdigest()
                if actual_base_sha256 != base_archive_sha256:
                    raise ValueError(
                        'Base prepared cache SHA-256 mismatch: '
                        f'{actual_base_sha256} != {base_archive_sha256}'
                    )
                extract_zip_with_progress(
                    local_base_archive,
                    PROCESSED_ROOT,
                    'Extracting verified r07 base image cache',
                )
                base_prepared = PROCESSED_ROOT / 'structural-2026.09-r07'
                if not base_prepared.is_dir():
                    raise FileNotFoundError(base_prepared)
                copied_candidate = PROCESSED_ROOT / DATASET_VERSION
                run_module(
                    'scripts.build_structural_r07_corrective_cache',
                    '--base-root', base_prepared,
                    '--target-root', copied_candidate,
                )
                print(
                    'Phase 3: reused the verified r07 prepared cache and appended '
                    'only verified surviving attack hard positives.',
                    flush=True,
                )
            else:
                raise ValueError('The r07 base cache contract is invalid.')
        if not combined_manifest.is_file():
            run_module(
                'ml_training.structural.src.train_local',
                '--mode', RUN_MODE,
                '--prepare-only', '--rebuild-data',
            )
        else:
            run_module(
                'ml_training.structural.src.train_local',
                '--mode', RUN_MODE,
                '--prepare-only',
            )
        local_cache_archive = Path('/tmp') / combined_cache_archive.name
        print('Phase 3: packing the validated prepared dataset as one cache file.', flush=True)
        with zipfile.ZipFile(
            local_cache_archive,
            'w',
            compression=zipfile.ZIP_STORED,
            allowZip64=True,
        ) as package:
            prepared_version = PROCESSED_ROOT / DATASET_VERSION
            prepared_files = sorted(
                path for path in prepared_version.rglob('*') if path.is_file()
            )
            report_every = max(1, len(prepared_files) // 10)
            for index, path in enumerate(prepared_files, start=1):
                package.write(path, path.relative_to(PROCESSED_ROOT).as_posix())
                if index == len(prepared_files) or index % report_every == 0:
                    print(f'  packed {index:,}/{len(prepared_files):,} files', flush=True)
        prepared_archive_sha256 = hashlib.sha256(
            local_cache_archive.read_bytes()
        ).hexdigest()
        copy_file_with_progress(
            local_cache_archive,
            combined_cache_archive,
            'Phase 3: saving validated prepared cache to Drive',
        )
        cache_contract_path.write_text(
            json.dumps(
                {
                    **expected_contract,
                    'prepared_archive_sha256': prepared_archive_sha256,
                },
                indent=2,
            )
        )
        print('Phase 3: prepared dataset and Drive cache refreshed.', flush=True)

    manifest_bytes = combined_manifest.read_bytes()
    manifest_rows = max(0, manifest_bytes.count(b'\n') - 1)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    print(
        f'Phase 3 complete: rows={manifest_rows:,}; sha256={manifest_sha256}',
        flush=True,
    )
"""
            ),
            _markdown("## Phase 4 - Dataset composition and leakage audit"),
            _code(
                r"""if RUN_MODE != 'report_only':
    import pandas as pd
    manifest = pd.read_csv(PROCESSED_ROOT / DATASET_VERSION / 'manifest.csv')
    display(pd.crosstab(manifest.split, [manifest.label, manifest.source]))
    groups = {name: set(part.group_id) for name, part in manifest.groupby('split')}
    overlaps = {
        f'{left}/{right}': len(groups[left] & groups[right])
        for index, left in enumerate(groups)
        for right in list(groups)[index + 1:]
    }
    assert not any(overlaps.values()), overlaps
    print('Rows:', len(manifest), '| groups:', manifest.group_id.nunique())
    if 'quality_condition' in manifest:
        display(pd.crosstab(manifest.quality_condition, manifest.label))
"""
            ),
            _markdown(
                "## Phase 5 - Train/resume/evaluate, then save outputs\n\n"
                "Every completed epoch is checkpointed to Drive. A gate failure "
                "still produces a valid candidate report and never updates the app."
            ),
            _code(
                r"""if RUN_MODE != 'report_only':
    execution = run_module(
        'ml_training.structural.src.train_local',
        '--mode', RUN_MODE,
        '--checkpoint-dir', CHECKPOINT_DIR,
        check=False,
    )
    if PERF.is_dir():
        shutil.copytree(PERF, OUTPUT_DRIVE / 'performance', dirs_exist_ok=True)
    if ARTIFACTS.is_dir():
        shutil.copytree(ARTIFACTS, OUTPUT_DRIVE / 'artifacts', dirs_exist_ok=True)
    print('Execution return code:', execution.returncode)
    if not (PERF / 'metrics.json').is_file():
        raise RuntimeError('Execution stopped before a complete performance report.')
"""
            ),
            _markdown("## Phase 6 - Display reusable performance evidence"),
            _code(
                r"""from IPython.display import Image as DisplayImage, Markdown, display
import pandas as pd

metrics_path = PERF / 'metrics.json'
if not metrics_path.is_file():
    raise FileNotFoundError(metrics_path)
metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
if metrics.get('version') != VERSION:
    raise RuntimeError(f"Wrong report version: {metrics.get('version')}")
current_config = REPO / 'ml_training/configs' / f'{VERSION}.json'
current_config_hash = hashlib.sha256(current_config.read_bytes()).hexdigest()
if metrics.get('run_identity', {}).get('config_sha256') != current_config_hash:
    raise RuntimeError('Saved report does not match this Structural config.')
state_path = CHECKPOINT_DIR / 'run_state.json'
if state_path.is_file():
    saved_state = json.loads(state_path.read_text(encoding='utf-8'))
    if saved_state.get('identity') != metrics.get('run_identity'):
        raise RuntimeError('Saved report and checkpoint run identities disagree.')
display(Markdown((PERF / 'STRUCTURAL_PERFORMANCE.md').read_text(encoding='utf-8')))
display(pd.DataFrame([
    {'Gate': 'Research', 'Passed': metrics['research_gates_passed'],
     'Failures': '; '.join(metrics['research_gate_failures']) or 'none'},
    {'Gate': 'Deployment', 'Passed': metrics['deployment_gates_passed'],
     'Failures': '; '.join(metrics['deployment_gate_failures']) or 'none'},
]))
for name in ('training_curves.png', 'confusion_matrix.png', 'roc_pr_curves.png',
             'calibration_curve.png', 'qrdn_clean_distribution.png'):
    path = PERF / name
    if path.is_file():
        display(Markdown(f'### {name}'))
        display(DisplayImage(filename=str(path)))
for name in ('metrics.csv', 'dataset_composition.csv', 'per_source_results.csv',
             'per_device_results.csv', 'per_quality_condition_results.csv',
             'quality_abstention_results.csv', 'gallery_camera_consistency.csv',
             'exported_gallery_camera_consistency.csv',
             'exported_runtime_predictions.csv', 'misclassified_samples.csv',
             'training_history.csv'):
    path = PERF / name
    if path.is_file() and path.stat().st_size:
        display(Markdown(f'### {name}'))
        display(pd.read_csv(path).head(50))
print('Persistent output:', OUTPUT_DRIVE)
"""
            ),
            _markdown("## Phase 7 - Validate report completeness (no promotion)"),
            _code(
                r"""validation = run_module(
    'ml_training.scripts.validate_performance_bundle',
    '--branch', 'structural', '--structural-version', VERSION,
    check=False,
) if RUN_MODE != 'report_only' else None
if validation is not None:
    print('Report validation return code:', validation.returncode)
print('Done. This notebook did not push, deploy, or replace runtime models.')
"""
            ),
        ]
    )


def semantic_frozen_notebook() -> dict:
    return _notebook(
        [
            _markdown(
                "# QRGuard Semantic semantic-2026.02 - frozen performance report\n\n"
                "FYP2 keeps this trained semantic artifact frozen. This notebook "
                "displays the checked-in measured evidence; it does not retrain it."
            ),
            _code(COMMON_SETUP),
            _code(
                r"""from IPython.display import Image as DisplayImage, Markdown, display
import pandas as pd
PERF = REPO / 'ml_training/semantic/performance/semantic-2026.02'
metrics = json.loads((PERF / 'metrics.json').read_text(encoding='utf-8'))
assert metrics['version'] == 'semantic-2026.02'
display(Markdown((PERF / 'SEMANTIC_PERFORMANCE.md').read_text(encoding='utf-8')))
display(metrics)
for name in ('training_curves.png', 'confusion_matrix.png', 'roc_pr_curves.png',
             'calibration_curve.png'):
    display(DisplayImage(filename=str(PERF / name)))
for name in ('metrics.csv', 'dataset_composition.csv', 'threshold_analysis.csv',
             'per_source_results.csv', 'hard_benign_results.csv',
             'behavioural_acceptance.csv'):
    display(Markdown(f'### {name}'))
    display(pd.read_csv(PERF / name).head(50))
print('Semantic remains frozen; no training or deployment occurred.')
"""
            ),
        ]
    )


def decision_frozen_notebook() -> dict:
    return _notebook(
        [
            _markdown(
                "# QRGuard Decision decision-2026.03-r05 — frozen performance report\n\n"
                "This notebook displays the saved local Fusion/Decision evidence. "
                "It does not retrain, promote, push, or deploy any model."
            ),
            _markdown("## Phase 0 — Reproducible workspace and Drive mount"),
            _code(COMMON_SETUP),
            _markdown("## Phase 1 — Display locked Decision performance evidence"),
            _code(
                r"""from IPython.display import Image as DisplayImage, Markdown, display
import pandas as pd

PERF = REPO / 'ml_training/decision_layer/performance/decision-2026.03-r05'
metrics = json.loads((PERF / 'metrics.json').read_text(encoding='utf-8'))
assert metrics['version'] == 'decision-2026.03-r05'
assert metrics['gates_passed'] is True
assert metrics['promotion_requested'] is False

display(Markdown((PERF / 'DECISION_LAYER_PERFORMANCE.md').read_text(encoding='utf-8')))
display(Markdown('## Locked metrics JSON'))
display(metrics)
display(Markdown('## Per-cell results'))
display(pd.read_csv(PERF / 'per_cell_metrics.csv'))

for name in ('tier_confusion_matrix.png', 'score_distribution.png', 'ablation.png'):
    display(Markdown(f'### {name}'))
    display(DisplayImage(filename=str(PERF / name)))

print('The saved training run did not self-promote its outputs.')
print('The repository later promoted r01+r05 locally; external deployment is pending.')
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

This folder is the self-contained ML hand-off. Structural v3 is the current
FYP2 candidate; Semantic `semantic-2026.02` is frozen and report-only. It
contains the canonical source, dataset contracts, licences, references,
check-pointable Structural notebook, frozen Semantic report notebook, and a
frozen report of the latest Decision/Fusion candidate.

The existing measured baseline/candidate numbers are summarised in
`REFERENCE_RESULTS.md` and their original figures/JSON/CSV files are under
`reference_performance/`. Structural can create a new Drive run; the Semantic
notebook displays its frozen evidence without retraining.

## Start here

1. Upload `QRGuard_ML_Colab.zip` to `MyDrive/QRGuard_ML_Colab.zip`.
2. For Structural, download the official QR-DN1.0 v2 and QR Codes in Surfaces
   v1 archives and place them at:
   - `MyDrive/QRGuard_ML_Data/structural/QR-DN1.0.zip`
   - `MyDrive/QRGuard_ML_Data/structural/qr_codes_in_surfaces.zip`
3. If available, copy labelled exact app captures to
   `MyDrive/QRGuard_ML_Data/structural/runtime_captures/`.
4. Open `01_Structural_Training_Colab.ipynb`, choose `fresh`, `resume`,
   `evaluate_only`, or `report_only`, select a T4 GPU when needed, and Run all.
5. Open `02_Semantic_Frozen_Report_Colab.ipynb` to display the existing measured
   Semantic evidence without retraining.
6. Open `03_Decision_Frozen_Report_Colab.ipynb` to display the saved Fusion
   metrics, per-cell table and ablation without retraining or promotion.
7. Structural checkpoints and outputs are saved under
   `MyDrive/QRGuard_ML/runs/structural-r07-corrective-v1/<RUN_ID>/`.

Raw third-party datasets are not redistributed in this source package because
they are large and governed by their source terms. Official URLs, DOI/licence,
expected byte sizes, SHA-256 hashes and acquisition code are included. That is
the reproducibility material; the notebooks fetch or verify the actual data.

## Honest camera gate

A QR can decode successfully while the image-integrity model cannot safely use
the camera frames. Decoding and Structural classification are different tasks.
Synthetic camera augmentation alone cannot prove performance on QRGuard's exact
crop pipeline. The deployed r01 model remains unchanged. The corrective notebook
starts from the locked r07 best checkpoint, connects all legal masks in one
consistency graph, retains 80 consumed clean hard negatives, and admits only 10
consumed attack crops with verified physical survival. Every consumed row remains
non-promoting. A new device/display/session blind holdout is still required before promotion.
GitHub and external Render deployment remain separate, reviewed steps.

## Colour contract

Structural Training uses RGB, 224×224, `[0,1]` scaling and ImageNet RGB
normalisation. It does not use CMYK or Lab. See
`QRGuard/ml_training/COLOR_PIPELINE.md` for the exact coloured-QR generation,
camera colour-correction and serving parity contract.
"""


REFERENCE_RESULTS = """# Existing measured Structural, Semantic and Decision performance

The first table is the measured 2026-08-31 local CPU v3 real-data candidate run.
It is checked-in reproduction evidence, not invented notebook output and not an
automatic production promotion. The second table contains the existing
`2026.02` rollback baseline and frozen Semantic evidence.

| Structural v3 local candidate metric | Measured result |
|---|---:|
| Grouped test accuracy | 0.9111 |
| Grouped macro-F1 | 0.9095 |
| Adversarial recall | 0.9889 |
| Tampered recall | 0.9500 |
| QR-DN clean false-positive rate | 0.0000 |
| Exact-app Camera clean FPR | 0.0000 |
| Exact-app Camera adversarial recall | 0.9500 |
| Exact-app Camera tampered recall | 1.0000 |
| Paired Camera/Gallery verdict agreement | 0.9833 |
| ECE | 0.0278 |
| Controlled nuisance conditions | 10 |
| ONNX P95 latency (local reference machine) | 44.09 ms |
| Research gates | PASS |
| Deployment gates | PASS — deployed and remote-smoke verified |

## Existing 2026.02 baseline and frozen Semantic reference

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

## Decision v3 local candidate

| Decision metric | Measured result |
|---|---:|
| Version | decision-2026.03-r05 |
| ROC-AUC | 0.9820 |
| Blocked-tier precision | 0.9912 |
| Safe-tier false-negative rate | 0.0194 |
| Exact three-tier accuracy | 0.8667 |
| Security-impact policy acceptance | 0.9759 |
| Internal Decision gates | PASS — all 36 cells; deployed |

Semantic `semantic-2026.02` passed its recorded gates. Structural
`structural-2026.03-r01` and Decision `decision-2026.03-r05` passed their
recorded local and integration gates and were later promoted into the local
runtime. The Colab package itself never copies runtime files, pushes GitHub, or
deploys services.
"""


DATA_REQUIREMENTS = """# Data requirements and Drive layout

```text
MyDrive/
  QRGuard_ML_Colab.zip
  QRGuard_ML_Data/
    structural/
      QR-DN1.0.zip
      qr_codes_in_surfaces.zip
      runtime_captures/          # paired Gallery/Camera exact app crops
  QRGuard_ML/
    cache/                       # reusable prepared Structural data
    runs/                        # checkpoints, artifacts and performance
```

Structural archive hashes are verified against
`QRGuard/ml_training/datasets/download_verification.json`. Runtime capture
folders must follow `CAPTURE_GUIDE_V3.md`: 1–5 distinct exact PNG crops, one
authoritative frame, Gallery/Camera pair metadata, measured quality condition,
and anonymised identifiers. Raw QR payloads are never required or stored.
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
    resolved_dist = DIST.resolve()
    resolved_output = OUTPUT.resolve()
    if (
        resolved_output.parent != resolved_dist
        or resolved_output.name != "QRGuard_ML_Colab"
    ):
        raise RuntimeError(
            f"refusing to clean unexpected package path: {resolved_output}"
        )
    if OUTPUT.exists():
        # OUTPUT is fully generated. Cleaning it prevents stale files (including
        # an accidentally nested prior package) from accumulating across builds.
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPO.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "README.md").write_text(README, encoding="utf-8")
    (OUTPUT / "DATA_REQUIREMENTS.md").write_text(DATA_REQUIREMENTS, encoding="utf-8")
    (OUTPUT / "REFERENCE_RESULTS.md").write_text(REFERENCE_RESULTS, encoding="utf-8")
    structural_json = json.dumps(structural_v3_notebook(), indent=1)
    semantic_json = json.dumps(semantic_frozen_notebook(), indent=1)
    decision_json = json.dumps(decision_frozen_notebook(), indent=1)
    (OUTPUT / "01_Structural_Training_Colab.ipynb").write_text(
        structural_json, encoding="utf-8"
    )
    (OUTPUT / "02_Semantic_Frozen_Report_Colab.ipynb").write_text(
        semantic_json, encoding="utf-8"
    )
    (OUTPUT / "03_Decision_Frozen_Report_Colab.ipynb").write_text(
        decision_json, encoding="utf-8"
    )
    (ROOT / "ml_training/structural/notebooks/structural_training_v3.ipynb").write_text(
        structural_json, encoding="utf-8"
    )
    (ROOT / "ml_training/semantic/notebooks/semantic_frozen_report.ipynb").write_text(
        semantic_json, encoding="utf-8"
    )
    decision_notebook = (
        ROOT / "ml_training/decision_layer/notebooks/decision_frozen_report.ipynb"
    )
    decision_notebook.parent.mkdir(parents=True, exist_ok=True)
    decision_notebook.write_text(decision_json, encoding="utf-8")

    for relative in (
        "ML_START_HERE.md",
        "ml_training/__init__.py",
        "ml_training/README.md",
        "ml_training/LATEST.md",
        "ml_training/CURRENT_CHECKPOINT.md",
        "ml_training/PERFORMANCE_VALIDATION.json",
        "ml_training/deployment/model_registry.json",
        "ml_training/deployment/promotion/structural-2026.03-r01__decision-2026.03-r05/README.md",
        "ml_training/deployment/promotion/structural-2026.03-r01__decision-2026.03-r05/PRODUCTION_SMOKE.json",
        "ml_training/deployment/promotion/structural-2026.03-r01__decision-2026.03-r05/candidate_stack_metrics.json",
        "ml_training/CLEANUP_REVIEW_2026-08-30.md",
        "ml_training/WORKSPACE_AUDIT_2026-08-30.md",
        "ml_training/CLEANUP_AUDIT.json",
        "ml_training/DATASET_RETENTION.json",
        "ml_training/R07_CORRECTIVE_HANDOFF.md",
        "ml_training/COLOR_PIPELINE.md",
        "ml_training/EXECUTION_PLAN.md",
        "ml_training/RESULTS_INDEX.md",
        "ml_training/requirements.txt",
    ):
        _copy_file(relative)
    for relative in (
        "ml_training/configs",
        "ml_training/datasets/references",
        "ml_training/scripts",
        "ml_training/structural/src",
        "ml_training/semantic/src",
    ):
        _copy_tree(relative)
    for relative in (
        "ml_training/datasets/README.md",
        "ml_training/datasets/download_verification.json",
        "ml_training/datasets/manifests/structural.template.csv",
        "ml_training/datasets/manifests/structural_v3.template.csv",
        "ml_training/datasets/manifests/semantic.template.csv",
        "ml_training/structural/README.md",
        "ml_training/structural/CAPTURE_GUIDE_V3.md",
        "ml_training/structural/COLAB_RUN_GUIDE_V3.md",
        "ml_training/structural/OFFLINE_CAPTURE_AND_IMPORT.md",
        "ml_training/structural/STRUCTURAL_V3_EXECUTION_PLAN.md",
        "ml_training/structural/STRUCTURAL_V3_LOCAL_RESULTS_2026-08-30.md",
        "ml_training/structural/STRUCTURAL_V3_REAL_100X3_RESULTS_2026-08-31.md",
        "ml_training/structural/EXPOSURE_INVARIANT_TRAINING.md",
        "ml_training/semantic/README.md",
        "ml_training/decision_layer/README.md",
        "ml_training/decision_layer/DECISION_V3_LOCAL_RESULTS_2026-08-30.md",
        "backend/semantic/__init__.py",
        "backend/semantic/semantic_features.py",
        "backend/semantic/semantic_service.py",
        "backend/structural/__init__.py",
        "backend/structural/image_quality.py",
        "backend/structural/structural_service.py",
        "scripts/evaluate_candidate_stack.py",
        "scripts/import_prepared_gallery_references.py",
        "scripts/build_structural_r07_corrective_cache.py",
        "scripts/import_consumed_blind_attack_development.py",
        "scripts/train_fusion.py",
        "ml_training/structural/runs/structural-2026.09-r07/colab-r07-dense-screen-clean-recovery-v1/checkpoints/best_model.pt",
    ):
        _copy_file(relative)
    # Private exact-app captures are not published. Include their aggregate audit
    # when it is installed locally, but keep public-source bundle builds valid.
    if (ROOT / "data/runtime_captures/audit.json").is_file():
        _copy_file("data/runtime_captures/audit.json")
    _copy_tree("data/structural_coverage_development/2026-09-r01")
    _copy_tree("data/structural_physical_attack_development/2026-09-r02")
    _copy_tree("data/acquisition_quality_development/2026-09-r02")
    _copy_tree("data/structural_consumed_blind_development/2026-09-r01")
    _copy_tree("data/structural_consumed_blind_attack_development/r07-corrective-v1")
    _copy_tree("data/prepared_gallery_references/structural-2026.03-r01")
    _copy_tree(
        "ml_training/structural/performance/structural-2026.02",
    )
    _copy_tree(
        "ml_training/structural/performance/structural-2026.03-r01",
    )
    _copy_tree(
        "ml_training/structural/performance/structural-2026.09-r07",
    )
    _copy_tree(
        "ml_training/semantic/performance/semantic-2026.02",
    )
    _copy_tree(
        "ml_training/decision_layer/performance/decision-2026.03-r05",
    )
    _copy_tree(
        "ml_training/structural/campaigns/structural-v3-real-2026.03-r01",
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
    with zipfile.ZipFile(
        ZIP_PATH,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(p for p in OUTPUT.rglob("*") if p.is_file()):
            archive_name = (Path(OUTPUT.name) / path.relative_to(OUTPUT)).as_posix()
            info = zipfile.ZipInfo(archive_name, date_time=DETERMINISTIC_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.file_size = path.stat().st_size
            with path.open("rb") as source, archive.open(
                info, "w", force_zip64=True
            ) as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
    print(f"Built {OUTPUT}")
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
