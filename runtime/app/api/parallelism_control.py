from __future__ import annotations

import asyncio
import hmac
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal, Protocol

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import WatchError

Target = Literal["worker", "queue", "api"]
ALLOWED_TARGETS = {"worker", "queue", "api"}


class ParallelismPatchRequest(BaseModel):
    stage: int = Field(ge=0, le=3)
    validation_pending: bool = True
    correlation_id: str = Field(min_length=8, max_length=128)
    execution_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    actor: str = Field(min_length=1, max_length=128)


class ParallelismState(BaseModel):
    target: Target
    stage: int = 0
    version: int = 0
    validation_pending: bool = False
    last_execution_sha256: str | None = None
    correlation_id: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None


class ParallelismAuditEvent(BaseModel):
    target: Target
    previous_stage: int
    new_stage: int
    previous_version: int
    new_version: int
    correlation_id: str
    execution_sha256: str
    actor: str
    occurred_at: str


class ParallelismStore(Protocol):
    async def get(self, target: Target) -> ParallelismState: ...

    async def compare_and_swap(
        self, target: Target, expected_version: int, request: ParallelismPatchRequest
    ) -> tuple[ParallelismState, ParallelismAuditEvent]: ...


class InMemoryParallelismStore:
    def __init__(self) -> None:
        self._states = {target: ParallelismState(target=target) for target in ALLOWED_TARGETS}
        self._locks = {target: asyncio.Lock() for target in ALLOWED_TARGETS}
        self.audit_events: list[ParallelismAuditEvent] = []

    async def get(self, target: Target) -> ParallelismState:
        return self._states[target].model_copy(deep=True)

    async def compare_and_swap(
        self, target: Target, expected_version: int, request: ParallelismPatchRequest
    ) -> tuple[ParallelismState, ParallelismAuditEvent]:
        async with self._locks[target]:
            current = self._states[target]
            if current.version != expected_version:
                raise VersionConflict(current.version)
            if current.last_execution_sha256 == request.execution_sha256:
                return current.model_copy(deep=True), _audit(current, current, request)
            if abs(request.stage - current.stage) > 1:
                raise ValueError("stage delta must be at most one")
            updated = _updated_state(current, request)
            event = _audit(current, updated, request)
            self._states[target] = updated
            self.audit_events.append(event)
            return updated.model_copy(deep=True), event


class RedisParallelismStore:
    def __init__(self, redis: Redis, prefix: str = "reqsys:runtime:parallelism") -> None:
        self.redis = redis
        self.prefix = prefix

    def _key(self, target: Target) -> str:
        return f"{self.prefix}:state:{target}"

    def _audit_key(self) -> str:
        return f"{self.prefix}:audit"

    async def get(self, target: Target) -> ParallelismState:
        raw = await self.redis.get(self._key(target))
        return ParallelismState.model_validate_json(raw) if raw else ParallelismState(target=target)

    async def compare_and_swap(
        self, target: Target, expected_version: int, request: ParallelismPatchRequest
    ) -> tuple[ParallelismState, ParallelismAuditEvent]:
        key = self._key(target)
        for _ in range(3):
            async with self.redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key)
                    raw = await pipe.get(key)
                    current = ParallelismState.model_validate_json(raw) if raw else ParallelismState(target=target)
                    if current.version != expected_version:
                        raise VersionConflict(current.version)
                    if current.last_execution_sha256 == request.execution_sha256:
                        await pipe.unwatch()
                        return current, _audit(current, current, request)
                    if abs(request.stage - current.stage) > 1:
                        raise ValueError("stage delta must be at most one")
                    updated = _updated_state(current, request)
                    event = _audit(current, updated, request)
                    pipe.multi()
                    pipe.set(key, updated.model_dump_json())
                    pipe.rpush(self._audit_key(), event.model_dump_json())
                    await pipe.execute()
                    return updated, event
                except WatchError:
                    continue
        current = await self.get(target)
        raise VersionConflict(current.version)


class VersionConflict(RuntimeError):
    def __init__(self, current_version: int) -> None:
        super().__init__("parallelism state version conflict")
        self.current_version = current_version


def _updated_state(current: ParallelismState, request: ParallelismPatchRequest) -> ParallelismState:
    return ParallelismState(
        target=current.target,
        stage=request.stage,
        version=current.version + 1,
        validation_pending=request.validation_pending,
        last_execution_sha256=request.execution_sha256,
        correlation_id=request.correlation_id,
        updated_by=request.actor,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def _audit(
    previous: ParallelismState, updated: ParallelismState, request: ParallelismPatchRequest
) -> ParallelismAuditEvent:
    return ParallelismAuditEvent(
        target=previous.target,
        previous_stage=previous.stage,
        new_stage=updated.stage,
        previous_version=previous.version,
        new_version=updated.version,
        correlation_id=request.correlation_id,
        execution_sha256=request.execution_sha256,
        actor=request.actor,
        occurred_at=datetime.now(timezone.utc).isoformat(),
    )


router = APIRouter(prefix="/api/runtime/parallelism", tags=["runtime-parallelism"])


def get_parallelism_store() -> ParallelismStore:  # pragma: no cover
    raise RuntimeError("ParallelismStore não configurado")


def get_control_token() -> str:  # pragma: no cover
    raise RuntimeError("Token de controle não configurado")


def get_smoke_check() -> Callable[[Target], Awaitable[dict[str, Any]]]:  # pragma: no cover
    raise RuntimeError("Smoke check não configurado")


def _authorize(authorization: str | None, expected_token: str) -> None:
    if not expected_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Control token not configured")
    provided = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not hmac.compare_digest(provided, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")


@router.get("/{target}", response_model=ParallelismState)
async def get_state(
    target: Target,
    response: Response,
    store: ParallelismStore = Depends(get_parallelism_store),
) -> ParallelismState:
    state = await store.get(target)
    response.headers["ETag"] = str(state.version)
    return state


@router.patch("/{target}", response_model=ParallelismState)
async def patch_state(
    target: Target,
    request: ParallelismPatchRequest,
    response: Response,
    if_match: str = Header(alias="If-Match"),
    authorization: str | None = Header(default=None),
    store: ParallelismStore = Depends(get_parallelism_store),
    token: str = Depends(get_control_token),
) -> ParallelismState:
    _authorize(authorization, token)
    try:
        expected_version = int(if_match.strip('"'))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="If-Match must be an integer version") from exc
    try:
        state, _ = await store.compare_and_swap(target, expected_version, request)
    except VersionConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"message": "Version conflict", "current_version": exc.current_version},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    response.headers["ETag"] = str(state.version)
    return state


@router.get("/{target}/smoke")
async def smoke(
    target: Target,
    check: Callable[[Target], Awaitable[dict[str, Any]]] = Depends(get_smoke_check),
) -> dict[str, Any]:
    result = await check(target)
    return {"healthy": bool(result.get("healthy")), "target": target, **result}
