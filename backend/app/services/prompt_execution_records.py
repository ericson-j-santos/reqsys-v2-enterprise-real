from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prompt_execution_record import PromptExecutionRecord

_ALLOWED_STATUS = {
    "planned",
    "approved",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "rollback_required",
}


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def normalize_status(status: str) -> str:
    resolved = (status or "planned").strip().lower()
    if resolved not in _ALLOWED_STATUS:
        raise ValueError(f"Status inválido: {resolved}. Valores aceitos: {sorted(_ALLOWED_STATUS)}")
    return resolved


def serialize_execution_record(item: PromptExecutionRecord) -> dict[str, Any]:
    return {
        "id": item.id,
        "correlation_id": item.correlation_id,
        "status": item.status,
        "objective": item.objective,
        "risk": item.risk,
        "human_approval_required": item.human_approval_required == "true",
        "branch_name": item.branch_name,
        "commit_sha": item.commit_sha,
        "pull_request_url": item.pull_request_url,
        "workflow_run_url": item.workflow_run_url,
        "artifact_url": item.artifact_url,
        "plan": _json_load(item.plan_json, {}),
        "evidence": _json_load(item.evidence_json, []),
        "error": item.error,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def upsert_execution_record(
    db: Session,
    *,
    plan: dict[str, Any],
    status: str = "planned",
    branch_name: str = "",
    commit_sha: str = "",
    pull_request_url: str = "",
    workflow_run_url: str = "",
    artifact_url: str = "",
    evidence: list[dict[str, Any] | str] | None = None,
    error: str = "",
) -> PromptExecutionRecord:
    correlation_id = str(plan.get("correlation_id") or "").strip()
    objective = str(plan.get("objetivo") or plan.get("objective") or "").strip()
    if not correlation_id:
        raise ValueError("correlation_id é obrigatório no plano")
    if len(objective) < 10:
        raise ValueError("objective deve ter pelo menos 10 caracteres")

    resolved_status = normalize_status(status)
    pdrs = plan.get("pdrs") or []
    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    risk = max((str(item.get("risk", "medium")) for item in pdrs), key=lambda value: risk_order.get(value, 1), default="medium")

    item = db.execute(
        select(PromptExecutionRecord).where(PromptExecutionRecord.correlation_id == correlation_id)
    ).scalar_one_or_none()
    if item is None:
        item = PromptExecutionRecord(correlation_id=correlation_id, objective=objective)
        db.add(item)

    item.status = resolved_status
    item.objective = objective
    item.risk = risk
    item.human_approval_required = "true" if bool(plan.get("human_approval_required")) else "false"
    item.branch_name = branch_name.strip()
    item.commit_sha = commit_sha.strip()
    item.pull_request_url = pull_request_url.strip()
    item.workflow_run_url = workflow_run_url.strip()
    item.artifact_url = artifact_url.strip()
    item.plan_json = _json_dump(plan)
    item.evidence_json = _json_dump(evidence or [])
    item.error = error[:4000]

    db.commit()
    db.refresh(item)
    return item


def get_execution_record(db: Session, correlation_id: str) -> PromptExecutionRecord | None:
    return db.execute(
        select(PromptExecutionRecord).where(PromptExecutionRecord.correlation_id == correlation_id)
    ).scalar_one_or_none()


def update_execution_record_status(
    db: Session,
    correlation_id: str,
    *,
    status: str,
    workflow_run_url: str | None = None,
    artifact_url: str | None = None,
    evidence: list[dict[str, Any] | str] | None = None,
    error: str | None = None,
) -> PromptExecutionRecord:
    item = get_execution_record(db, correlation_id)
    if item is None:
        raise ValueError(f"Execution Record não encontrado: {correlation_id}")

    item.status = normalize_status(status)
    if workflow_run_url is not None:
        item.workflow_run_url = workflow_run_url.strip()
    if artifact_url is not None:
        item.artifact_url = artifact_url.strip()
    if evidence is not None:
        item.evidence_json = _json_dump(evidence)
    if error is not None:
        item.error = error[:4000]

    db.commit()
    db.refresh(item)
    return item
