from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.prompt_development_coordinator import (
    ExecutionStatusRequest,
    PromptCoordinationRequest,
    _public_catalog,
    get_prompt_catalog,
    get_prompt_execution,
    patch_prompt_execution,
    plan_prompt_development,
)
from app.db import Base
from app.models.prompt_execution_record import PromptExecutionRecord
from app.services.development_prompt_coordinator import load_prompt_catalog


def _session():
    engine = create_engine("sqlite:///:memory:")
    assert PromptExecutionRecord.__tablename__ in Base.metadata.tables
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


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


def test_plan_endpoint_persists_and_updates_execution_record():
    db = _session()
    payload = PromptCoordinationRequest(
        objective="Implementar correção de segurança no login JWT",
        dry_run=True,
        branch_name="agent/security-login",
        pull_request_url="https://github.com/org/repo/pull/1",
    )

    response = plan_prompt_development(payload, db=db, x_correlation_id="corr-api-001")
    data = response["data"]
    plan = data["plan"]
    record = data["execution_record"]

    assert response["success"] is True
    assert plan["correlation_id"] == "corr-api-001"
    assert plan["human_approval_required"] is True
    assert record["status"] == "planned"
    assert record["risk"] == "critical"
    assert record["branch_name"] == "agent/security-login"

    updated = patch_prompt_execution(
        "corr-api-001",
        ExecutionStatusRequest(
            status="succeeded",
            workflow_run_url="https://github.com/org/repo/actions/runs/1",
            evidence=["CI verde"],
        ),
        db=db,
    )
    assert updated["data"]["status"] == "succeeded"
    assert updated["data"]["evidence"] == ["CI verde"]

    fetched = get_prompt_execution("corr-api-001", db=db)
    assert fetched["data"]["workflow_run_url"].endswith("/1")
