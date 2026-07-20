from app.api.prompt_development_coordinator import (
    PromptCoordinationRequest,
    _public_catalog,
    get_prompt_catalog,
    plan_prompt_development,
)
from app.services.development_prompt_coordinator import load_prompt_catalog


def test_public_catalog_omits_keywords_and_keeps_governance_contract():
    public = _public_catalog(load_prompt_catalog())

    assert public["source_adr"] == "ADR-045"
    assert public["records"]
    assert "keywords" not in public["records"][0]
    assert public["records"][0]["required_adrs"]
    assert public["records"][0]["required_evidence"]


def test_catalog_endpoint_returns_envelope():
    response = get_prompt_catalog()

    assert response["success"] is True
    assert response["data"]["schema_version"] == "1.0.0"
    assert len(response["data"]["records"]) >= 4


def test_plan_endpoint_preserves_correlation_and_requires_approval_for_security():
    payload = PromptCoordinationRequest(
        objective="Implementar correção de segurança no login JWT",
        dry_run=True,
    )

    response = plan_prompt_development(payload, x_correlation_id="corr-api-001")
    plan = response["data"]

    assert response["success"] is True
    assert plan["correlation_id"] == "corr-api-001"
    assert plan["capability"] == "ReqSys ADR + PDR Development Coordinator"
    assert plan["human_approval_required"] is True
    assert any(record["id"] == "PDR-SEC-001" for record in plan["pdrs"])
    assert plan["evidence_manifest"]
