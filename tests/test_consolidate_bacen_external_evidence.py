from __future__ import annotations

from scripts.consolidate_bacen_external_evidence import consolidate


def _mfa(accepted: bool = True, integrity_valid: bool = True) -> dict:
    return {
        "structural_checks_passed": True,
        "mfa_evidenced": accepted,
        "ingestion": {
            "accepted": accepted,
            "expected_sha256_match": integrity_valid,
            "raw_evidence_persisted": False,
        },
        "human_review_required": not accepted,
    }


def _dpa(accepted: bool = True, integrity_valid: bool = True) -> dict:
    return {
        "result": "valid" if accepted else "invalid",
        "summary": {"validated_records": 2 if accepted else 0},
        "ingestion": {
            "accepted": accepted,
            "expected_sha256_match": integrity_valid,
            "raw_evidence_persisted": False,
        },
        "human_review_required": not accepted,
    }


def test_consolidation_ready_requires_human_review() -> None:
    report = consolidate(
        _mfa(),
        _dpa(),
        mfa_source_ref="run:100",
        dpa_source_ref="run:200",
    )

    assert report["decision"] == "evidence_ready_for_human_review"
    assert report["summary"]["controls_ready"] == 2
    assert report["regulatory_status_change_allowed"] is False
    assert report["automatic_implementation_claim_allowed"] is False
    assert report["human_approval_required"] is True
    assert report["production_touched"] is False


def test_consolidation_blocks_when_one_control_is_not_ready() -> None:
    report = consolidate(
        _mfa(accepted=False),
        _dpa(),
        mfa_source_ref="run:101",
        dpa_source_ref="run:201",
    )

    assert report["decision"] == "blocked"
    assert report["summary"] == {
        "controls_checked": 2,
        "controls_ready": 1,
        "controls_blocked": 1,
        "all_external_evidence_ready": False,
    }
    assert report["controls"]["BACEN-02"]["evidence_ready"] is False
    assert report["controls"]["BACEN-05"]["evidence_ready"] is True


def test_consolidation_reuses_upstream_integrity_without_sensitive_hashing() -> None:
    mfa = _mfa()
    mfa["private_reference"] = "vault://secret/mfa"
    dpa = _dpa()
    dpa["private_reference"] = "vault://secret/dpa"

    report = consolidate(
        mfa,
        dpa,
        mfa_source_ref="run:102",
        dpa_source_ref="run:202",
    )

    serialized = str(report)
    assert "vault://secret/mfa" not in serialized
    assert "vault://secret/dpa" not in serialized
    assert "normalized_report_sha256" not in serialized
    assert report["controls"]["BACEN-02"]["source_integrity_validated_upstream"] is True
    assert report["controls"]["BACEN-05"]["integrity_validation_mode"] == "upstream_governed_ingestion"
    assert report["raw_external_evidence_persisted"] is False


def test_consolidation_blocks_when_upstream_integrity_is_not_validated() -> None:
    report = consolidate(
        _mfa(integrity_valid=False),
        _dpa(),
        mfa_source_ref="run:103",
        dpa_source_ref="run:203",
    )

    assert report["decision"] == "blocked"
    assert report["controls"]["BACEN-02"]["source_integrity_validated_upstream"] is False
    assert report["controls"]["BACEN-02"]["evidence_ready"] is False
