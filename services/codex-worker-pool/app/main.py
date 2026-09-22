from __future__ import annotations

import hmac
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.store import ConflictError, NotFoundError, WorkerPoolStore


SERVICE_NAME = "codex-worker-pool"
DB_PATH = Path(os.getenv("CODEX_WORKER_POOL_DB", "./data/codex-worker-pool.db"))
TOKEN_FILE = os.getenv("CODEX_WORKER_POOL_API_TOKEN_FILE", "").strip()
HEARTBEAT_TTL_SECONDS = int(os.getenv("CODEX_WORKER_POOL_HEARTBEAT_TTL_SECONDS", "90"))
LEASE_SECONDS = int(os.getenv("CODEX_WORKER_POOL_LEASE_SECONDS", "120"))
MAX_ATTEMPTS = int(os.getenv("CODEX_WORKER_POOL_MAX_ATTEMPTS", "3"))
EXPECTED_RULES_SHA = os.getenv("CODEX_WORKER_POOL_EXPECTED_RULES_SHA", "").strip().lower() or None

store = WorkerPoolStore(
    DB_PATH,
    heartbeat_ttl_seconds=HEARTBEAT_TTL_SECONDS,
    default_lease_seconds=LEASE_SECONDS,
    default_max_attempts=MAX_ATTEMPTS,
    expected_rules_sha=EXPECTED_RULES_SHA,
)

logger = logging.getLogger(SERVICE_NAME)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(message)s")

app = FastAPI(
    title="ReqSys Codex Worker Pool",
    version="1.1.0",
    description="Fila governada para workers Codex distribuídos com lease, idempotência e validação independente.",
)


def _audit(event: str, correlation_id: str, **fields: Any) -> None:
    payload = {
        "service": SERVICE_NAME,
        "event": event,
        "correlation_id": correlation_id,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _read_api_token() -> str:
    if not TOKEN_FILE:
        return ""
    path = Path(TOKEN_FILE)
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return token


def require_auth(authorization: str | None = Header(default=None)) -> None:
    expected = _read_api_token()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="worker_pool_auth_not_configured",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def correlation(value: str | None) -> str:
    return (value or "").strip() or str(uuid.uuid4())


def public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if key != "lease_token"}


class WorkerRegistration(BaseModel):
    worker_id: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=128)
    role: Literal["builder", "validator"]
    profile: Literal["NORMAL", "ESTUDO"] = "NORMAL"
    capacity_score: int = Field(default=50, ge=0, le=100)
    controller_version: str | None = Field(default=None, max_length=64)
    rules_sha: str | None = Field(default=None, max_length=64)
    gateway_ok: bool
    state_validated: bool
    worktree_root: str | None = Field(default=None, max_length=512)
    correlation_id: str = Field(min_length=1, max_length=128)


class Heartbeat(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=128)
    profile: Literal["NORMAL", "ESTUDO"] | None = None
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    gateway_ok: bool | None = None
    state_validated: bool | None = None


class RepositoryLaneConfig(BaseModel):
    repository: str = Field(min_length=3, max_length=256)
    enabled: bool = True
    max_in_flight: int = Field(default=1, ge=1, le=100)
    correlation_id: str = Field(min_length=1, max_length=128)


class WorkerAffinityUpdate(BaseModel):
    repositories: list[str] = Field(default_factory=list, max_length=100)
    correlation_id: str = Field(min_length=1, max_length=128)


class TaskCreate(BaseModel):
    repository: str = Field(min_length=3, max_length=256)
    issue_number: int = Field(ge=1)
    request_id: str = Field(min_length=1, max_length=256)
    correlation_id: str = Field(min_length=1, max_length=128)
    priority: int = Field(default=100, ge=0, le=10000)
    base_sha: str = Field(min_length=40, max_length=40)
    target_branch: str | None = Field(default=None, max_length=200)
    max_attempts: int | None = Field(default=None, ge=1, le=20)


class ClaimRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)
    lease_seconds: int | None = Field(default=None, ge=1, le=3600)


class LeaseMutation(BaseModel):
    worker_id: str = Field(min_length=1, max_length=128)
    lease_token: str = Field(min_length=16, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)


class RenewLease(LeaseMutation):
    lease_seconds: int | None = Field(default=None, ge=1, le=3600)


class ValidationHandoff(LeaseMutation):
    produced_sha: str = Field(min_length=40, max_length=40)


class Failure(LeaseMutation):
    reason: str = Field(min_length=1, max_length=1000)


class Requeue(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=128)


@app.exception_handler(NotFoundError)
async def not_found_handler(_request, exc: NotFoundError):
    return _error_response(status.HTTP_404_NOT_FOUND, str(exc))


@app.exception_handler(ConflictError)
async def conflict_handler(_request, exc: ConflictError):
    return _error_response(status.HTTP_409_CONFLICT, str(exc))


@app.exception_handler(ValueError)
async def value_error_handler(_request, exc: ValueError):
    return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


def _error_response(code: int, detail: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=code, content={"detail": detail})


@app.get("/health")
def health(response: Response) -> dict[str, Any]:
    auth_configured = bool(_read_api_token())
    rules_sha_configured = bool(EXPECTED_RULES_SHA)
    ready = auth_configured and rules_sha_configured
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "healthy" if ready else "not_ready",
        "service": SERVICE_NAME,
        "auth_configured": auth_configured,
        "expected_rules_sha_configured": rules_sha_configured,
        "db_path_configured": bool(str(DB_PATH)),
    }


@app.get("/v1/workers", dependencies=[Depends(require_auth)])
def workers() -> list[dict[str, Any]]:
    return store.snapshot()["workers"]


@app.post("/v1/workers", dependencies=[Depends(require_auth)])
def register_worker(payload: WorkerRegistration) -> dict[str, Any]:
    worker = store.register_worker(**payload.model_dump())
    _audit("worker.registered", payload.correlation_id, worker_id=payload.worker_id, host=payload.host, role=payload.role)
    return worker


@app.post("/v1/workers/{worker_id}/heartbeat", dependencies=[Depends(require_auth)])
def heartbeat(worker_id: str, payload: Heartbeat) -> dict[str, Any]:
    worker = store.heartbeat_worker(worker_id, **payload.model_dump(exclude_none=True))
    _audit("worker.heartbeat", payload.correlation_id, worker_id=worker_id, profile=worker["profile"])
    return worker


@app.get("/v1/repositories", dependencies=[Depends(require_auth)])
def repositories() -> list[dict[str, Any]]:
    return store.snapshot()["repositories"]


@app.post("/v1/repositories", dependencies=[Depends(require_auth)])
def configure_repository(payload: RepositoryLaneConfig) -> dict[str, Any]:
    configured = store.configure_repository(
        repository=payload.repository,
        enabled=payload.enabled,
        max_in_flight=payload.max_in_flight,
    )
    _audit(
        "repository.configured",
        payload.correlation_id,
        repository=payload.repository,
        enabled=payload.enabled,
        max_in_flight=payload.max_in_flight,
    )
    return configured


@app.put("/v1/workers/{worker_id}/affinities", dependencies=[Depends(require_auth)])
def worker_affinities(worker_id: str, payload: WorkerAffinityUpdate) -> dict[str, Any]:
    repositories = store.replace_worker_affinities(worker_id, payload.repositories)
    _audit(
        "worker.affinity.replaced",
        payload.correlation_id,
        worker_id=worker_id,
        repository_count=len(repositories),
    )
    return {"worker_id": worker_id, "repositories": repositories}


@app.post("/v1/tasks", dependencies=[Depends(require_auth)], status_code=201)
def enqueue_task(payload: TaskCreate, response: Response) -> dict[str, Any]:
    task, created = store.enqueue_task(**payload.model_dump())
    if not created:
        response.status_code = status.HTTP_200_OK
    _audit(
        "task.enqueued" if created else "task.replayed",
        payload.correlation_id,
        task_id=task["task_id"],
        issue_number=payload.issue_number,
        branch=task["branch"],
        created=created,
    )
    return {"created": created, "task": public_task(task)}


@app.get("/v1/tasks/{task_id}", dependencies=[Depends(require_auth)])
def get_task(task_id: str) -> dict[str, Any]:
    return public_task(store.get_task(task_id))


@app.post("/v1/claims", dependencies=[Depends(require_auth)])
def claim(payload: ClaimRequest) -> dict[str, Any]:
    worker = store.get_worker(payload.worker_id)
    task, lease = store.claim_task(
        worker_id=payload.worker_id,
        role=worker["role"],
        correlation_id=payload.correlation_id,
        lease_seconds=payload.lease_seconds,
    )
    if task is None or lease is None:
        _audit("claim.empty", payload.correlation_id, worker_id=payload.worker_id, role=worker["role"])
        return {"claimed": False, "task": None, "lease": None}
    _audit(
        "claim.acquired",
        payload.correlation_id,
        worker_id=payload.worker_id,
        role=worker["role"],
        task_id=task["task_id"],
    )
    return {
        "claimed": True,
        "task": public_task(task),
        "lease": {
            "task_id": lease.task_id,
            "lease_token": lease.lease_token,
            "worker_id": lease.worker_id,
            "role": lease.role,
            "lease_expires_at": lease.lease_expires_at,
        },
    }


@app.post("/v1/tasks/{task_id}/lease/renew", dependencies=[Depends(require_auth)])
def renew(task_id: str, payload: RenewLease) -> dict[str, Any]:
    task = store.renew_lease(task_id=task_id, **payload.model_dump())
    _audit("lease.renewed", payload.correlation_id, worker_id=payload.worker_id, task_id=task_id)
    return public_task(task)


@app.post("/v1/tasks/{task_id}/start", dependencies=[Depends(require_auth)])
def start(task_id: str, payload: LeaseMutation) -> dict[str, Any]:
    task = store.start_task(task_id=task_id, **payload.model_dump())
    _audit("task.started", payload.correlation_id, worker_id=payload.worker_id, task_id=task_id)
    return public_task(task)


@app.post("/v1/tasks/{task_id}/validation", dependencies=[Depends(require_auth)])
def validation(task_id: str, payload: ValidationHandoff) -> dict[str, Any]:
    task = store.submit_for_validation(task_id=task_id, **payload.model_dump())
    _audit(
        "task.validation_requested",
        payload.correlation_id,
        worker_id=payload.worker_id,
        task_id=task_id,
        produced_sha=payload.produced_sha,
    )
    return public_task(task)


@app.post("/v1/tasks/{task_id}/complete", dependencies=[Depends(require_auth)])
def complete(task_id: str, payload: LeaseMutation) -> dict[str, Any]:
    task = store.complete_task(task_id=task_id, **payload.model_dump())
    _audit("task.completed", payload.correlation_id, worker_id=payload.worker_id, task_id=task_id)
    return public_task(task)


@app.post("/v1/tasks/{task_id}/fail", dependencies=[Depends(require_auth)])
def fail(task_id: str, payload: Failure) -> dict[str, Any]:
    task = store.fail_task(task_id=task_id, **payload.model_dump())
    _audit(
        "task.failed_attempt",
        payload.correlation_id,
        worker_id=payload.worker_id,
        task_id=task_id,
        state=task["state"],
    )
    return public_task(task)


@app.post("/v1/tasks/{task_id}/block", dependencies=[Depends(require_auth)])
def block(task_id: str, payload: Failure) -> dict[str, Any]:
    task = store.block_task(task_id=task_id, **payload.model_dump())
    _audit(
        "task.blocked_external",
        payload.correlation_id,
        worker_id=payload.worker_id,
        task_id=task_id,
        reason_code="external_block",
    )
    return public_task(task)


@app.post("/v1/tasks/{task_id}/requeue", dependencies=[Depends(require_auth)])
def requeue(task_id: str, payload: Requeue) -> dict[str, Any]:
    task = store.requeue_blocked(task_id, correlation_id=payload.correlation_id)
    _audit("task.requeued", payload.correlation_id, task_id=task_id)
    return public_task(task)


@app.post("/v1/leases/recover", dependencies=[Depends(require_auth)])
def recover_leases(x_correlation_id: str | None = Header(default=None)) -> dict[str, Any]:
    correlation_id = correlation(x_correlation_id)
    recovered = store.recover_expired_leases()
    _audit("lease.recovery_cycle", correlation_id, recovered=recovered)
    return {"recovered": recovered, "correlation_id": correlation_id}


@app.get("/v1/snapshot", dependencies=[Depends(require_auth)])
def snapshot() -> dict[str, Any]:
    return store.snapshot()


@app.get("/v1/quarantine", dependencies=[Depends(require_auth)])
def quarantine() -> list[dict[str, Any]]:
    return store.list_quarantine()
