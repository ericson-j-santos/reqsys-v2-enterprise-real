from uuid import uuid4

from fastapi import APIRouter, Header

from app.core.envelope import ok
from app.runtime.engine import RuntimeValidatorEngine
from app.runtime.schemas import RemediationRequest, WorkflowValidationRequest

router = APIRouter(prefix="/api/runtime-validator", tags=["Runtime Validator"])
ENGINE = RuntimeValidatorEngine()


def _cid(x_correlation_id: str | None, x_request_id: str | None) -> str:
    return x_correlation_id or x_request_id or str(uuid4())


@router.get("/health")
def runtime_health(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    correlation_id = _cid(x_correlation_id, x_request_id)
    checks = ENGINE.health.collect_checks()
    ENGINE.timeline.append(
        "runtime.health",
        "Health check executado",
        correlation_id,
        {"checks": len(checks)},
    )
    return ok(
        {
            "checks": [c.model_dump() for c in checks],
            "stability_score": ENGINE.health.score(checks),
        },
        correlation_id,
    )


@router.post("/workflows/validate")
def validate_workflow(
    payload: WorkflowValidationRequest,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    correlation_id = _cid(x_correlation_id, x_request_id)
    result = ENGINE.workflow.validate(payload, correlation_id)
    ENGINE.timeline.append(
        "workflow.validation", "Workflow validado", correlation_id, result.model_dump()
    )
    return ok(result.model_dump(), correlation_id)


@router.get("/incidents")
def incidents(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    correlation_id = _cid(x_correlation_id, x_request_id)
    data = [
        i.model_dump()
        for i in ENGINE.incidents.detect(ENGINE.health.collect_checks(), correlation_id)
    ]
    return ok({"items": data, "total": len(data)}, correlation_id)


@router.post("/remediations")
def remediate(
    payload: RemediationRequest,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    correlation_id = _cid(x_correlation_id, x_request_id)
    result = ENGINE.remediation.remediate(payload, correlation_id)
    ENGINE.timeline.append(
        "runtime.remediation",
        "Remediacao solicitada",
        correlation_id,
        result.model_dump(),
    )
    return ok(result.model_dump(), correlation_id)


@router.get("/timeline")
def timeline():
    return ok({"items": [e.model_dump() for e in ENGINE.timeline.list()]})


@router.get("/dashboard")
def dashboard(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    correlation_id = _cid(x_correlation_id, x_request_id)
    return ok(ENGINE.dashboard(correlation_id).model_dump(), correlation_id)
