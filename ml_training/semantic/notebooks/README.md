# Semantic notebooks

`semantic_training.ipynb` is the canonical complete Semantic training notebook.
It prepares the registered URL datasets, trains a serving-compatible candidate,
validates the saved artifacts and writes the run to an isolated candidate
version. It never promotes or deploys a model.

`semantic_frozen_report.ipynb` is the canonical report-only notebook for the
deployed `semantic-2026.02` model. It displays saved evidence and intentionally
does not retrain the frozen Semantic branch.

The early DomURLs BERT experiment is not part of this folder or repository. It
used a different architecture from the current runtime model and was removed to
keep the two supported workflows unambiguous.
