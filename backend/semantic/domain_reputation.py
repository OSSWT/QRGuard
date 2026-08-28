"""Domain reputation — is this registered domain a well-known site?

Implements the proposal's "domain reliability" signal for the Semantic branch, and
exists because of a measured effect: Method 1's false-positive rate on benign URLs is
**11.4% on domains inside the Tranco top-150k but 43.9% on unknown domains**. The
string model is simply far more reliable on sites it has seen the shape of, so telling
the Fusion Engine whether a domain is well-known lets it weigh `p_url` accordingly.

The signal is exposed as `domain_unknown` (1 = not in the list) so it behaves as a RISK
feature, consistent with the fusion engine's monotonic non-negative weighting.

Important: an unknown domain is NOT evidence of fraud on its own — most small
legitimate businesses are unknown. It is a *reliability* hint, and the fusion model
learns from data how much it is worth. Conversely a well-known domain is not proof of
safety either (famous sites do get compromised — that is what the `defacement` class in
the training corpus represents), which is why this is a feature and never an override.
"""

from __future__ import annotations

import gzip
from functools import lru_cache
from pathlib import Path
from typing import Optional

_LIST_PATH = Path(__file__).resolve().parent.parent / "data" / "tranco_top.txt.gz"


@lru_cache(maxsize=1)
def _load_domains(path: Optional[str] = None) -> frozenset[str]:
    """Load the well-known-domain set once per process (~150k entries)."""
    p = Path(path) if path else _LIST_PATH
    if not p.is_file():
        return frozenset()
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return frozenset(line.strip().lower() for line in f if line.strip())


def is_well_known(registered_domain: Optional[str]) -> bool:
    """True if the registered domain appears in the top-domains list."""
    if not registered_domain:
        return False
    return registered_domain.strip().lower() in _load_domains()


def domain_unknown(registered_domain: Optional[str]) -> float:
    """Fusion feature: 1.0 when the domain is NOT well known, else 0.0.

    A missing/unparseable domain counts as unknown — absence of a recognisable
    registrable domain is itself unusual for a legitimate destination.
    """
    return 0.0 if is_well_known(registered_domain) else 1.0


def list_size() -> int:
    """Number of loaded domains — used in health checks and tests."""
    return len(_load_domains())
