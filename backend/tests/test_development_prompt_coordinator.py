from app.services.development_prompt_coordinator import (
    PromptCatalogError,
    plan_development_coordination,
    resolve_prompt_records,
    validate_prompt_catalog,
)


def test_resolve_ci_prompt_prioritizes_high_risk_record():
    records = resolve_prompt_records("Corrigir falha no workflow do GitHub Actions e validar CI")

    assert records[0]["id"] == "PDR-CICD-001"
    assert records[0]["risk"] == "high"


def test_plan_combines_adr_pdr_and_evidence_manifest():
    plan = plan_development_coordination(
        objective="Implementar melhoria de segurança no login JWT",
        dry_run=True,
        correlation_id="corr-test-001",
    )

    assert plan["correlation_id"] == "corr-test-001"
    assert plan["capability"] == "ReqSys ADR + PDR Development Coordinator"
    assert plan["human_approval_required"] is True
    assert any(item["id"] == "PDR-SEC-001" for item in plan["pdrs"])
    assert "aprovação humana" in plan["evidence_manifest"]
    assert plan["roteamento"]


def test_catalog_rejects_duplicate_identifiers():
    catalog = {
        "schema_version": "1.0.0",
        "defaults": {},
        "records": [],
    }
    record = {
        "id": "PDR-DEV-001",
        "version": "1.0.0",
        "status": "active",
        "title": "Teste",
        "domain": "development",
        "task_types": ["incremento"],
        "keywords": ["implementar"],
        "path": "docs/prompts/teste.md",
        "required_adrs": ["ADR-045"],
        "agents": ["Agente"],
        "required_evidence": ["teste"],
        "risk": "low",
    }
    catalog["records"] = [record, dict(record)]

    try:
        validate_prompt_catalog(catalog)
    except PromptCatalogError as exc:
        assert "duplicado" in str(exc)
    else:
        raise AssertionError("Catálogo duplicado deveria ser rejeitado")
