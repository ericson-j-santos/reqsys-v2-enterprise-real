from scripts.validate_integration_excel_sql_sharepoint_functional_evidence import (
    digest,
    validate_functional_evidence,
)


SOURCE_SHA = "a" * 40
CORRELATION_ID = "corr-1649"
IDENTIFIER = "123456"


def candidate_evidence():
    return {
        "status": "resolved",
        "candidate_source": "original_excel_workbook",
        "real_source": True,
        "mocked": False,
        "simulated": False,
        "synthetic_fixture_used": False,
        "source_sha": SOURCE_SHA,
        "correlation_id": CORRELATION_ID,
        "selected_identifier_sha256": digest(IDENTIFIER),
    }


def e2e_evidence():
    return {
        "status": "passed",
        "real": True,
        "mocked": False,
        "simulated": False,
        "source_sha": SOURCE_SHA,
        "correlation_id": CORRELATION_ID,
        "sql_validation_mode": "power_platform_gateway",
        "checks": {
            "positive_case": "passed",
            "negative_case": "passed",
            "idempotency": "passed",
            "sql_via_gateway_real_flow": "passed",
        },
        "positive": {"identifier": IDENTIFIER, "independent_read": "passed"},
        "negative": {"independent_read": "passed"},
        "idempotency": {"independent_read": "passed", "same_item_id": True},
        "cleanup": {
            "flow_stopped": True,
            "workbook_restored": True,
            "sharepoint_item_removed": True,
        },
    }


def test_functional_evidence_passa_com_origem_real_e_controles_completos():
    result = validate_functional_evidence(
        candidate_evidence(),
        e2e_evidence(),
        source_sha=SOURCE_SHA,
        correlation_id=CORRELATION_ID,
    )
    assert result["functional_evidence"] is True
    assert result["blockers"] == []


def test_functional_evidence_falha_se_identificador_nao_for_o_mesmo_do_excel():
    e2e = e2e_evidence()
    e2e["positive"]["identifier"] = "999999"
    result = validate_functional_evidence(
        candidate_evidence(), e2e, source_sha=SOURCE_SHA, correlation_id=CORRELATION_ID
    )
    assert result["functional_evidence"] is False
    assert "positive_identifier_not_bound_to_real_candidate" in result["blockers"]


def test_functional_evidence_falha_se_cleanup_nao_for_comprovado():
    e2e = e2e_evidence()
    e2e["cleanup"]["sharepoint_item_removed"] = False
    result = validate_functional_evidence(
        candidate_evidence(), e2e, source_sha=SOURCE_SHA, correlation_id=CORRELATION_ID
    )
    assert result["functional_evidence"] is False
    assert "cleanup_sharepoint_item_not_removed" in result["blockers"]
