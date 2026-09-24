from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import pending_development_worker_pool_bridge as bridge


BASE_SHA = "a" * 40


def test_worker_pool_contract_identity_is_pinned_to_public_v1() -> None:
    assert bridge.EXPECTED_WORKER_POOL_CONTRACT_NAME == "engineering-worker-pool"
    assert bridge.EXPECTED_WORKER_POOL_CONTRACT_VERSION == "v1"


def report(status: str = "dispatched") -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "correlation_id": "run-1766",
        "repository": "owner/repo",
        "base_branch": "main",
        "decisions": [
            {
                "kind": "issue",
                "number": 1766,
                "route": "local_codex_branch_first",
                "status": status,
            }
        ],
    }


def test_probe_selects_only_local_codex_issue_decisions() -> None:
    payload = report()
    payload["decisions"].append(
        {"kind": "issue", "number": 99, "route": "human_gate", "status": "blocked"}
    )
    selected = bridge.local_codex_decisions(payload)
    assert [item["number"] for item in selected] == [1766]


def test_non_loopback_pool_is_rejected() -> None:
    with pytest.raises(bridge.BridgeError, match="worker_pool_url_not_loopback"):
        bridge.validate_pool_url("https://worker.example.internal:8097")


def test_token_resolution_prefers_explicit_then_environment(monkeypatch, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit-token"
    monkeypatch.setenv("CODEX_WORKER_POOL_API_TOKEN_FILE", str(tmp_path / "container-token"))
    monkeypatch.setenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", str(tmp_path / "host-token"))
    monkeypatch.setattr(
        bridge,
        "discover_worker_pool_token_file_from_docker",
        lambda: (_ for _ in ()).throw(AssertionError("docker discovery must not run")),
    )

    assert bridge.resolve_token_file(explicit) == explicit
    assert bridge.resolve_token_file(None) == tmp_path / "container-token"

    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE")
    assert bridge.resolve_token_file(None) == tmp_path / "host-token"


def test_read_token_classifies_missing_file_without_path_leak(tmp_path: Path) -> None:
    token_path = tmp_path / "missing-token"

    with pytest.raises(bridge.BridgeError) as exc_info:
        bridge.read_token(token_path)

    assert str(exc_info.value) == "worker_pool_token_file_missing"
    assert str(token_path) not in str(exc_info.value)


def test_read_token_classifies_permission_denied_without_path_leak(
    monkeypatch, tmp_path: Path
) -> None:
    token_path = tmp_path / "protected-token"

    def denied_read_text(_self: Path, *args, **kwargs) -> str:
        raise PermissionError("access denied")

    monkeypatch.setattr(Path, "read_text", denied_read_text)

    with pytest.raises(bridge.BridgeError) as exc_info:
        bridge.read_token(token_path)

    assert str(exc_info.value) == "worker_pool_token_permission_denied"
    assert str(token_path) not in str(exc_info.value)


def test_read_token_keeps_generic_os_error_sanitized(
    monkeypatch, tmp_path: Path
) -> None:
    token_path = tmp_path / "io-error-token"

    def failed_read_text(_self: Path, *args, **kwargs) -> str:
        raise OSError("device error")

    monkeypatch.setattr(Path, "read_text", failed_read_text)

    with pytest.raises(bridge.BridgeError) as exc_info:
        bridge.read_token(token_path)

    assert str(exc_info.value) == "worker_pool_token_unavailable"
    assert str(token_path) not in str(exc_info.value)


def test_token_resolution_discovers_single_docker_bind(monkeypatch) -> None:
    source = r"C:\secure\codex-worker-pool.token"
    calls: list[list[str]] = []

    def container(*, host_ip: str | None, source_path: str | None) -> dict[str, Any]:
        bindings = []
        if host_ip is not None:
            bindings = [{"HostIp": host_ip, "HostPort": bridge.WORKER_POOL_HOST_PORT}]
        mounts = []
        if source_path is not None:
            mounts = [
                {
                    "Type": "bind",
                    "Source": source_path,
                    "Destination": bridge.WORKER_POOL_TOKEN_DESTINATION,
                }
            ]
        return {
            "Config": {
                "Labels": {
                    "com.docker.compose.service": bridge.WORKER_POOL_COMPOSE_SERVICE
                }
            },
            "State": {"Running": True},
            "NetworkSettings": {
                "Ports": {bridge.WORKER_POOL_CONTAINER_PORT: bindings}
            },
            "Mounts": mounts,
        }

    def fake_run(args: list[str], **_kwargs):
        calls.append(args)
        if args[1] == "ps":
            return SimpleNamespace(stdout="container-old\ncontainer-active\n")
        if args[1] == "inspect":
            return SimpleNamespace(
                stdout=json.dumps(
                    [
                        container(host_ip=None, source_path=None),
                        container(host_ip=bridge.WORKER_POOL_HOST_IP, source_path=source),
                    ]
                )
            )
        raise AssertionError(args)

    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE", raising=False)
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    assert str(bridge.resolve_token_file(None)) == source
    assert calls[0] == [
        "docker",
        "ps",
        "--filter",
        f"label=com.docker.compose.service={bridge.WORKER_POOL_COMPOSE_SERVICE}",
        "--format",
        "{{.ID}}",
    ]
    assert calls[1] == ["docker", "inspect", "container-old", "container-active"]

def test_token_resolution_fails_closed_for_ambiguous_container(monkeypatch) -> None:
    def canonical(source: str) -> dict[str, Any]:
        return {
            "Config": {
                "Labels": {
                    "com.docker.compose.service": bridge.WORKER_POOL_COMPOSE_SERVICE
                }
            },
            "State": {"Running": True},
            "NetworkSettings": {
                "Ports": {
                    bridge.WORKER_POOL_CONTAINER_PORT: [
                        {
                            "HostIp": bridge.WORKER_POOL_HOST_IP,
                            "HostPort": bridge.WORKER_POOL_HOST_PORT,
                        }
                    ]
                }
            },
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": source,
                    "Destination": bridge.WORKER_POOL_TOKEN_DESTINATION,
                }
            ],
        }

    def fake_run(args: list[str], **_kwargs):
        if args[1] == "ps":
            return SimpleNamespace(stdout="one\ntwo\n")
        return SimpleNamespace(
            stdout=json.dumps([canonical(r"C:\secure\one"), canonical(r"C:\secure\two")])
        )

    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE", raising=False)
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    with pytest.raises(bridge.BridgeError, match="worker_pool_endpoint_container_not_unique"):
        bridge.resolve_token_file(None)

def test_token_resolution_fails_closed_for_ambiguous_mount(monkeypatch) -> None:
    def fake_run(args: list[str], **_kwargs):
        if args[1] == "ps":
            return SimpleNamespace(stdout="container-123\n")
        mount = {
            "Type": "bind",
            "Source": r"C:\secure\token",
            "Destination": bridge.WORKER_POOL_TOKEN_DESTINATION,
        }
        return SimpleNamespace(
            stdout=json.dumps(
                [
                    {
                        "Config": {
                            "Labels": {
                                "com.docker.compose.service": bridge.WORKER_POOL_COMPOSE_SERVICE
                            }
                        },
                        "State": {"Running": True},
                        "NetworkSettings": {
                            "Ports": {
                                bridge.WORKER_POOL_CONTAINER_PORT: [
                                    {
                                        "HostIp": bridge.WORKER_POOL_HOST_IP,
                                        "HostPort": bridge.WORKER_POOL_HOST_PORT,
                                    }
                                ]
                            }
                        },
                        "Mounts": [mount, dict(mount)],
                    }
                ]
            )
        )

    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE", raising=False)
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    with pytest.raises(bridge.BridgeError, match="worker_pool_token_mount_not_unique"):
        bridge.resolve_token_file(None)


def test_token_resolution_fails_closed_for_noncanonical_endpoint_binding(monkeypatch) -> None:
    def fake_run(args: list[str], **_kwargs):
        if args[1] == "ps":
            return SimpleNamespace(stdout="container-123\n")
        return SimpleNamespace(
            stdout=json.dumps(
                [
                    {
                        "Config": {
                            "Labels": {
                                "com.docker.compose.service": bridge.WORKER_POOL_COMPOSE_SERVICE
                            }
                        },
                        "State": {"Running": True},
                        "NetworkSettings": {
                            "Ports": {
                                bridge.WORKER_POOL_CONTAINER_PORT: [
                                    {"HostIp": "0.0.0.0", "HostPort": bridge.WORKER_POOL_HOST_PORT}
                                ]
                            }
                        },
                        "Mounts": [],
                    }
                ]
            )
        )

    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE", raising=False)
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    with pytest.raises(bridge.BridgeError, match="worker_pool_endpoint_container_not_unique"):
        bridge.resolve_token_file(None)


def test_enqueue_proves_replay_and_independent_readback() -> None:
    calls: list[tuple[str, str]] = []
    task = {
        "task_id": "cwp-123",
        "repository": "owner/repo",
        "issue_number": 1766,
        "request_id": bridge.local_codex_request_id("owner/repo", 1766, "main"),
        "branch": "codex/issue-1766-abc",
        "workspace_key": "worker-abc",
        "base_sha": BASE_SHA,
        "state": "queued",
    }

    def fake_request(
        method: str,
        url: str,
        token: str,
        payload: dict[str, Any] | None,
    ) -> tuple[int, dict[str, Any]]:
        assert token == "local-secret"
        calls.append((method, url))
        if url.endswith("/health"):
            return 200, {"status": "healthy"}
        if url.endswith("/v1/contract"):
            return 200, {
                "contract_name": bridge.EXPECTED_WORKER_POOL_CONTRACT_NAME,
                "contract_version": bridge.EXPECTED_WORKER_POOL_CONTRACT_VERSION,
            }
        if method == "POST" and len([call for call in calls if call[0] == "POST"]) == 1:
            assert payload is not None and payload["base_sha"] == BASE_SHA
            return 201, {"created": True, "task": dict(task)}
        if method == "POST":
            return 200, {"created": False, "task": dict(task)}
        if method == "GET" and "/v1/tasks/" in url:
            return 200, dict(task)
        raise AssertionError((method, url))

    result = bridge.enqueue_local_work(
        report(),
        base_sha=BASE_SHA,
        pool_url="http://127.0.0.1:8097",
        token="local-secret",
        request_fn=fake_request,
    )

    assert result["result"] == "WORKER_POOL_ENQUEUED"
    assert result["enqueued"] == 1
    assert result["items"][0]["created"] is True
    assert result["items"][0]["replay_created"] is False
    assert result["items"][0]["independent_readback"] is True
    assert result["items"][0]["base_sha"] == BASE_SHA
    assert result["contract_mode"] == "v1"
    assert result["contract_version"] == "v1"
    assert result["legacy_fallback_used"] is False
    assert result["items"][0]["contract_mode"] == "v1"
    assert "local-secret" not in str(result)
    assert [method for method, _url in calls] == ["GET", "GET", "POST", "POST", "GET"]


def test_already_dispatched_replays_into_same_idempotent_queue() -> None:
    assert len(bridge.local_codex_decisions(report("already_dispatched"))) == 1


def test_no_local_work_does_not_contact_pool() -> None:
    payload = report()
    payload["decisions"][0]["route"] = "human_gate"

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network must not be used")

    result = bridge.enqueue_local_work(
        payload,
        base_sha="invalid-is-ignored-without-work",
        pool_url="https://invalid.example",
        token="not-used",
        request_fn=forbidden,
    )
    assert result["result"] == "NO_LOCAL_CODEX_WORK"
    assert result["enqueued"] == 0


def test_invalid_base_sha_fails_before_network() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network must not be used")

    with pytest.raises(bridge.BridgeError, match="base_sha_invalid"):
        bridge.enqueue_local_work(
            report(),
            base_sha="bad",
            pool_url="http://127.0.0.1:8097",
            token="local-secret",
            request_fn=forbidden,
        )


def test_contract_probe_allows_only_missing_endpoint_as_legacy_fallback() -> None:
    def missing_contract(
        _method: str,
        _url: str,
        _token: str,
        _payload: dict[str, Any] | None,
    ) -> tuple[int, dict[str, Any]]:
        raise bridge.BridgeError("worker_pool_http_404")

    assert bridge.verify_contract(
        "http://127.0.0.1:8097",
        "local-secret",
        missing_contract,
        allow_legacy_fallback=True,
    ) == "legacy_fallback"

    with pytest.raises(bridge.BridgeError, match="worker_pool_contract_required"):
        bridge.verify_contract(
            "http://127.0.0.1:8097",
            "local-secret",
            missing_contract,
            allow_legacy_fallback=False,
        )


def test_contract_probe_rejects_incompatible_version() -> None:
    def incompatible(
        _method: str,
        _url: str,
        _token: str,
        _payload: dict[str, Any] | None,
    ) -> tuple[int, dict[str, Any]]:
        return 200, {
            "contract_name": bridge.EXPECTED_WORKER_POOL_CONTRACT_NAME,
            "contract_version": "v2",
        }

    with pytest.raises(bridge.BridgeError, match="worker_pool_contract_incompatible"):
        bridge.verify_contract(
            "http://127.0.0.1:8097",
            "local-secret",
            incompatible,
            allow_legacy_fallback=True,
        )


@pytest.mark.parametrize("reason", ["worker_pool_http_401", "worker_pool_http_503", "worker_pool_unreachable"])
def test_contract_probe_never_falls_back_on_auth_runtime_or_transport_failure(reason: str) -> None:
    def failed(
        _method: str,
        _url: str,
        _token: str,
        _payload: dict[str, Any] | None,
    ) -> tuple[int, dict[str, Any]]:
        raise bridge.BridgeError(reason)

    with pytest.raises(bridge.BridgeError, match=reason):
        bridge.verify_contract(
            "http://127.0.0.1:8097",
            "local-secret",
            failed,
            allow_legacy_fallback=True,
        )
