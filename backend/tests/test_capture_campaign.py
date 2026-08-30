from __future__ import annotations

import hashlib
import json
from collections import Counter

import cv2
import pytest
from PIL import Image

from ml_training.structural.src.capture_campaign import (
    CAMPAIGN_ID,
    QUALITY_CONDITIONS,
    activate_case,
    audit_campaign,
    build_cases,
    create_pilot_reference,
    write_campaign,
)


def test_default_campaign_has_balanced_450_cases_and_900_sessions():
    cases = build_cases()

    assert len(cases) == 450
    assert Counter(case.label for case in cases) == {
        "clean": 150,
        "adversarial": 150,
        "tampered": 150,
    }
    assert all(case.gallery_required and case.camera_required for case in cases)
    assert len({case.case_id for case in cases}) == 450
    assert len({case.pair_token for case in cases}) == 450
    for label in ("clean", "adversarial", "tampered"):
        for condition in QUALITY_CONDITIONS:
            part = [
                case
                for case in cases
                if case.label == label and case.quality_condition == condition
            ]
            assert len(part) == 15


def test_nuisance_severity_is_balanced_and_normal_stays_none():
    cases = build_cases()

    for condition in QUALITY_CONDITIONS:
        part = [
            case
            for case in cases
            if case.label == "clean" and case.quality_condition == condition
        ]
        severities = Counter(case.quality_severity for case in part)
        if condition == "normal":
            assert severities == {"none": 15}
        else:
            assert severities == {"mild": 5, "moderate": 5, "severe": 5}


def test_adversarial_activation_requires_verified_provenance(tmp_path):
    campaign = tmp_path / "campaign"
    write_campaign(campaign)
    output = tmp_path / "captures" / "_active_case.json"

    with pytest.raises(ValueError, match="verified attack method"):
        activate_case(
            campaign / "campaign.csv",
            "adv-normal-01",
            output,
            device="pixel-test",
            environment="indoor-controlled",
        )

    context = activate_case(
        campaign / "campaign.csv",
        "adv-normal-01",
        output,
        device="pixel-test",
        environment="indoor-controlled",
        attack_method="eot_pgd",
        attack_reference_sha256="a" * 64,
    )
    assert context["attack_method"] == "eot_pgd"
    assert json.loads(output.read_text())["attack_reference_sha256"] == "a" * 64


def test_tampered_activation_requires_documented_manipulation(tmp_path):
    campaign = tmp_path / "campaign"
    write_campaign(campaign)

    with pytest.raises(ValueError, match="documented manipulation"):
        activate_case(
            campaign / "campaign.csv",
            "tmp-glare-01",
            tmp_path / "captures" / "_active_case.json",
            device="pixel-test",
            environment="indoor-controlled",
        )


def test_campaign_audit_counts_only_valid_same_payload_pairs(tmp_path):
    campaign = tmp_path / "campaign"
    captures = tmp_path / "captures"
    cases = write_campaign(campaign)
    case = next(item for item in cases if item.case_id == "cln-normal-01")

    for source in ("gallery", "camera"):
        session = captures / case.label / f"scan_{source}"
        session.mkdir(parents=True)
        (session / "metadata.json").write_text(
            json.dumps(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "campaign_case_id": case.case_id,
                    "ground_truth": case.label,
                    "quality_condition": case.quality_condition,
                    "quality_severity": case.quality_severity,
                    "paired_group_sha256": hashlib.sha256(
                        case.pair_token.encode()
                    ).hexdigest(),
                    "physical_qr_sha256": hashlib.sha256(
                        case.physical_qr_token.encode()
                    ).hexdigest(),
                    "payload_sha256": "b" * 64,
                    "image_source": source,
                    "attack_method": "none",
                    "attack_reference_sha256": "",
                    "manipulation_method": "none",
                }
            ),
            encoding="utf-8",
        )

    progress = audit_campaign(campaign / "campaign.csv", captures)

    assert progress.total_cases == 450
    assert progress.expected_sessions == 900
    assert progress.valid_planned_sessions == 2
    assert progress.complete_pairs == 1
    assert progress.pending_cases == 449
    assert progress.invalid_cases == 0
    assert progress.per_label_complete_pairs["clean"] == 1
    assert (captures / "campaign_progress.json").is_file()
    assert (captures / "campaign_progress.csv").is_file()


def test_pilot_reference_keeps_raw_payload_out_of_metadata(tmp_path):
    campaign = tmp_path / "campaign"
    pilot = tmp_path / "pilot"
    write_campaign(campaign)

    metadata = create_pilot_reference(
        campaign / "campaign.csv", "cln-normal-01", pilot
    )

    image_path = pilot / str(metadata["reference_image"])
    with Image.open(image_path) as image:
        assert image.format == "PNG"
        assert image.width == image.height
        assert image.width >= 400
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(
        cv2.imread(str(image_path))
    )
    assert decoded.startswith("https://example.com/?qg3=cln-normal-01-")
    assert hashlib.sha256(decoded.encode()).hexdigest() == metadata["payload_sha256"]
    text = (pilot / "cln-normal-01-reference.json").read_text(encoding="utf-8")
    assert "raw_payload" not in json.loads(text)
    assert metadata["raw_payload_stored_in_metadata"] is False
    assert metadata["payload_policy"] == (
        "unique non-personal HTTPS URL on example.com"
    )
    assert metadata["decoder_contract"] == "opencv exact payload match"
    assert int(metadata["generation_attempts"]) >= 1
    assert len(str(metadata["payload_sha256"])) == 64

    with pytest.raises(FileExistsError, match="do not replace"):
        create_pilot_reference(
            campaign / "campaign.csv", "cln-normal-01", pilot
        )
