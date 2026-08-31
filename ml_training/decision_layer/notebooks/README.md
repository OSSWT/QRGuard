# Decision/Fusion notebooks

`decision_frozen_report.ipynb` is the canonical report-only notebook for the
deployed `decision-2026.03-r05` candidate. It displays recorded evidence and does
not retrain or promote production artifacts.

Run `python scripts/build_colab_bundle.py` to sync the canonical notebook and
create the ignored upload bundle under `dist/`.
