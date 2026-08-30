from scripts.evaluate_candidate_stack import summarise


def test_candidate_stack_summary_uses_final_verdicts_and_complete_pairs():
    rows = []
    for label, verdict in (
        ("clean", "safe"),
        ("adversarial", "blocked"),
        ("tampered", "blocked"),
    ):
        for source in ("gallery", "camera"):
            rows.append(
                {
                    "label": label,
                    "image_source": source,
                    "paired_group": label,
                    "structural_status": "completed",
                    "verdict": verdict,
                }
            )

    metrics = summarise(rows)

    assert metrics["per_source"]["camera"]["clean_false_block_rate"] == 0.0
    assert metrics["per_source"]["camera"]["adversarial_block_recall"] == 1.0
    assert metrics["per_source"]["camera"]["tampered_block_recall"] == 1.0
    assert metrics["paired"]["complete_pairs"] == 3
    assert metrics["paired"]["exact_verdict_agreement"] == 1.0
