from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.services.development_prompt_coordinator import (
    PromptCatalogError,
    load_prompt_catalog,
    plan_development_coordination,
)
from app.services.prompt_execution_records import (
    get_execution_record,
    serialize_execution_record,
    update_execution_record_status,
    upsert_execution_record,
)

router = APIRouter(prefix="/agents/coordenador/prompts", tags=["Prompt Development Coordinator"])


class PromptCoordinationRequest(BaseModel):
    objective: str = Field(min_length=10, max_length=4000)
    adr_refs: list[str] | None = None
    pdr_refs: list[str] | None = None
    dry_run: bool = True
    persist_execution: bool = True
    branch_name: str = Field(default="", max_length=255)
    commit_sha: str = Field(default="", max_length=80)
    pull_request_url: str = Field(default="", max_length=2000)


class ExecutionStatusRequest(BaseModel):
    status: str
    workflow_run_url: str | None = Field(default=None, max_length=2000)
    artifact_url: str | None = Field(default=None, max_length=2000)
    evidence: list[dict[str, Any] | str] | None = None
    error: str | None = Field(default=None, max_length=4000)


def _public_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": catalog["schema_version"],
        "updated_at": catalog.get("updated_at"),
        "source_adr": catalog.get("source_adr"),
        "defaults": catalog["defaults"],
        "records": [
            {
                "id": record["id"],
                "version": record["version"],
                "status": record["status"],
                "title": record["title"],
                "domain": record["domain"],
                "task_types": record["task_types"],
                "required_adrs": record["required_adrs"],
                "agents": record["agents"],
                "required_evidence": record["required_evidence"],
                "risk": record["risk"],
                "source": record["path"],
            }
            for record in catalog["records"]
        ],
    }


@router.get("/catalog")
def get_prompt_catalog():
    """Retorna o catálogo governado de PDRs sem conteúdo de prompt ou segredos."""
    try:
        catalog = load_prompt_catalog()
    except PromptCatalogError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ok(_public_catalog(catalog))


@router.post("/plan")
def plan_prompt_development(
    payload: PromptCoordinationRequest,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Resolve ADRs/PDRs e opcionalmente persiste o Execution Record idempotente."""
    try:
        plan = plan_development_coordination(
            objective=payload.objective,
            adr_refs=payload.adr_refs,
            pdr_refs=payload.pdr_refs,
            dry_run=payload.dry_run,
            correlation_id=x_correlation_id,
        )
        execution = None
        if payload.persist_execution:
            execution = serialize_execution_record(
                upsert_execution_record(
                    db,
                    plan=plan,
                    status="planned",
                    branch_name=payload.branch_name,
                    commit_sha=payload.commit_sha,
                    pull_request_url=payload.pull_request_url,
                    evidence=plan.get("evidence_manifest", []),
                )
            )
    except PromptCatalogError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({"plan": plan, "execution_record": execution}, plan["correlation_id"])


@router.get("/executions/{correlation_id}")
def get_prompt_execution(correlation_id: str, db: Session = Depends(get_db)):
    item = get_execution_record(db, correlation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Execution Record não encontrado")
    return ok(serialize_execution_record(item), correlation_id)


@router.patch("/executions/{correlation_id}")
def patch_prompt_execution(
    correlation_id: str,
    payload: ExecutionStatusRequest,
    db: Session = Depends(get_db),
):
    try:
        item = update_execution_record_status(
            db,
            correlation_id,
            status=payload.status,
            workflow_run_url=payload.workflow_run_url,
            artifact_url=payload.artifact_url,
            evidence=payload.evidence,
            error=payload.error,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "não encontrado" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return ok(serialize_execution_record(item), correlation_id)
