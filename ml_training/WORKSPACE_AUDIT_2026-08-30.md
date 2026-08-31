# Workspace audit — 2026-08-30

This is a read-only classification of the local workspace before Structural v3
implementation. No file was deleted during the audit.

## Baseline

- Git branch before work: `main` at `3ab23334b43cd73eded0ea9b9fc4e2d6173b505e`.
- Work started on local branch `work/structural-2026.03-r01`.
- Backend: 293 tests passed.
- Flutter: 69 tests passed; `flutter analyze` reported no issues.
- The broad Python Ruff invocation reports 262 pre-existing issues. New work is
  checked with targeted lint; unrelated mass-formatting is out of scope.

## Canonical folders — retain

| Path | Purpose |
|---|---|
| `backend/` | API, inference services and fusion runtime |
| `app/` | Flutter client |
| `ml_training/` | Canonical training recipes, manifests, provenance and measured results |
| `training/artifacts/structural/` | Current Gallery runtime artifact; do not overwrite during candidate work |
| `training/artifacts/semantic/` | Frozen accepted Semantic runtime artifact |
| `research_evidence/` | Report-facing evidence snapshot |
| `dist/QRGuard_ML_Colab/` and zip | Ignored Colab hand-off generated from canonical sources |
| `deploy/` | Deployment definitions; unchanged until manual promotion |

The report-facing copies under `research_evidence` are intentional snapshots.
The Colab hand-off is regenerated from canonical sources and is never edited
independently.

## Large local data — retain while training

- `ml_training/` is about 4.59 GiB, dominated by verified dataset archives,
  extracted/processed data and experiment outputs.
- QR-DN1.0 v2 archive: about 978 MiB, verified and expensive to download again.
- QR Surfaces archive: about 366 MiB, verified.
- `.venv/` is about 1.35 GiB and reproducible, but retaining it avoids reinstall
  time during active work.
- `data/` is about 134 MiB and contains local evaluation/runtime inputs.

Raw, processed and download folders are Git-ignored. Their manifests, official
URLs and hashes are the durable record.

## Review-required legacy material

`training/` occupies about 1.68 GiB locally. Only the active Structural and
Semantic runtime artifacts plus a few legacy scripts are tracked. Large ignored
items include old Method 1 Transformer exports, archived zips and Structural
RUN 1–5 folders. They are likely archive/delete candidates, but must first be
matched against `ml_training/deployment/rollback` and report references.

No legacy model or zip may be removed solely because it has the same filename as
another artifact; hashes, registry references and rollback purpose must be
checked first.

## 2026-08-31 organisation update

The tracked root-level `QRGuard_ML_Colab/` snapshot and ZIP were verified as
generated duplicates and retired. Canonical notebooks are retained under
`ml_training/*/notebooks/`; the builder and its contract tests now regenerate an
ignored package under `dist/`. This update supersedes the earlier classification
of the root-level generated package as a tracked retention item.

## Regenerable cleanup candidates — no deletion yet

| Candidate | Approximate effect | Condition before removal |
|---|---:|---|
| `app/build/` and root `build/` | major local space recovery | Flutter tests/build can regenerate |
| `.pytest_cache/`, `.ruff_cache/`, `ml_training/__pycache__/` | small | Always regenerable |
| `logs/` | about 3 MiB | Preserve any report/debug evidence first |
| `QRGuard_colab_source.zip` | small | Superseded by canonical bundle builder |
| old ignored `training/artifacts/**` archives/models | potentially over 1.5 GiB | Complete hash/reference/rollback audit |

The previous root-level tracked package has now been replaced by the ignored
`dist/` build output described above.

## Secret handling

`GEMINI_API_KEY.env.txt` exists locally, is covered by the secret patterns in
`.gitignore`, and is not tracked. Its contents were not read during this audit.
Moving secrets outside the repository can be considered after confirming the
local startup scripts' expected path.

## Deletion policy

1. Generate a path-level cleanup candidate list with size, hash and references.
2. Mark each item `canonical`, `runtime`, `rollback`, `generated` or `obsolete`.
3. Run tests and rebuild checks before and after any removal.
4. Obtain explicit approval for the final deletion list.
5. Prefer a recoverable archive/move for legacy evidence before permanent
   deletion.
