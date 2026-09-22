from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGNATION_PATH = REPO_ROOT / "governance/bacen/EXECUTIVE-DESIGNATION.yaml"


def test_bacen_08_decision_reference_is_canonical_without_replicating_pii() -> None:
    document = yaml.safe_load(DESIGNATION_PATH.read_text(encoding="utf-8"))
    evidence = document["decision_evidence"]
    designation = document["designation"]

    assert document["schema_version"] == "1.2.0"
    assert evidence["decision"] == "approved"
    assert evidence["authenticated_actor"] == "ericson-j-santos"
    assert evidence["comment_url"].endswith("#issuecomment-5415495880")
    assert evidence["comment_sha256"] == (
        "fe7e01da351994f15c766c74bcab85bf03d3ce4007a8c3901723951079364be5"
    )
    assert evidence["designation_document_reference"] == "autodesignação-2026-08-25"
    assert evidence["report_signoff_reference"] is None
    assert evidence["personal_or_sensitive_content_replicated"] is False
    assert evidence["automatic_status_promotion_allowed"] is False

    deferred = document["deferred_institutional_governance"]
    assert deferred["enabled"] is True
    assert deferred["maximum_control_status"] == "partial"
    assert deferred["production_gate"]["block_production_when_missing"] is True

    assert designation["status"] == "pending_formal_designation"
    assert designation["executive_name"] is None
    assert designation["executive_role"] is None
    assert designation["designated_by"] is None
