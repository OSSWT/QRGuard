"""Audit every QR demo request at Structural, Semantic and Fusion level.

Final-verdict-only checks can hide a wrong branch.  A clean phishing QR may still
finish Blocked when Structural incorrectly reports tampering, because Semantic
also blocks it.  This audit calls that a masked branch error and fails the gate.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "ml_training/datasets/qr_codes_demo"
DEFAULT_MANIFEST = PACK / "MANIFEST.json"
DEFAULT_EVIDENCE = PACK / "AUTOMATED_RESULTS_LOCAL.json"
DEFAULT_CONTRACT = ROOT / "ml_training/configs/demo_branch_expectations.json"

STRUCTURAL_REASONS = {
    "QR image appears manipulated",
    "Structural model confirmed QR manipulation",
}
SOURCES = ("gallery", "camera_simulation")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _expectation(case: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    if case["category"] == "structural":
        expected = deepcopy(contract["structural_category_default"])
        expected["decision_driver"] = (
            "none" if case["structural_ground_truth"] == "clean" else "structural"
        )
        return expected
    try:
        return deepcopy(contract["semantic_cases"][case["case_id"]])
    except KeyError as exc:
        raise ValueError(
            f"Missing semantic branch contract for {case['case_id']}"
        ) from exc


def _reason_attribution_matches(
    result: dict[str, Any], structural_ground_truth: str, decision_driver: str
) -> bool:
    reasons = set(result.get("reasons") or [])
    structural_reasons = reasons & STRUCTURAL_REASONS
    if structural_ground_truth == "clean" and structural_reasons:
        return False
    if structural_ground_truth != "clean" and not STRUCTURAL_REASONS.issubset(reasons):
        return False
    if decision_driver == "none" and reasons:
        return False
    return decision_driver not in {"semantic", "payload_rule"} or bool(reasons)


def audit_documents(
    manifest: dict[str, Any], evidence: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    """Return an auditable report without mutating any input document."""
    cases = {case["case_id"]: case for case in manifest["cases"]}
    evidence_rows = {row["case_id"]: row for row in evidence["results"]}
    if set(cases) != set(evidence_rows):
        missing = sorted(set(cases) - set(evidence_rows))
        extra = sorted(set(evidence_rows) - set(cases))
        raise ValueError(
            f"Evidence/manifest case mismatch; missing={missing}, extra={extra}"
        )

    rows: list[dict[str, Any]] = []
    for case_id, case in cases.items():
        expected = _expectation(case, contract)
        evidence_row = evidence_rows[case_id]
        for source in SOURCES:
            result = evidence_row[source]
            final_matches = (
                result.get("http_status") == 200
                and result.get("verdict") == case["intended_verdict"].lower()
                and result.get("partial_analysis") is False
            )
            structural_matches = (
                result.get("structural_status") == "completed"
                and result.get("structural_type") == case["structural_ground_truth"]
            )
            semantic_matches = (
                result.get("payload_type") == expected["payload_type"]
                and result.get("semantic_status") == expected["semantic_status"]
                and sorted(result.get("rule_flags") or [])
                == sorted(expected["rule_flags"])
                and (
                    (result.get("p_url") is not None)
                    == (expected["semantic_status"] == "completed")
                )
            )
            reasons_match = _reason_attribution_matches(
                result,
                case["structural_ground_truth"],
                expected["decision_driver"],
            )
            branch_matches = structural_matches and semantic_matches and reasons_match
            rows.append(
                {
                    "case_id": case_id,
                    "source": source,
                    "expected_structural_type": case["structural_ground_truth"],
                    "actual_structural_type": result.get("structural_type"),
                    "expected_semantic_status": expected["semantic_status"],
                    "actual_semantic_status": result.get("semantic_status"),
                    "expected_decision_driver": expected["decision_driver"],
                    "final_matches": final_matches,
                    "structural_matches": structural_matches,
                    "semantic_matches": semantic_matches,
                    "reasons_match": reasons_match,
                    "branch_contract_matches": branch_matches,
                    "masked_branch_error": final_matches and not branch_matches,
                }
            )

    summary = {
        "request_count": len(rows),
        "final_matches": sum(row["final_matches"] for row in rows),
        "structural_matches": sum(row["structural_matches"] for row in rows),
        "semantic_matches": sum(row["semantic_matches"] for row in rows),
        "reasons_match": sum(row["reasons_match"] for row in rows),
        "branch_contract_matches": sum(row["branch_contract_matches"] for row in rows),
        "masked_branch_errors": sum(row["masked_branch_error"] for row in rows),
    }
    summary["gate_passed"] = (
        summary["final_matches"] == len(rows)
        and summary["branch_contract_matches"] == len(rows)
        and summary["masked_branch_errors"] == 0
    )
    return {
        "schema_version": 1,
        "pack_id": manifest["pack_id"],
        "evidence_target": evidence.get("target"),
        "summary": summary,
        "failures": [
            row
            for row in rows
            if not row["final_matches"] or not row["branch_contract_matches"]
        ],
        "results": rows,
    }


def audit_files(manifest: Path, evidence: Path, contract: Path) -> dict[str, Any]:
    return audit_documents(_load(manifest), _load(evidence), _load(contract))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-fail", action="store_true")
    args = parser.parse_args()

    report = audit_files(args.manifest, args.evidence, args.contract)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report["summary"], indent=2))
    if not args.no_fail and not report["summary"]["gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
