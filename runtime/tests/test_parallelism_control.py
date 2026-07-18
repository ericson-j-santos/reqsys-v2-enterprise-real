import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import parallelism_control


@pytest.fixture
def store():
    return parallelism_control.InMemoryParallelismStore()


@pytest.fixture
def client(store):
    app = FastAPI()
    app.dependency_overrides[parallelism_control.get_parallelism_store] = lambda: store
    app.dependency_overrides[parallelism_control.get_control_token] = lambda: "test-secret"

    async def smoke(target):
        return {"healthy": True, "component": target}

    app.dependency_overrides[parallelism_control.get_smoke_check] = lambda: smoke
    app.include_router(parallelism_control.router)
    return TestClient(app)


def payload(stage=1, execution="a" * 64):
    return {
        "stage": stage,
        "validation_pending": True,
        "correlation_id": "corr-12345678",
        "execution_sha256": execution,
        "actor": "governance-owner",
    }


def test_get_returns_initial_state_and_etag(client):
    response = client.get("/api/runtime/parallelism/worker")
    assert response.status_code == 200
    assert response.headers["etag"] == "0"
    assert response.json()["stage"] == 0


def test_patch_requires_service_token(client):
    response = client.patch(
        "/api/runtime/parallelism/worker", headers={"If-Match": "0"}, json=payload()
    )
    assert response.status_code == 401


def test_compare_and_swap_updates_version_and_audit(client, store):
    response = client.patch(
        "/api/runtime/parallelism/worker",
        headers={"If-Match": "0", "Authorization": "Bearer test-secret"},
        json=payload(),
    )
    assert response.status_code == 200
    assert response.headers["etag"] == "1"
    assert response.json()["version"] == 1
    assert response.json()["validation_pending"] is True
    assert len(store.audit_events) == 1
    assert store.audit_events[0].correlation_id == "corr-12345678"


def test_stale_version_is_rejected(client):
    headers = {"If-Match": "0", "Authorization": "Bearer test-secret"}
    assert client.patch("/api/runtime/parallelism/api", headers=headers, json=payload()).status_code == 200
    response = client.patch(
        "/api/runtime/parallelism/api", headers=headers, json=payload(stage=0, execution="b" * 64)
    )
    assert response.status_code == 412
    assert response.json()["detail"]["current_version"] == 1


def test_same_execution_is_idempotent(client, store):
    headers = {"If-Match": "0", "Authorization": "Bearer test-secret"}
    first = client.patch("/api/runtime/parallelism/queue", headers=headers, json=payload())
    second = client.patch(
        "/api/runtime/parallelism/queue",
        headers={"If-Match": "1", "Authorization": "Bearer test-secret"},
        json=payload(),
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["version"] == 1
    assert len(store.audit_events) == 1


def test_stage_delta_above_one_is_blocked(client):
    response = client.patch(
        "/api/runtime/parallelism/worker",
        headers={"If-Match": "0", "Authorization": "Bearer test-secret"},
        json=payload(stage=2),
    )
    assert response.status_code == 409


def test_smoke_is_target_specific(client):
    response = client.get("/api/runtime/parallelism/api/smoke")
    assert response.status_code == 200
    assert response.json() == {"healthy": True, "target": "api", "component": "api"}


def test_prod_style_empty_token_blocks_mutation(store):
    app = FastAPI()
    app.dependency_overrides[parallelism_control.get_parallelism_store] = lambda: store
    app.dependency_overrides[parallelism_control.get_control_token] = lambda: ""
    app.include_router(parallelism_control.router)
    client = TestClient(app)
    response = client.patch(
        "/api/runtime/parallelism/api",
        headers={"If-Match": "0", "Authorization": "Bearer any"},
        json=payload(),
    )
    assert response.status_code == 503
