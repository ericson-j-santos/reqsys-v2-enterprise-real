from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGNATION_PATH = REPO_ROOT / "governance/bacen/EXECUTIVE-DESIGNATION.yaml"


def test_bacen_08_decision_reference_is_canonical_without_replicating_pii() -> None:
    document = yaml.safe_load(DESIGNATION_PATH.read_text(encoding="utf-8"))
    evidence = document["decision_evidence"]
    designation = document["designation"]

    assert document["schema_version"] == "1.1.0"
    assert evidence["decision"] == "approved"
    assert evidence["authenticated_actor"] == "ericson-j-santos"
    assert evidence["comment_url"].endswith("#issuecomment-5141616243")
    assert evidence["comment_sha256"] == (
        "d45d901949da5b527c514268e24cf5a7d04fb3e29d5c5f8df18602c69688a60f"
    )
    assert evidence["designation_document_reference"] == "REF-2026-015"
    assert evidence["report_signoff_reference"] == "REF-2026-021"
    assert evidence["personal_or_sensitive_content_replicated"] is False
    assert evidence["automatic_status_promotion_allowed"] is False

    assert designation["status"] == "pending_formal_designation"
    assert designation["executive_name"] is None
    assert designation["executive_role"] is None
    assert designation["designated_by"] is None
