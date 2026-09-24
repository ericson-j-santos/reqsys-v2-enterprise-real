from __future__ import annotations

import importlib.util
import json
from io import BytesIO
from urllib.error import HTTPError
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "restore_codex_worker_pool_token_dev.py"
WORKFLOW = ROOT / ".github" / "workflows" / "codex-worker-pool-smoke-dev.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"

spec = importlib.util.spec_from_file_location("worker_pool_token_restore", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_restore_reuses_existing_token_without_rotation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("x" * 48, encoding="utf-8")
    monkeypatch.setattr(module, "_canonical_container_and_token_path", lambda: ("container-1", token_file))
    monkeypatch.setattr(module, "_inspect_container", lambda _container_id: {"Config": {"Env": []}})
    monkeypatch.setattr(module, "_validate_container_auth_contract", lambda _container: None)
    monkeypatch.setattr(module, "_validate_runtime", lambda _token: (200, True, ""))
    seen: list[list[str]] = []
    monkeypatch.setattr(module, "_docker", lambda args: seen.append(args) or "")

    result = module.restore()

    assert result["token_rotated"] is False
    assert result["existing_token_reused"] is True
    assert result["service_restarted"] is False
    assert result["authenticated_readback"] is True
    assert seen == []


def test_restore_generates_token_locally_and_recreates_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "token"
    container = {"Config": {"Env": []}}
    monkeypatch.setattr(module, "_canonical_container_and_token_path", lambda: ("container-1", token_file))
    monkeypatch.setattr(module, "_inspect_container", lambda _container_id: container)
    monkeypatch.setattr(module, "_validate_container_auth_contract", lambda _container: None)
    monkeypatch.setattr(module.secrets, "token_urlsafe", lambda _size: "y" * 64)
    monkeypatch.setattr(module, "_validate_runtime", lambda _token: (200, True, ""))
    monkeypatch.setattr(module, "_wait_runtime", lambda _token: 200)
    recreated: list[tuple[dict, Path]] = []
    monkeypatch.setattr(
        module,
        "_compose_recreate_service",
        lambda inspected, path: recreated.append((inspected, path)),
    )

    result = module.restore()

    assert token_file.read_text(encoding="utf-8").strip() == "y" * 64
    assert result["token_rotated"] is True
    assert result["service_restarted"] is False
    assert result["service_recreated"] is True
    assert result["bind_mount_resynced"] is True
    assert recreated == [(container, token_file)]
    assert "y" * 64 not in json.dumps(result)


def test_restore_recreates_stale_file_bind_without_rotating_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("x" * 48, encoding="utf-8")
    container = {"Config": {"Env": []}}
    monkeypatch.setattr(module, "_canonical_container_and_token_path", lambda: ("container-1", token_file))
    monkeypatch.setattr(module, "_inspect_container", lambda _container_id: container)
    monkeypatch.setattr(module, "_validate_container_auth_contract", lambda _container: None)

    validations = iter(
        [
            (200, False, "worker_pool_token_mismatch_after_restore"),
            (200, True, ""),
        ]
    )
    monkeypatch.setattr(module, "_validate_runtime", lambda _token: next(validations))
    monkeypatch.setattr(module, "_container_token_matches_host", lambda _container_id, _token: False)
    monkeypatch.setattr(module, "_wait_runtime", lambda _token: 200)
    recreated: list[tuple[dict, Path]] = []
    monkeypatch.setattr(
        module,
        "_compose_recreate_service",
        lambda inspected, path: recreated.append((inspected, path)),
    )

    result = module.restore()

    assert result["token_rotated"] is False
    assert result["existing_token_reused"] is True
    assert result["service_recreated"] is True
    assert result["bind_mount_resynced"] is True
    assert recreated == [(container, token_file)]


def test_restore_fails_closed_when_container_and_host_token_match_but_api_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("x" * 48, encoding="utf-8")
    container = {"Config": {"Env": []}}
    monkeypatch.setattr(module, "_canonical_container_and_token_path", lambda: ("container-1", token_file))
    monkeypatch.setattr(module, "_inspect_container", lambda _container_id: container)
    monkeypatch.setattr(module, "_validate_container_auth_contract", lambda _container: None)
    monkeypatch.setattr(
        module,
        "_validate_runtime",
        lambda _token: (200, False, "worker_pool_token_mismatch_after_restore"),
    )
    monkeypatch.setattr(module, "_container_token_matches_host", lambda _container_id, _token: True)
    monkeypatch.setattr(
        module,
        "_compose_recreate_service",
        lambda _container, _path: pytest.fail("must not recreate when bind content already matches"),
    )

    with pytest.raises(module.RestoreError, match="worker_pool_auth_process_mismatch"):
        module.restore()


def test_container_auth_contract_requires_exact_token_file_env() -> None:
    module._validate_container_auth_contract(
        {
            "Config": {
                "Env": [
                    f"CODEX_WORKER_POOL_API_TOKEN_FILE={module.TOKEN_DESTINATION}"
                ]
            }
        }
    )
    with pytest.raises(module.RestoreError, match="worker_pool_token_env_mismatch"):
        module._validate_container_auth_contract({"Config": {"Env": []}})


def test_restore_fails_closed_for_non_file_token_path(tmp_path: Path) -> None:
    with pytest.raises(module.RestoreError, match="worker_pool_token_path_not_file"):
        module._read_existing_token(tmp_path)


def test_write_new_token_creates_missing_canonical_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "missing" / "nested" / "token"
    monkeypatch.setattr(module.secrets, "token_urlsafe", lambda _size: "z" * 64)

    token = module._write_new_token(token_file)

    assert token == "z" * 64
    assert token_file.is_file()
    assert token_file.read_text(encoding="utf-8").strip() == "z" * 64


def test_write_new_token_fails_closed_when_parent_is_unusable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked_parent = tmp_path / "blocked-parent"
    blocked_parent.write_text("not-a-directory", encoding="utf-8")
    token_file = blocked_parent / "token"
    monkeypatch.setattr(module.secrets, "token_urlsafe", lambda _size: "z" * 64)

    with pytest.raises(module.RestoreError, match="worker_pool_token_parent_create_failed"):
        module._write_new_token(token_file)


def test_request_preserves_health_payload_on_http_503(monkeypatch: pytest.MonkeyPatch) -> None:
    body = BytesIO(
        b'{"status":"not_ready","auth_configured":false,"expected_rules_sha_configured":true}'
    )

    def fail(_request, timeout: int):
        assert timeout == 3
        raise HTTPError(module.HEALTH_URL, 503, "not ready", {}, body)

    monkeypatch.setattr(module, "urlopen", fail)

    status, payload = module._request(module.HEALTH_URL)

    assert status == 503
    assert payload["auth_configured"] is False
    assert payload["expected_rules_sha_configured"] is True


@pytest.mark.parametrize(
    ("health_status", "health", "snapshot_status", "expected"),
    [
        (0, {}, 0, "worker_pool_health_unreachable"),
        (
            503,
            {"auth_configured": False, "expected_rules_sha_configured": True},
            503,
            "worker_pool_auth_file_not_visible_in_container",
        ),
        (
            503,
            {"auth_configured": True, "expected_rules_sha_configured": False},
            200,
            "worker_pool_expected_rules_sha_not_configured",
        ),
        (
            200,
            {"auth_configured": True, "expected_rules_sha_configured": True},
            401,
            "worker_pool_token_mismatch_after_restore",
        ),
        (
            200,
            {"auth_configured": True, "expected_rules_sha_configured": True},
            0,
            "worker_pool_authenticated_endpoint_unreachable",
        ),
    ],
)
def test_runtime_failure_reason_is_specific_and_sanitized(
    health_status: int,
    health: dict[str, object],
    snapshot_status: int,
    expected: str,
) -> None:
    assert module._runtime_failure_reason(health_status, health, snapshot_status) == expected


def test_wait_runtime_propagates_last_specific_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        module,
        "_validate_runtime",
        lambda _token: (503, False, "worker_pool_expected_rules_sha_not_configured"),
    )
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(module.RestoreError, match="worker_pool_expected_rules_sha_not_configured"):
        module._wait_runtime("x" * 48, attempts=2)


def test_workflow_uses_session_launcher_and_owner_risk3_gateway() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "chatgpt-operational-rules" in raw
    assert "session_launcher.py" in raw
    assert "SESSION_LAUNCH_OK" in raw
    assert "owner_risk3_gateway.py" in raw
    assert "reqsys.worker-pool-auth-file-restore.dev" in raw
    assert "repo://reqsys/environment/dev/worker-pool" in raw
    assert "scripts/configure_worker_pool_auth_restore_risk3.py" in raw
    assert "ENABLE-WORKER-POOL-AUTH-RESTORE-ONCE" in raw
    assert "DISABLE-WORKER-POOL-AUTH-RESTORE-ONCE" in raw
    assert "Remover autorização Risk3 temporária" in raw
    assert "secrets." not in raw


def test_gateway_and_runner_policy_allow_only_fixed_restore_workflow() -> None:
    gateway = GATEWAY.read_text(encoding="utf-8")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert "github.event.comment.body == '/reqsys run codex-worker-pool-token-restore-dev'" in gateway
    assert "target='codex-worker-pool-smoke-dev.yml'" in gateway
    assert "mode='restore'" in gateway
    assert "-f mode=restore" in gateway
    assert ".github/workflows/codex-worker-pool-smoke-dev.yml" in policy["approved_workflows"]
    assert ".github/workflows/codex-worker-pool-token-restore-dev.yml" not in policy["approved_workflows"]
    assert not (ROOT / ".github" / "workflows" / "codex-worker-pool-token-restore-dev.yml").exists()
