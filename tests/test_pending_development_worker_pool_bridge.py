from __future__ import annotations
from pathlib import Path
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


def test_token_resolution_prefers_explicit_then_host_then_service(monkeypatch, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit-token"
    host = tmp_path / "host-token"
    service = tmp_path / "service-token"
    monkeypatch.setenv("CODEX_WORKER_POOL_API_TOKEN_FILE", str(service))
    monkeypatch.setenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", str(host))
    assert bridge.resolve_token_file(explicit) == explicit
    assert bridge.resolve_token_file(None) == host
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST")
    assert bridge.resolve_token_file(None) == service


def test_native_token_file_reads_existing_value(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "protected-token"
    path.write_text("test-fixture-not-a-real-secret\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", str(path))
    assert bridge.read_token(bridge.resolve_token_file(None)) == "test-fixture-not-a-real-secret"


def test_no_native_token_reference_fails_closed_without_docker_probe(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE", raising=False)
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setenv("DOCKER_HOST", "tcp://127.0.0.1:2375")
    with pytest.raises(bridge.BridgeError, match="^worker_pool_token_file_not_configured$"):
        bridge.resolve_token_file(None)
    source = (Path(__file__).resolve().parents[1] / "scripts/pending_development_worker_pool_bridge.py").read_text(
        encoding="utf-8"
    ).lower()
    assert "subprocess" not in source
    assert "docker" not in source


def test_missing_reference_diagnostic_is_sanitized(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE", raising=False)
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    with pytest.raises(bridge.BridgeError) as exc:
        bridge.resolve_token_file(None)
    assert str(exc.value) == "worker_pool_token_file_not_configured"


def test_token_reference_rejects_relative_path(monkeypatch) -> None:
    monkeypatch.setenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", "secrets/token")
    with pytest.raises(bridge.BridgeError, match="worker_pool_token_file_not_absolute"):
        bridge.resolve_token_file(None)
    with pytest.raises(bridge.BridgeError, match="worker_pool_token_file_not_absolute"):
        bridge.read_token(Path("secrets/token"))


def test_token_reference_rejects_symlink(monkeypatch, tmp_path: Path) -> None:
    alias = tmp_path / "alias"
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self == alias or original_is_symlink(self))
    with pytest.raises(bridge.BridgeError, match="worker_pool_token_file_symlink_forbidden"):
        bridge.resolve_token_file(alias)
    with pytest.raises(bridge.BridgeError, match="worker_pool_token_file_symlink_forbidden"):
        bridge.read_token(alias)


def test_token_reference_rejects_directory_without_leak(tmp_path: Path) -> None:
    with pytest.raises(bridge.BridgeError) as exc:
        bridge.read_token(tmp_path)
    assert str(exc.value) == "worker_pool_token_file_not_regular"
    assert str(tmp_path) not in str(exc.value)


def test_read_token_classifies_missing_file_without_path_leak(tmp_path: Path) -> None:
    path = tmp_path / "missing-token"
    with pytest.raises(bridge.BridgeError) as exc:
        bridge.read_token(path)
    assert str(exc.value) == "worker_pool_token_file_missing"
    assert str(path) not in str(exc.value)


def test_read_token_classifies_permission_denied_without_path_leak(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "protected-token"
    def denied(_self: Path, *args, **kwargs) -> str:
        raise PermissionError("access denied")
    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(bridge.BridgeError) as exc:
        bridge.read_token(path)
    assert str(exc.value) == "worker_pool_token_permission_denied"
    assert str(path) not in str(exc.value)


def test_read_token_keeps_generic_os_error_sanitized(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "io-error-token"
    def failed(_self: Path, *args, **kwargs) -> str:
        raise OSError("device error")
    monkeypatch.setattr(Path, "read_text", failed)
    with pytest.raises(bridge.BridgeError) as exc:
        bridge.read_token(path)
    assert str(exc.value) == "worker_pool_token_unavailable"
    assert str(path) not in str(exc.value)


def test_enqueue_prefers_work_v1_and_proves_replay_and_independent_readback() -> None:
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
    work = {
        "work_id": "work-123",
        "task_id": task["task_id"],
        "phase": "queue",
        "task": dict(task),
        "evidence": {"state": "pending"},
        "merge": {"state": "pending"},
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
        if method == "POST" and url.endswith("/v1/work"):
            assert payload is not None and payload["base_sha"] == BASE_SHA
            post_count = sum(1 for m, u in calls if m == "POST" and u.endswith("/v1/work"))
            return (
                (201, {"created": True, "work": dict(work)})
                if post_count == 1
                else (200, {"created": False, "work": dict(work)})
            )
        if method == "GET" and url.endswith("/v1/work/work-123"):
            return 200, dict(work)
        raise AssertionError((method, url))

    result = bridge.enqueue_local_work(
        report(),
        base_sha=BASE_SHA,
        pool_url="http://127.0.0.1:8097",
        token="local-secret",
        request_fn=fake_request,
    )

    item = result["items"][0]
    assert result["result"] == "WORKER_POOL_ENQUEUED"
    assert result["enqueued"] == 1
    assert item["created"] is True
    assert item["replay_created"] is False
    assert item["independent_readback"] is True
    assert item["base_sha"] == BASE_SHA
    assert item["work_id"] == "work-123"
    assert item["task_id"] == "cwp-123"
    assert item["dispatch_mode"] == "work_v1"
    assert item["work_phase"] == "queue"
    assert result["dispatch_modes"] == ["work_v1"]
    assert result["work_orchestrator_preferred"] is True
    assert result["contract_mode"] == "v1"
    assert result["contract_version"] == "v1"
    assert result["legacy_fallback_used"] is False
    assert "local-secret" not in str(result)
    assert [method for method, _url in calls] == ["GET", "GET", "POST", "POST", "GET"]


def test_work_v1_404_falls_back_to_task_v1_only_when_allowed() -> None:
    calls: list[tuple[str, str]] = []
    task = {
        "task_id": "cwp-fallback",
        "repository": "owner/repo",
        "issue_number": 1766,
        "request_id": bridge.local_codex_request_id("owner/repo", 1766, "main"),
        "branch": "codex/issue-1766-fallback",
        "workspace_key": "worker-fallback",
        "base_sha": BASE_SHA,
        "state": "queued",
    }

    def fake_request(method, url, _token, _payload):
        calls.append((method, url))
        if url.endswith("/health"):
            return 200, {"status": "healthy"}
        if url.endswith("/v1/contract"):
            return 200, {
                "contract_name": bridge.EXPECTED_WORKER_POOL_CONTRACT_NAME,
                "contract_version": "v1",
            }
        if method == "POST" and url.endswith("/v1/work"):
            raise bridge.BridgeError("worker_pool_http_404")
        if method == "POST" and url.endswith("/v1/tasks"):
            post_count = sum(1 for m, u in calls if m == "POST" and u.endswith("/v1/tasks"))
            return (
                (201, {"created": True, "task": dict(task)})
                if post_count == 1
                else (200, {"created": False, "task": dict(task)})
            )
        if method == "GET" and url.endswith("/v1/tasks/cwp-fallback"):
            return 200, dict(task)
        raise AssertionError((method, url))

    result = bridge.enqueue_local_work(
        report(),
        base_sha=BASE_SHA,
        pool_url="http://127.0.0.1:8097",
        token="local-secret",
        request_fn=fake_request,
        allow_work_fallback=True,
    )
    assert result["items"][0]["dispatch_mode"] == "task_v1_fallback"
    assert result["items"][0]["work_id"] is None
    assert result["items"][0]["independent_readback"] is True
    assert result["dispatch_modes"] == ["task_v1_fallback"]

    with pytest.raises(bridge.BridgeError, match="worker_pool_work_contract_required"):
        bridge.enqueue_local_work(
            report(),
            base_sha=BASE_SHA,
            pool_url="http://127.0.0.1:8097",
            token="local-secret",
            request_fn=fake_request,
            allow_work_fallback=False,
        )


@pytest.mark.parametrize("reason", ["worker_pool_http_401", "worker_pool_http_503", "worker_pool_unreachable"])
def test_work_v1_never_falls_back_on_auth_runtime_or_transport_failure(reason: str) -> None:
    def failed(method, url, _token, _payload):
        if url.endswith("/health"):
            return 200, {"status": "healthy"}
        if url.endswith("/v1/contract"):
            return 200, {
                "contract_name": bridge.EXPECTED_WORKER_POOL_CONTRACT_NAME,
                "contract_version": "v1",
            }
        if method == "POST" and url.endswith("/v1/work"):
            raise bridge.BridgeError(reason)
        raise AssertionError((method, url))

    with pytest.raises(bridge.BridgeError, match=reason):
        bridge.enqueue_local_work(
            report(),
            base_sha=BASE_SHA,
            pool_url="http://127.0.0.1:8097",
            token="local-secret",
            request_fn=failed,
            allow_work_fallback=True,
        )


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


def _assert_legacy_handoff_checkout_contract(source: str) -> None:
    """Reject using a task's historic base_sha to run the dispatcher itself."""
    assert "\n  enqueue:\n" in source
    enqueue = source.split("\n  enqueue:\n", 1)[1].split(
        "\n  native-preflight:\n", 1
    )[0]
    assert "github.ref == 'refs/heads/main'" in enqueue
    assert "ref: ${{ github.sha }}" in enqueue
    assert "ref: ${{ inputs.base_sha }}" not in enqueue
    assert '--base-sha "${{ inputs.base_sha }}"' in enqueue
    assert '--base-sha "${{ github.sha }}"' not in enqueue
    assert "persist-credentials: false" in enqueue


def test_handoff_uses_current_trusted_dispatcher_without_rebasing_task() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/codex-worker-pool-handoff.yml"
    ).read_text(encoding="utf-8")
    _assert_legacy_handoff_checkout_contract(workflow)


@pytest.mark.parametrize(
    "before,after",
    [
        ("ref: ${{ github.sha }}", "ref: ${{ inputs.base_sha }}"),
        ('--base-sha "${{ inputs.base_sha }}"', '--base-sha "${{ github.sha }}"'),
        (" && github.ref == 'refs/heads/main'", ""),
        ("persist-credentials: false", "persist-credentials: true"),
    ],
)
def test_handoff_sha_separation_regression_controls_detect_old_bug(
    before: str, after: str
) -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/codex-worker-pool-handoff.yml"
    ).read_text(encoding="utf-8")
    assert before in workflow
    with pytest.raises(AssertionError):
        _assert_legacy_handoff_checkout_contract(workflow.replace(before, after, 1))
