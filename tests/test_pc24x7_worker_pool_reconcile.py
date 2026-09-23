import json
from pathlib import Path

import pytest

from scripts import pc24x7_worker_pool_reconcile as reconcile


def _container(source: str, *, running: bool = False, canonical_port: bool = False) -> dict:
    bindings = []
    if canonical_port:
        bindings = [{"HostIp": reconcile.HOST_IP, "HostPort": reconcile.HOST_PORT}]
    return {
        "Config": {"Labels": {"com.docker.compose.service": reconcile.SERVICE}},
        "State": {"Running": running},
        "NetworkSettings": {"Ports": {reconcile.CONTAINER_PORT: bindings}},
        "Mounts": [
            {
                "Type": "bind",
                "Source": source,
                "Destination": reconcile.TOKEN_DESTINATION,
            }
        ],
    }


def test_discovers_unique_token_source_from_stopped_container_history(tmp_path, monkeypatch) -> None:
    token = tmp_path / "worker-pool.token"
    token.write_text("opaque", encoding="utf-8")
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(reconcile, "_service_container_ids", lambda *, all_containers: ["old", "new"])
    monkeypatch.setattr(
        reconcile,
        "_inspect",
        lambda _ids: [_container(str(token)), _container(str(token))],
    )

    resolved, method = reconcile.discover_token_source()

    assert resolved == token
    assert method == "docker_mount_history"


def test_token_source_ambiguity_fails_closed(tmp_path, monkeypatch) -> None:
    first = tmp_path / "first.token"
    second = tmp_path / "second.token"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(reconcile, "_service_container_ids", lambda *, all_containers: ["one", "two"])
    monkeypatch.setattr(
        reconcile,
        "_inspect",
        lambda _ids: [_container(str(first)), _container(str(second))],
    )

    with pytest.raises(reconcile.ReconcileError, match="worker_pool_token_source_not_unique"):
        reconcile.discover_token_source()


def test_canonical_endpoint_requires_exact_loopback_binding(monkeypatch) -> None:
    monkeypatch.setattr(reconcile, "_service_container_ids", lambda *, all_containers: ["old", "active"])
    monkeypatch.setattr(
        reconcile,
        "_inspect",
        lambda _ids: [
            _container("ignored", running=True, canonical_port=False),
            _container("ignored", running=True, canonical_port=True),
        ],
    )

    endpoints = reconcile._canonical_endpoint_containers()

    assert len(endpoints) == 1


def test_evidence_does_not_require_secret_or_token_path(tmp_path) -> None:
    evidence = tmp_path / "evidence.json"
    payload = {
        "result": "WORKER_POOL_RUNTIME_RECONCILED",
        "token_source_method": "docker_mount_history",
        "token_content_read": False,
    }

    reconcile.write_evidence(evidence, payload)
    written = json.loads(evidence.read_text(encoding="utf-8"))

    assert written["token_content_read"] is False
    assert "token_source" not in written
