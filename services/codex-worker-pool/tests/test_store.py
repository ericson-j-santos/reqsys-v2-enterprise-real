from __future__ import annotations

import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.store import ConflictError, WorkerPoolStore, build_idempotency_key


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 18, 18, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


@pytest.fixture()
def clock() -> MutableClock:
    return MutableClock()


@pytest.fixture()
def store(tmp_path: Path, clock: MutableClock) -> WorkerPoolStore:
    return WorkerPoolStore(
        tmp_path / "worker-pool.db",
        clock=clock,
        heartbeat_ttl_seconds=60,
        default_lease_seconds=10,
        default_max_attempts=2,
        expected_rules_sha="a" * 40,
    )


def register_ready(store: WorkerPoolStore, worker_id: str, role: str, *, profile: str = "NORMAL") -> None:
    store.register_worker(
        worker_id=worker_id,
        host=f"host-{worker_id}",
        role=role,
        profile=profile,
        correlation_id=f"corr-{worker_id}",
        controller_version="0.2.51",
        rules_sha="a" * 40,
        gateway_ok=True,
        state_validated=True,
        worktree_root=f"C:/dev/chatgpt-workers/{worker_id}",
    )


def enqueue(
    store: WorkerPoolStore,
    request_id: str = "req-1",
    *,
    max_attempts: int = 2,
    repository: str = "ericson-j-santos/reqsys-v2-enterprise-real",
    issue_number: int = 1769,
    priority: int = 10,
):
    return store.enqueue_task(
        repository=repository,
        issue_number=issue_number,
        request_id=request_id,
        correlation_id=f"corr-{request_id}",
        priority=priority,
        base_sha="1" * 40,
        max_attempts=max_attempts,
    )


def test_init_closes_connection(tmp_path: Path, monkeypatch) -> None:
    class InitConnection:
        def __init__(self) -> None:
            self.closed = False
            self.script_executed = False

        def executescript(self, _script: str) -> None:
            self.script_executed = True

        def close(self) -> None:
            self.closed = True

    connection = InitConnection()
    monkeypatch.setattr(WorkerPoolStore, "_db", lambda _self: connection)

    WorkerPoolStore(tmp_path / "init-close.db")

    assert connection.script_executed is True
    assert connection.closed is True


def test_enqueue_is_idempotent(store: WorkerPoolStore) -> None:
    first, created_first = enqueue(store)
    second, created_second = enqueue(store)

    assert created_first is True
    assert created_second is False
    assert first["task_id"] == second["task_id"]
    assert first["idempotency_key"] == build_idempotency_key(
        "ericson-j-santos/reqsys-v2-enterprise-real", 1769, "req-1"
    )


def test_concurrent_claim_assigns_exactly_once(store: WorkerPoolStore) -> None:
    register_ready(store, "builder-a", "builder")
    register_ready(store, "builder-b", "builder")
    task, _ = enqueue(store)
    barrier = threading.Barrier(2)
    results: list[tuple[str, str | None]] = []
    errors: list[Exception] = []

    def claim(worker: str) -> None:
        try:
            barrier.wait(timeout=3)
            claimed, _lease = store.claim_task(
                worker_id=worker,
                role="builder",
                correlation_id=f"claim-{worker}",
            )
            results.append((worker, claimed["task_id"] if claimed else None))
        except Exception as exc:  # pragma: no cover - diagnostic safety
            errors.append(exc)

    threads = [
        threading.Thread(target=claim, args=("builder-a",)),
        threading.Thread(target=claim, args=("builder-b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert errors == []
    assert sum(task_id == task["task_id"] for _worker, task_id in results) == 1
    assert sum(task_id is None for _worker, task_id in results) == 1


def test_expired_lease_is_recovered_by_another_builder(
    store: WorkerPoolStore, clock: MutableClock
) -> None:
    register_ready(store, "builder-a", "builder")
    register_ready(store, "builder-b", "builder")
    task, _ = enqueue(store)

    claimed, lease = store.claim_task(
        worker_id="builder-a", role="builder", correlation_id="claim-a"
    )
    assert claimed and lease
    store.start_task(
        task_id=task["task_id"],
        worker_id="builder-a",
        lease_token=lease.lease_token,
        correlation_id="start-a",
    )

    clock.advance(11)
    store.heartbeat_worker("builder-b", correlation_id="hb-b")
    recovered = store.recover_expired_leases()
    assert recovered == 1
    assert store.get_task(task["task_id"])["state"] == "queued"

    claimed_again, lease_again = store.claim_task(
        worker_id="builder-b", role="builder", correlation_id="claim-b"
    )
    assert claimed_again and lease_again
    assert claimed_again["task_id"] == task["task_id"]
    assert claimed_again["attempt_count"] == 2


def test_permanent_failure_goes_to_quarantine(store: WorkerPoolStore) -> None:
    register_ready(store, "builder-a", "builder")
    task, _ = enqueue(store, max_attempts=1)
    claimed, lease = store.claim_task(
        worker_id="builder-a", role="builder", correlation_id="claim"
    )
    assert claimed and lease

    failed = store.fail_task(
        task_id=task["task_id"],
        worker_id="builder-a",
        lease_token=lease.lease_token,
        correlation_id="failed",
        reason="known_permanent_failure",
    )

    assert failed["state"] == "failed"
    dlq = store.list_quarantine()
    assert len(dlq) == 1
    assert dlq[0]["task_id"] == task["task_id"]
    assert dlq[0]["reason"] == "known_permanent_failure"


def test_builder_validator_handoff_uses_exact_sha_and_separate_worker(
    store: WorkerPoolStore,
) -> None:
    register_ready(store, "builder-a", "builder")
    register_ready(store, "validator-a", "validator")
    task, _ = enqueue(store)

    claimed, builder_lease = store.claim_task(
        worker_id="builder-a", role="builder", correlation_id="claim-builder"
    )
    assert claimed and builder_lease
    store.start_task(
        task_id=task["task_id"],
        worker_id="builder-a",
        lease_token=builder_lease.lease_token,
        correlation_id="start-builder",
    )
    produced_sha = "b" * 40
    waiting = store.submit_for_validation(
        task_id=task["task_id"],
        worker_id="builder-a",
        lease_token=builder_lease.lease_token,
        produced_sha=produced_sha,
        correlation_id="handoff",
    )
    assert waiting["state"] == "validating"
    assert waiting["produced_sha"] == produced_sha
    assert waiting["leased_by"] is None

    validating, validator_lease = store.claim_task(
        worker_id="validator-a", role="validator", correlation_id="claim-validator"
    )
    assert validating and validator_lease
    assert validating["produced_sha"] == produced_sha
    completed = store.complete_task(
        task_id=task["task_id"],
        worker_id="validator-a",
        lease_token=validator_lease.lease_token,
        correlation_id="complete",
    )
    assert completed["state"] == "completed"
    assert completed["builder_worker_id"] == "builder-a"
    assert completed["validator_worker_id"] == "validator-a"


def test_role_and_profile_fail_closed(store: WorkerPoolStore) -> None:
    register_ready(store, "builder-study", "builder", profile="ESTUDO")
    register_ready(store, "validator-a", "validator")
    enqueue(store)

    with pytest.raises(ConflictError, match="profile ESTUDO"):
        store.claim_task(
            worker_id="builder-study", role="builder", correlation_id="claim-study"
        )

    with pytest.raises(ConflictError, match="não possui role builder"):
        store.claim_task(
            worker_id="validator-a", role="builder", correlation_id="bad-role"
        )


def test_blocked_external_releases_worker_and_can_requeue(store: WorkerPoolStore) -> None:
    register_ready(store, "builder-a", "builder")
    task, _ = enqueue(store)
    claimed, lease = store.claim_task(
        worker_id="builder-a", role="builder", correlation_id="claim"
    )
    assert claimed and lease

    blocked = store.block_task(
        task_id=task["task_id"],
        worker_id="builder-a",
        lease_token=lease.lease_token,
        correlation_id="blocked",
        reason="BLOCKED_EXTERNAL:MOVIMENTO_EMAIL_SOURCE_DSN",
    )
    assert blocked["state"] == "blocked"
    assert blocked["leased_by"] is None

    requeued = store.requeue_blocked(task["task_id"], correlation_id="unblocked")
    assert requeued["state"] == "queued"


def test_snapshot_distinguishes_idle_offline_and_estudo(
    store: WorkerPoolStore, clock: MutableClock
) -> None:
    register_ready(store, "builder-idle", "builder")
    register_ready(store, "validator-study", "validator", profile="ESTUDO")
    clock.advance(61)
    register_ready(store, "builder-online", "builder")

    snapshot = store.snapshot()
    workers = {item["worker_id"]: item for item in snapshot["workers"]}

    assert workers["builder-idle"]["online"] is False
    assert workers["builder-idle"]["why_idle"] == "offline_or_stale"
    assert workers["validator-study"]["online"] is False
    assert workers["validator-study"]["why_idle"] == "offline_or_stale"
    assert workers["builder-online"]["online"] is True
    assert workers["builder-online"]["why_idle"] == "no_queued_work"


def test_wrong_lease_token_cannot_mutate_task(store: WorkerPoolStore) -> None:
    register_ready(store, "builder-a", "builder")
    task, _ = enqueue(store)
    claimed, lease = store.claim_task(
        worker_id="builder-a", role="builder", correlation_id="claim"
    )
    assert claimed and lease

    with pytest.raises(ConflictError, match="lease inválido"):
        store.start_task(
            task_id=task["task_id"],
            worker_id="builder-a",
            lease_token="wrong",
            correlation_id="tamper",
        )

    observed = store.get_task(task["task_id"])
    assert observed["state"] == "leased"


def test_e2e_replay_readback_and_independent_validation(store: WorkerPoolStore) -> None:
    register_ready(store, "desktop-builder", "builder")
    register_ready(store, "noteri-validator", "validator")

    task, created = enqueue(store, request_id="e2e-1769")
    replay, replay_created = enqueue(store, request_id="e2e-1769")
    assert created is True and replay_created is False
    assert replay["task_id"] == task["task_id"]

    building, build_lease = store.claim_task(
        worker_id="desktop-builder", role="builder", correlation_id="e2e-build-claim"
    )
    assert building and build_lease
    store.start_task(
        task_id=task["task_id"],
        worker_id="desktop-builder",
        lease_token=build_lease.lease_token,
        correlation_id="e2e-build-start",
    )
    store.submit_for_validation(
        task_id=task["task_id"],
        worker_id="desktop-builder",
        lease_token=build_lease.lease_token,
        produced_sha="c" * 40,
        correlation_id="e2e-handoff",
    )

    validating, validation_lease = store.claim_task(
        worker_id="noteri-validator",
        role="validator",
        correlation_id="e2e-validator-claim",
    )
    assert validating and validation_lease
    store.complete_task(
        task_id=task["task_id"],
        worker_id="noteri-validator",
        lease_token=validation_lease.lease_token,
        correlation_id="e2e-complete",
    )

    independent_read = store.get_task(task["task_id"])
    assert independent_read["state"] == "completed"
    assert independent_read["produced_sha"] == "c" * 40
    assert independent_read["builder_worker_id"] == "desktop-builder"
    assert independent_read["validator_worker_id"] == "noteri-validator"

    final_replay, final_replay_created = enqueue(store, request_id="e2e-1769")
    assert final_replay_created is False
    assert final_replay["task_id"] == task["task_id"]


def test_rules_sha_mismatch_fails_closed(store: WorkerPoolStore) -> None:
    store.register_worker(
        worker_id="builder-stale-rules",
        host="host-builder-stale-rules",
        role="builder",
        profile="NORMAL",
        correlation_id="corr-stale-rules",
        controller_version="0.2.51",
        rules_sha="b" * 40,
        gateway_ok=True,
        state_validated=True,
        worktree_root="C:/dev/chatgpt-workers/builder-stale-rules",
    )
    enqueue(store, request_id="rules-sha-negative")

    with pytest.raises(ConflictError, match="rules_sha divergente"):
        store.claim_task(
            worker_id="builder-stale-rules",
            role="builder",
            correlation_id="claim-stale-rules",
        )


def test_snapshot_redacts_sensitive_values_and_hides_lease_token(
    store: WorkerPoolStore,
) -> None:
    register_ready(store, "builder-observability", "builder")
    task, _ = enqueue(store, request_id="snapshot-negative-1771")
    claimed, lease = store.claim_task(
        worker_id="builder-observability",
        role="builder",
        correlation_id="snapshot-negative-claim",
    )
    assert claimed and lease

    raw_marker = "NEGATIVE_SECRET_MARKER_1771"
    blocked = store.block_task(
        task_id=task["task_id"],
        worker_id="builder-observability",
        lease_token=lease.lease_token,
        correlation_id="snapshot-negative-block",
        reason=f"api_key={raw_marker}",
    )
    assert blocked["state"] == "blocked"

    snapshot_text = repr(store.snapshot())

    assert lease.lease_token not in snapshot_text
    assert "lease_token" not in snapshot_text
    assert raw_marker not in snapshot_text
    assert "[REDACTED]" in snapshot_text


def test_repository_fair_scheduler_rotates_between_repositories(
    store: WorkerPoolStore,
) -> None:
    repo_a = "ericson-j-santos/repo-a"
    repo_b = "ericson-j-santos/repo-b"
    for worker_id in ("builder-a", "builder-b", "builder-c", "builder-d"):
        register_ready(store, worker_id, "builder")

    store.configure_repository(repository=repo_a, max_in_flight=2)
    store.configure_repository(repository=repo_b, max_in_flight=2)
    first_a, _ = enqueue(store, "fair-a-1", repository=repo_a, issue_number=1)
    second_a, _ = enqueue(store, "fair-a-2", repository=repo_a, issue_number=2)
    first_b, _ = enqueue(store, "fair-b-1", repository=repo_b, issue_number=1)
    second_b, _ = enqueue(store, "fair-b-2", repository=repo_b, issue_number=2)

    observed = []
    for worker_id in ("builder-a", "builder-b", "builder-c", "builder-d"):
        claimed, lease = store.claim_task(
            worker_id=worker_id,
            role="builder",
            correlation_id=f"fair-claim-{worker_id}",
        )
        assert claimed and lease
        observed.append(claimed["task_id"])

    assert observed == [
        first_a["task_id"],
        first_b["task_id"],
        second_a["task_id"],
        second_b["task_id"],
    ]


def test_repository_max_in_flight_prevents_second_active_task(
    store: WorkerPoolStore,
) -> None:
    repository = "ericson-j-santos/limited-repo"
    register_ready(store, "builder-a", "builder")
    register_ready(store, "builder-b", "builder")
    store.configure_repository(repository=repository, max_in_flight=1)
    enqueue(store, "limited-1", repository=repository, issue_number=1)
    enqueue(store, "limited-2", repository=repository, issue_number=2)

    first, first_lease = store.claim_task(
        worker_id="builder-a", role="builder", correlation_id="limited-first"
    )
    assert first and first_lease

    second, second_lease = store.claim_task(
        worker_id="builder-b", role="builder", correlation_id="limited-second"
    )
    assert second is None
    assert second_lease is None


def test_worker_repository_affinity_filters_claims(store: WorkerPoolStore) -> None:
    repo_a = "ericson-j-santos/affinity-a"
    repo_b = "ericson-j-santos/affinity-b"
    register_ready(store, "builder-affinity", "builder")
    enqueue(store, "affinity-a", repository=repo_a, issue_number=1)
    expected, _ = enqueue(store, "affinity-b", repository=repo_b, issue_number=1)
    store.replace_worker_affinities("builder-affinity", [repo_b])

    claimed, lease = store.claim_task(
        worker_id="builder-affinity",
        role="builder",
        correlation_id="affinity-claim",
    )

    assert claimed and lease
    assert claimed["task_id"] == expected["task_id"]
    assert claimed["repository"] == repo_b


def test_worker_without_affinity_remains_shared_pool_compatible(
    store: WorkerPoolStore,
) -> None:
    repository = "ericson-j-santos/shared-pool"
    register_ready(store, "builder-shared", "builder")
    expected, _ = enqueue(store, "shared-1", repository=repository, issue_number=1)

    claimed, lease = store.claim_task(
        worker_id="builder-shared",
        role="builder",
        correlation_id="shared-claim",
    )

    assert claimed and lease
    assert claimed["task_id"] == expected["task_id"]


def test_disabled_repository_lane_does_not_start_new_work(
    store: WorkerPoolStore,
) -> None:
    repository = "ericson-j-santos/paused-repo"
    register_ready(store, "builder-paused", "builder")
    enqueue(store, "paused-1", repository=repository, issue_number=1)
    store.configure_repository(repository=repository, enabled=False, max_in_flight=1)

    claimed, lease = store.claim_task(
        worker_id="builder-paused",
        role="builder",
        correlation_id="paused-claim",
    )

    assert claimed is None
    assert lease is None


def test_snapshot_exposes_repository_lanes_and_worker_affinity(
    store: WorkerPoolStore,
) -> None:
    repository = "ericson-j-santos/observable-repo"
    register_ready(store, "builder-observable", "builder")
    store.configure_repository(repository=repository, max_in_flight=3)
    store.replace_worker_affinities("builder-observable", [repository])
    enqueue(store, "observable-1", repository=repository, issue_number=1)

    snapshot = store.snapshot()

    lane = next(item for item in snapshot["repositories"] if item["repository"] == repository)
    worker = next(item for item in snapshot["workers"] if item["worker_id"] == "builder-observable")
    assert snapshot["schema_version"] == "1.1.0"
    assert lane["enabled"] is True
    assert lane["max_in_flight"] == 3
    assert lane["queued"] == 1
    assert worker["repository_affinity"] == [repository]
