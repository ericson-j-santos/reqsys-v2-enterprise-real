from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.services.development_prompt_coordinator import (
    PromptCatalogError,
    load_prompt_catalog,
    plan_development_coordination,
)

router = APIRouter(prefix="/agents/coordenador/prompts", tags=["Prompt Development Coordinator"])


class PromptCoordinationRequest(BaseModel):
    objective: str = Field(min_length=10, max_length=4000)
    adr_refs: list[str] | None = None
    pdr_refs: list[str] | None = None
    dry_run: bool = True


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
    x_correlation_id: str | None = Header(default=None),
):
    """Resolve ADRs, PDRs, agentes, risco e evidências para um incremento de código."""
    try:
        plan = plan_development_coordination(
            objective=payload.objective,
            adr_refs=payload.adr_refs,
            pdr_refs=payload.pdr_refs,
            dry_run=payload.dry_run,
            correlation_id=x_correlation_id,
        )
    except PromptCatalogError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ok(plan, plan["correlation_id"])
