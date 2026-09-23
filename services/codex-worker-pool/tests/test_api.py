from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def load_app(tmp_path: Path, monkeypatch):
    service_root = Path(__file__).resolve().parents[1]
    if str(service_root) not in sys.path:
        sys.path.insert(0, str(service_root))
    token_file = tmp_path / "api-token"
    token_file.write_text("test-token-value\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_WORKER_POOL_DB", str(tmp_path / "pool.db"))
    monkeypatch.setenv("CODEX_WORKER_POOL_API_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("CODEX_WORKER_POOL_HEARTBEAT_TTL_SECONDS", "60")
    monkeypatch.setenv("CODEX_WORKER_POOL_LEASE_SECONDS", "30")
    monkeypatch.setenv("CODEX_WORKER_POOL_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS", "30")
    monkeypatch.setenv("CODEX_WORKER_POOL_EXPECTED_RULES_SHA", "a" * 40)
    sys.modules.pop("app.main", None)
    module = importlib.import_module("app.main")
    return module, TestClient(module.app), {"Authorization": "Bearer test-token-value"}


def test_health_and_auth_fail_closed(tmp_path: Path, monkeypatch) -> None:
    _module, client, headers = load_app(tmp_path, monkeypatch)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["auth_configured"] is True
    assert health.json()["expected_rules_sha_configured"] is True
    assert health.json()["progress_stall_seconds"] == 30

    denied = client.get("/v1/snapshot")
    assert denied.status_code == 401

    allowed = client.get("/v1/snapshot", headers=headers)
    assert allowed.status_code == 200
    assert allowed.json()["progress_stall_seconds"] == 30

    watchdog = client.post(
        "/v1/watchdog/recover",
        headers={**headers, "X-Correlation-Id": "watchdog-empty"},
    )
    assert watchdog.status_code == 200
    assert watchdog.json() == {
        "rerouted": 0,
        "blocked": 0,
        "failed": 0,
        "correlation_id": "watchdog-empty",
    }


def test_api_e2e_builder_validator_replay(tmp_path: Path, monkeypatch) -> None:
    _module, client, headers = load_app(tmp_path, monkeypatch)

    for worker_id, role in (("desktop-builder", "builder"), ("noteri-validator", "validator")):
        response = client.post(
            "/v1/workers",
            headers=headers,
            json={
                "worker_id": worker_id,
                "host": worker_id.split("-")[0],
                "role": role,
                "profile": "NORMAL",
                "capacity_score": 80,
                "controller_version": "0.2.51",
                "rules_sha": "a" * 40,
                "gateway_ok": True,
                "state_validated": True,
                "worktree_root": f"C:/dev/chatgpt-workers/{worker_id}",
                "correlation_id": f"corr-{worker_id}",
            },
        )
        assert response.status_code == 200

    payload = {
        "repository": "ericson-j-santos/reqsys-v2-enterprise-real",
        "issue_number": 1769,
        "request_id": "api-e2e-1769",
        "correlation_id": "api-e2e",
        "priority": 10,
        "base_sha": "1" * 40,
        "max_attempts": 2,
    }
    first = client.post("/v1/tasks", headers=headers, json=payload)
    replay = client.post("/v1/tasks", headers=headers, json=payload)
    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["created"] is True
    assert replay.json()["created"] is False
    task_id = first.json()["task"]["task_id"]
    assert replay.json()["task"]["task_id"] == task_id

    build_claim = client.post(
        "/v1/claims",
        headers=headers,
        json={"worker_id": "desktop-builder", "correlation_id": "build-claim"},
    )
    assert build_claim.status_code == 200
    assert build_claim.json()["claimed"] is True
    build_lease = build_claim.json()["lease"]["lease_token"]

    start = client.post(
        f"/v1/tasks/{task_id}/start",
        headers=headers,
        json={
            "worker_id": "desktop-builder",
            "lease_token": build_lease,
            "correlation_id": "build-start",
        },
    )
    assert start.status_code == 200
    assert start.json()["state"] == "running"

    handoff = client.post(
        f"/v1/tasks/{task_id}/validation",
        headers=headers,
        json={
            "worker_id": "desktop-builder",
            "lease_token": build_lease,
            "correlation_id": "handoff",
            "produced_sha": "b" * 40,
        },
    )
    assert handoff.status_code == 200
    assert handoff.json()["state"] == "validating"

    validator_claim = client.post(
        "/v1/claims",
        headers=headers,
        json={"worker_id": "noteri-validator", "correlation_id": "validator-claim"},
    )
    assert validator_claim.status_code == 200
    validation_lease = validator_claim.json()["lease"]["lease_token"]

    complete = client.post(
        f"/v1/tasks/{task_id}/complete",
        headers=headers,
        json={
            "worker_id": "noteri-validator",
            "lease_token": validation_lease,
            "correlation_id": "complete",
        },
    )
    assert complete.status_code == 200
    assert complete.json()["state"] == "completed"

    independent = client.get(f"/v1/tasks/{task_id}", headers=headers)
    assert independent.status_code == 200
    assert independent.json()["state"] == "completed"
    assert independent.json()["produced_sha"] == "b" * 40
    assert "lease_token" not in independent.json()

    final_replay = client.post("/v1/tasks", headers=headers, json=payload)
    assert final_replay.status_code == 200
    assert final_replay.json()["created"] is False


def test_task_requires_base_sha(tmp_path: Path, monkeypatch) -> None:
    _module, client, headers = load_app(tmp_path, monkeypatch)

    response = client.post(
        "/v1/tasks",
        headers=headers,
        json={
            "repository": "ericson-j-santos/reqsys-v2-enterprise-real",
            "issue_number": 1769,
            "request_id": "missing-base-sha",
            "correlation_id": "missing-base-sha",
        },
    )

    assert response.status_code == 422


def test_repository_lane_and_worker_affinity_api(tmp_path: Path, monkeypatch) -> None:
    _module, client, headers = load_app(tmp_path, monkeypatch)

    worker = client.post(
        "/v1/workers",
        headers=headers,
        json={
            "worker_id": "desktop-builder-repo",
            "host": "desktop",
            "role": "builder",
            "profile": "NORMAL",
            "capacity_score": 80,
            "controller_version": "0.2.51",
            "rules_sha": "a" * 40,
            "gateway_ok": True,
            "state_validated": True,
            "worktree_root": "C:/dev/chatgpt-workers/desktop-builder-repo",
            "correlation_id": "repo-api-worker",
        },
    )
    assert worker.status_code == 200

    configured = client.post(
        "/v1/repositories",
        headers=headers,
        json={
            "repository": "ericson-j-santos/painel-powerbi",
            "enabled": True,
            "max_in_flight": 2,
            "correlation_id": "repo-api-config",
        },
    )
    assert configured.status_code == 200
    assert configured.json()["max_in_flight"] == 2

    affinity = client.put(
        "/v1/workers/desktop-builder-repo/affinities",
        headers=headers,
        json={
            "repositories": ["ericson-j-santos/painel-powerbi"],
            "correlation_id": "repo-api-affinity",
        },
    )
    assert affinity.status_code == 200
    assert affinity.json()["repositories"] == ["ericson-j-santos/painel-powerbi"]

    observed = client.get("/v1/repositories", headers=headers)
    assert observed.status_code == 200
    lane = next(
        item
        for item in observed.json()
        if item["repository"] == "ericson-j-santos/painel-powerbi"
    )
    assert lane["enabled"] is True
    assert lane["max_in_flight"] == 2

    snapshot = client.get("/v1/snapshot", headers=headers)
    assert snapshot.status_code == 200
    worker_view = next(
        item
        for item in snapshot.json()["workers"]
        if item["worker_id"] == "desktop-builder-repo"
    )
    assert worker_view["repository_affinity"] == ["ericson-j-santos/painel-powerbi"]
