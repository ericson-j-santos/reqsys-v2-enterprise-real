from datetime import datetime, timedelta, timezone

import pytest

from app.api.parallelism_control import InMemoryParallelismStore, ParallelismPatchRequest
from app.api.parallelism_reconciliation import ParallelismReconciler


def request(stage: int, *, execution: str = "a" * 64):
    return ParallelismPatchRequest(
        stage=stage,
        validation_pending=True,
        correlation_id="corr-reconcile-123",
        execution_sha256=execution,
        actor="governance-owner",
    )


@pytest.mark.asyncio
async def test_healthy_smoke_confirms_pending_validation():
    store = InMemoryParallelismStore()
    state, _ = await store.compare_and_swap("api", 0, request(1))

    async def smoke(target):
        return {"healthy": True, "component": target}

    reconciler = ParallelismReconciler(store, smoke, validation_slo_seconds=30)
    result = await reconciler.reconcile_target("api")

    assert result["action"] == "CONFIRMED"
    assert result["state"]["validation_pending"] is False
    assert result["state"]["version"] == state.version + 1
    assert reconciler.metrics.confirmations == 1


@pytest.mark.asyncio
async def test_unhealthy_smoke_waits_before_slo():
    store = InMemoryParallelismStore()
    await store.compare_and_swap("queue", 0, request(1))

    async def smoke(target):
        return {"healthy": False, "component": target}

    reconciler = ParallelismReconciler(store, smoke, validation_slo_seconds=3600)
    result = await reconciler.reconcile_target("queue")

    assert result["action"] == "WAITING"
    assert (await store.get("queue")).validation_pending is True
    assert reconciler.metrics.rollbacks == 0


@pytest.mark.asyncio
async def test_expired_unhealthy_state_rolls_back():
    store = InMemoryParallelismStore()
    await store.compare_and_swap("worker", 0, request(1))
    store._states["worker"].updated_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    async def smoke(target):
        return {"healthy": False, "component": target}

    reconciler = ParallelismReconciler(store, smoke, validation_slo_seconds=30)
    result = await reconciler.reconcile_target("worker")

    assert result["action"] == "ROLLBACK_EXPIRED"
    assert result["state"]["stage"] == 0
    assert result["state"]["validation_pending"] is False
    assert reconciler.metrics.expired_states == 1
    assert reconciler.metrics.rollbacks == 1


@pytest.mark.asyncio
async def test_orphan_pending_state_rolls_back_without_timestamp():
    store = InMemoryParallelismStore()
    store._states["api"].stage = 1
    store._states["api"].validation_pending = True
    store._states["api"].updated_at = None

    async def smoke(target):
        return {"healthy": True, "component": target}

    reconciler = ParallelismReconciler(store, smoke)
    result = await reconciler.reconcile_target("api")

    assert result["action"] == "ROLLBACK_ORPHAN"
    assert result["state"]["stage"] == 0
    assert reconciler.metrics.orphan_states == 1


@pytest.mark.asyncio
async def test_reconcile_all_publishes_noop_for_stable_targets():
    store = InMemoryParallelismStore()

    async def smoke(target):
        return {"healthy": True, "component": target}

    reconciler = ParallelismReconciler(store, smoke)
    results = await reconciler.reconcile_all()

    assert len(results) == 3
    assert {item["action"] for item in results} == {"NOOP"}
    assert reconciler.metrics.snapshot()["validation_duration_ms_average"] == 0.0
