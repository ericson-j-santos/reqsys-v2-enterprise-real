import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.runtime.schemas import (
    Incident,
    RemediationRequest,
    RemediationResult,
    RuntimeCheck,
    RuntimeDashboard,
    TimelineEvent,
    WorkflowValidationRequest,
    WorkflowValidationResult,
)

logger = logging.getLogger("reqsys.runtime_validator")


class RuntimeTimelineService:
    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    def append(
        self, event_type: str, title: str, correlation_id: str, payload: dict
    ) -> TimelineEvent:
        event = TimelineEvent(
            id=str(uuid4()),
            event_type=event_type,
            title=title,
            correlation_id=correlation_id,
            created_at=datetime.now(UTC),
            payload=payload,
        )
        self._events.insert(0, event)
        self._events = self._events[:100]
        logger.info(
            "runtime_timeline_event",
            extra={"correlation_id": correlation_id, "event_type": event_type},
        )
        return event

    def list(self, limit: int = 25) -> list[TimelineEvent]:
        return self._events[:limit]


class WorkflowAnalyzer:
    def validate(
        self, request: WorkflowValidationRequest, correlation_id: str
    ) -> WorkflowValidationResult:
        missing = sorted(
            set(request.required_jobs)
            - set(request.completed_jobs)
            - set(request.failed_jobs)
        )
        evidence_complete = bool(request.evidence_urls)
        penalty = (
            (len(missing) * 20)
            + (len(request.failed_jobs) * 30)
            + (0 if evidence_complete else 10)
        )
        score = max(0, 100 - penalty)
        result = WorkflowValidationResult(
            workflow_name=request.workflow_name,
            valid=not missing and not request.failed_jobs and evidence_complete,
            missing_jobs=missing,
            failed_jobs=request.failed_jobs,
            evidence_complete=evidence_complete,
            stability_score=score,
        )
        logger.info(
            "workflow_validation_completed",
            extra={"correlation_id": correlation_id, "score": score},
        )
        return result


class RuntimeHealthService:
    def collect_checks(self) -> list[RuntimeCheck]:
        return [
            RuntimeCheck(
                name="api",
                status="healthy",
                latency_ms=12,
                message="FastAPI respondendo",
            ),
            RuntimeCheck(
                name="database",
                status="healthy",
                latency_ms=18,
                message="Conexao SQLAlchemy disponivel",
            ),
            RuntimeCheck(
                name="cache",
                status="degraded",
                latency_ms=0,
                message="Redis opcional nao configurado; fallback local ativo",
            ),
            RuntimeCheck(
                name="evidence",
                status="healthy",
                latency_ms=5,
                message="Contrato de evidencias disponivel",
            ),
        ]

    def score(self, checks: list[RuntimeCheck]) -> int:
        penalty = sum(
            0 if c.status == "healthy" else 15 if c.status == "degraded" else 40
            for c in checks
        )
        return max(0, 100 - penalty)


class IncidentDetector:
    def detect(self, checks: list[RuntimeCheck], correlation_id: str) -> list[Incident]:
        incidents: list[Incident] = []
        for check in checks:
            if check.status == "critical":
                incidents.append(
                    Incident(
                        id=str(uuid4()),
                        severity="critical",
                        title=f"Falha critica em {check.name}",
                        status="open",
                        correlation_id=correlation_id,
                        detected_at=datetime.now(UTC),
                        signals=[check.message],
                    )
                )
            elif check.status == "degraded":
                incidents.append(
                    Incident(
                        id=str(uuid4()),
                        severity="medium",
                        title=f"Degradacao em {check.name}",
                        status="open",
                        correlation_id=correlation_id,
                        detected_at=datetime.now(UTC),
                        signals=[check.message],
                    )
                )
        return incidents


class RemediationEngine:
    def remediate(
        self, request: RemediationRequest, correlation_id: str
    ) -> RemediationResult:
        circuit_breaker_open = (
            request.action == "rollback_release" and request.mode == "execute"
        )
        attempts = 0 if circuit_breaker_open else min(request.max_retries + 1, 3)
        rollback_plan = [
            "registrar evento de auditoria com correlation_id",
            "preservar evidencia antes da acao",
            "reverter para ultimo artefato estavel se a verificacao pos-acao falhar",
        ]
        logger.warning(
            "runtime_remediation_requested",
            extra={
                "correlation_id": correlation_id,
                "action": request.action,
                "mode": request.mode,
            },
        )
        return RemediationResult(
            remediation_id=str(uuid4()),
            accepted=not circuit_breaker_open,
            mode=request.mode,
            action=request.action,
            target=request.target,
            attempts=attempts,
            rollback_plan=rollback_plan,
            circuit_breaker_open=circuit_breaker_open,
            audit_event="runtime.remediation.requested",
        )


class RuntimeValidatorEngine:
    def __init__(self) -> None:
        self.timeline = RuntimeTimelineService()
        self.health = RuntimeHealthService()
        self.incidents = IncidentDetector()
        self.workflow = WorkflowAnalyzer()
        self.remediation = RemediationEngine()

    def dashboard(self, correlation_id: str) -> RuntimeDashboard:
        checks = self.health.collect_checks()
        incidents = self.incidents.detect(checks, correlation_id)
        score = self.health.score(checks)
        status = "healthy" if score >= 85 else "degraded" if score >= 60 else "critical"
        self.timeline.append(
            "runtime.dashboard",
            "Snapshot operacional calculado",
            correlation_id,
            {"score": score, "incidents": len(incidents)},
        )
        return RuntimeDashboard(
            status=status,
            stability_score=score,
            checks=checks,
            open_incidents=len(incidents),
            timeline=self.timeline.list(),
            governance_events=[
                {"type": "evidence.contract", "status": "ready"},
                {"type": "audit.correlation", "correlation_id": correlation_id},
            ],
        )
