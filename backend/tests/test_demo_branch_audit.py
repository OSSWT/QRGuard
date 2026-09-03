"""Branch-level gates that prevent SEM-05-style masked errors."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.audit_demo_branches import audit_documents

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "ml_training/datasets/qr_codes_demo"
CONTRACT = ROOT / "ml_training/configs/demo_branch_expectations.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _documents() -> tuple[dict, dict, dict]:
    return (
        _json(PACK / "MANIFEST.json"),
        _json(PACK / "AUTOMATED_RESULTS_LOCAL.json"),
        _json(CONTRACT),
    )


def test_locked_demo_evidence_passes_every_branch_contract():
    report = audit_documents(*_documents())
    assert report["summary"] == {
        "request_count": 84,
        "final_matches": 84,
        "structural_matches": 84,
        "semantic_matches": 84,
        "reasons_match": 84,
        "branch_contract_matches": 84,
        "masked_branch_errors": 0,
        "gate_passed": True,
    }
    assert report["failures"] == []


def test_sem_05_wrong_structural_branch_is_a_masked_error():
    manifest, evidence, contract = _documents()
    evidence = deepcopy(evidence)
    sem_05 = next(row for row in evidence["results"] if row["case_id"] == "SEM-05-USERINFO")
    camera = sem_05["camera_simulation"]
    assert camera["verdict"] == "blocked"
    camera["structural_type"] = "adversarial"
    camera["reasons"] = [
        *camera["reasons"],
        "QR image appears manipulated",
        "Structural model confirmed QR manipulation",
    ]

    report = audit_documents(manifest, evidence, contract)
    assert report["summary"]["final_matches"] == 84
    assert report["summary"]["structural_matches"] == 83
    assert report["summary"]["masked_branch_errors"] == 1
    assert report["summary"]["gate_passed"] is False
    assert report["failures"] == [
        next(
            row
            for row in report["results"]
            if row["case_id"] == "SEM-05-USERINFO"
            and row["source"] == "camera_simulation"
        )
    ]


def test_sem_11_final_mismatch_is_not_hidden_as_a_branch_error():
    manifest, evidence, contract = _documents()
    evidence = deepcopy(evidence)
    sem_11 = next(row for row in evidence["results"] if row["case_id"] == "SEM-11-PLAIN-TEXT")
    sem_11["camera_simulation"]["verdict"] = "blocked"

    report = audit_documents(manifest, evidence, contract)
    failure = next(
        row
        for row in report["failures"]
        if row["case_id"] == "SEM-11-PLAIN-TEXT"
        and row["source"] == "camera_simulation"
    )
    assert failure["final_matches"] is False
    assert failure["branch_contract_matches"] is True
    assert failure["masked_branch_error"] is False
