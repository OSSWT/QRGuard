from __future__ import annotations

import numpy as np
import pandas as pd

from ml_training.structural.src.train_local import _quality_slice_row


def test_quality_slice_does_not_turn_a_missing_class_into_zero_recall() -> None:
    frame = pd.DataFrame(
        {
            "class_id": [0, 0, 2, 2],
            "group_id": ["clean-a", "clean-b", "tampered-a", "tampered-b"],
        }
    )
    probabilities = np.asarray(
        [
            [0.90, 0.05, 0.05],
            [0.20, 0.70, 0.10],
            [0.10, 0.10, 0.80],
            [0.10, 0.70, 0.20],
        ]
    )

    result = _quality_slice_row(
        "controlled_synthetic_grouped_test", "glare", frame, probabilities
    )

    assert result["rows"] == 4
    assert result["groups"] == 4
    assert result["accuracy"] == 0.5
    assert result["clean_false_positive_rate"] == 0.5
    assert result["adversarial_recall"] is None
    assert result["tampered_recall"] == 0.5
    assert "not a substitute" in result["evidence_note"]
