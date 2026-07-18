from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.parallelism_control import (
    ALLOWED_TARGETS,
    ParallelismPatchRequest,
    ParallelismState,
    ParallelismStore,
    Target,
    VersionConflict,
)


@dataclass(slots=True)
class ReconciliationMetrics:
    confirmations: int = 0
    expired_states: int = 0
    orphan_states: int = 0
    rollbacks: int = 0
    cas_conflicts: int = 0
    validation_duration_ms_total: int = 0
    validation_duration_samples: int = 0

    def snapshot(self) -> dict[str, int | float]:
        average = (
            self.validation_duration_ms_total / self.validation_duration_samples
            if self.validation_duration_samples
            else 0.0
        )
        return {
            "confirmations": self.confirmations,
            "expired_states": self.expired_states,
            "orphan_states": self.orphan_states,
            "rollbacks": self.rollbacks,
            "cas_conflicts": self.cas_conflicts,
            "validation_duration_ms_average": round(average, 2),
        }


class ParallelismReconciler:
    def __init__(
        self,
        store: ParallelismStore,
        smoke_check: Callable[[Target], Awaitable[dict[str, Any]]],
        *,
        validation_slo_seconds: int = 300,
        metrics: ReconciliationMetrics | None = None,
    ) -> None:
        self.store = store
        self.smoke_check = smoke_check
        self.validation_slo_seconds = validation_slo_seconds
        self.metrics = metrics or ReconciliationMetrics()

    def _age_seconds(self, state: ParallelismState, now: datetime) -> float | None:
        if not state.updated_at:
            return None
        try:
            updated = datetime.fromisoformat(state.updated_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        return max(0.0, (now - updated).total_seconds())

    def _execution_id(self, target: Target, action: str, version: int) -> str:
        raw = f"reconciler:{target}:{action}:{version}".encode()
        return hashlib.sha256(raw).hexdigest()

    async def _transition(
        self,
        state: ParallelismState,
        *,
        stage: int,
        pending: bool,
        action: str,
    ) -> ParallelismState:
        request = ParallelismPatchRequest(
            stage=stage,
            validation_pending=pending,
            correlation_id=f"reconcile-{state.target}-{state.version}",
            execution_sha256=self._execution_id(state.target, action, state.version),
            actor="runtime-reconciler",
        )
        try:
            updated, _ = await self.store.compare_and_swap(state.target, state.version, request)
            return updated
        except VersionConflict:
            self.metrics.cas_conflicts += 1
            raise

    async def reconcile_target(self, target: Target, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        state = await self.store.get(target)
        if not state.validation_pending:
            return {"target": target, "action": "NOOP", "state": state.model_dump()}

        age = self._age_seconds(state, now)
        if age is None:
            self.metrics.orphan_states += 1
            rollback_stage = max(0, state.stage - 1)
            updated = await self._transition(state, stage=rollback_stage, pending=False, action="orphan-rollback")
            self.metrics.rollbacks += 1
            return {"target": target, "action": "ROLLBACK_ORPHAN", "state": updated.model_dump()}

        smoke = await self.smoke_check(target)
        if bool(smoke.get("healthy")):
            updated = await self._transition(state, stage=state.stage, pending=False, action="confirm")
            self.metrics.confirmations += 1
            self.metrics.validation_duration_ms_total += int(age * 1000)
            self.metrics.validation_duration_samples += 1
            return {"target": target, "action": "CONFIRMED", "state": updated.model_dump(), "smoke": smoke}

        if age < self.validation_slo_seconds:
            return {"target": target, "action": "WAITING", "age_seconds": age, "smoke": smoke}

        self.metrics.expired_states += 1
        rollback_stage = max(0, state.stage - 1)
        updated = await self._transition(state, stage=rollback_stage, pending=False, action="expired-rollback")
        self.metrics.rollbacks += 1
        return {"target": target, "action": "ROLLBACK_EXPIRED", "state": updated.model_dump(), "smoke": smoke}

    async def reconcile_all(self) -> list[dict[str, Any]]:
        results = []
        for target in sorted(ALLOWED_TARGETS):
            try:
                results.append(await self.reconcile_target(target))
            except VersionConflict:
                results.append({"target": target, "action": "CAS_CONFLICT"})
        return results


router = APIRouter(
    prefix="/api/runtime/parallelism/reconciliation",
    tags=["runtime-parallelism-reconciliation"],
)


def get_reconciler() -> ParallelismReconciler:  # pragma: no cover
    raise RuntimeError("ParallelismReconciler não configurado")


@router.post("/confirm/{target}")
async def confirm_target(target: Target, reconciler: ParallelismReconciler = Depends(get_reconciler)) -> dict[str, Any]:
    result = await reconciler.reconcile_target(target)
    if result["action"] == "WAITING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result)
    return result


@router.post("/run")
async def reconcile(reconciler: ParallelismReconciler = Depends(get_reconciler)) -> dict[str, Any]:
    return {"results": await reconciler.reconcile_all(), "metrics": reconciler.metrics.snapshot()}


@router.get("/metrics")
async def metrics(reconciler: ParallelismReconciler = Depends(get_reconciler)) -> dict[str, int | float]:
    return reconciler.metrics.snapshot()
