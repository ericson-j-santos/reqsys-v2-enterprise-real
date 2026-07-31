from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = REPO_ROOT / "governance/bacen/CYBERSECURITY-POLICY-METADATA.yaml"


def test_bacen_01_decision_reference_is_canonical_without_false_promotion() -> None:
    metadata = yaml.safe_load(METADATA_PATH.read_text(encoding="utf-8"))
    evidence = metadata["decision_evidence"]

    assert metadata["schema_version"] == "1.1.0"
    assert evidence["decision"] == "approved"
    assert evidence["authenticated_actor"] == "ericson-j-santos"
    assert evidence["comment_url"].endswith("#issuecomment-5141594075")
    assert evidence["comment_sha256"] == (
        "95a733dc11d523500a09ea94c3f091b7d11ebfd76ea2d6d8b6b3acc4d2477b18"
    )
    assert evidence["decision_record_reference"] == "REF-2026-001"
    assert evidence["personal_or_sensitive_content_replicated"] is False
    assert evidence["automatic_status_promotion_allowed"] is False

    assert metadata["approval_status"] == "pending_formal_institutional_approval"
    assert metadata["approval_authority"] == "pending_formal_designation"
    assert metadata["approval_record"] is None
    assert metadata["production_touched"] is False
