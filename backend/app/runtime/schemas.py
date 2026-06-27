from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RuntimeStatus = Literal["healthy", "degraded", "critical"]
IncidentSeverity = Literal["low", "medium", "high", "critical"]
RemediationMode = Literal["dry_run", "execute"]


class RuntimeCheck(BaseModel):
    name: str
    status: RuntimeStatus
    latency_ms: int = Field(ge=0)
    message: str


class WorkflowValidationRequest(BaseModel):
    workflow_name: str
    required_jobs: list[str] = Field(default_factory=list)
    completed_jobs: list[str] = Field(default_factory=list)
    failed_jobs: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)


class WorkflowValidationResult(BaseModel):
    workflow_name: str
    valid: bool
    missing_jobs: list[str]
    failed_jobs: list[str]
    evidence_complete: bool
    stability_score: int = Field(ge=0, le=100)


class Incident(BaseModel):
    id: str
    severity: IncidentSeverity
    title: str
    status: Literal["open", "mitigated"]
    correlation_id: str
    detected_at: datetime
    signals: list[str]


class RemediationRequest(BaseModel):
    incident_id: str | None = None
    target: str
    action: Literal[
        "restart_service", "rerun_workflow", "clear_cache", "rollback_release"
    ]
    mode: RemediationMode = "dry_run"
    max_retries: int = Field(default=2, ge=0, le=5)


class RemediationResult(BaseModel):
    remediation_id: str
    accepted: bool
    mode: RemediationMode
    action: str
    target: str
    attempts: int
    rollback_plan: list[str]
    circuit_breaker_open: bool
    audit_event: str


class TimelineEvent(BaseModel):
    id: str
    event_type: str
    title: str
    correlation_id: str
    created_at: datetime
    payload: dict


class RuntimeDashboard(BaseModel):
    status: RuntimeStatus
    stability_score: int = Field(ge=0, le=100)
    checks: list[RuntimeCheck]
    open_incidents: int
    timeline: list[TimelineEvent]
    governance_events: list[dict]
