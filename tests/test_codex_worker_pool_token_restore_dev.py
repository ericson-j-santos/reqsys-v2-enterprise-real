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


def test_restore_resyncs_host_file_from_valid_runtime_token_without_recreate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "token"
    host_token = "x" * 48
    runtime_token = "r" * 48
    token_file.write_text(host_token, encoding="utf-8")
    container = {"Config": {"Env": []}}
    monkeypatch.setattr(
        module,
        "_canonical_container_and_token_path",
        lambda: ("container-1", token_file),
    )
    monkeypatch.setattr(module, "_inspect_container", lambda _container_id: container)
    monkeypatch.setattr(module, "_validate_container_auth_contract", lambda _container: None)

    def validate(token: str) -> tuple[int, bool, str]:
        if token == host_token:
            return 200, False, "worker_pool_token_mismatch_after_restore"
        if token == runtime_token:
            return 200, True, ""
        pytest.fail("unexpected token")

    monkeypatch.setattr(module, "_validate_runtime", validate)
    monkeypatch.setattr(module, "_read_container_token", lambda _container_id: runtime_token)
    monkeypatch.setattr(
        module,
        "_compose_recreate_service",
        lambda _container, _path: pytest.fail("mismatch must not recreate the service"),
    )

    result = module.restore()

    assert token_file.read_text(encoding="utf-8").strip() == runtime_token
    assert result["token_rotated"] is False
    assert result["existing_token_reused"] is True
    assert result["service_recreated"] is False
    assert result["bind_mount_resynced"] is False
    assert result["runtime_token_reused"] is True
    assert result["host_file_resynced_from_runtime"] is True
    assert result["authenticated_readback"] is True
    assert runtime_token not in json.dumps(result)

def test_restore_fails_closed_when_container_and_host_token_match_but_api_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "token"
    host_token = "x" * 48
    token_file.write_text(host_token, encoding="utf-8")
    container = {"Config": {"Env": []}}
    monkeypatch.setattr(
        module,
        "_canonical_container_and_token_path",
        lambda: ("container-1", token_file),
    )
    monkeypatch.setattr(module, "_inspect_container", lambda _container_id: container)
    monkeypatch.setattr(module, "_validate_container_auth_contract", lambda _container: None)
    monkeypatch.setattr(
        module,
        "_validate_runtime",
        lambda _token: (200, False, "worker_pool_token_mismatch_after_restore"),
    )
    monkeypatch.setattr(module, "_read_container_token", lambda _container_id: host_token)
    monkeypatch.setattr(
        module,
        "_write_token",
        lambda _path, _token: pytest.fail("must not rewrite when host/runtime already match"),
    )

    with pytest.raises(module.RestoreError, match="worker_pool_auth_process_mismatch"):
        module.restore()

def test_restore_keeps_host_unchanged_when_runtime_token_is_not_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "token"
    host_token = "x" * 48
    runtime_token = "r" * 48
    token_file.write_text(host_token, encoding="utf-8")
    monkeypatch.setattr(
        module,
        "_canonical_container_and_token_path",
        lambda: ("container-1", token_file),
    )
    monkeypatch.setattr(module, "_inspect_container", lambda _container_id: {"Config": {"Env": []}})
    monkeypatch.setattr(module, "_validate_container_auth_contract", lambda _container: None)

    def validate(token: str) -> tuple[int, bool, str]:
        if token == host_token:
            return 200, False, "worker_pool_token_mismatch_after_restore"
        if token == runtime_token:
            return 200, False, "worker_pool_token_mismatch_after_restore"
        pytest.fail("unexpected token")

    monkeypatch.setattr(module, "_validate_runtime", validate)
    monkeypatch.setattr(module, "_read_container_token", lambda _container_id: runtime_token)

    with pytest.raises(module.RestoreError, match="worker_pool_token_mismatch_after_restore"):
        module.restore()

    assert token_file.read_text(encoding="utf-8").strip() == host_token


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


def test_compose_recreate_is_scoped_and_does_not_put_token_in_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "token"
    working_dir = tmp_path / "compose"
    working_dir.mkdir()
    config_file = working_dir / "docker-compose.pc24x7-codex-worker-pool.yml"
    config_file.write_text("services: {}\n", encoding="utf-8")
    container = {
        "Config": {
            "Labels": {
                "com.docker.compose.project": "reqsys",
                "com.docker.compose.project.working_dir": str(working_dir),
                "com.docker.compose.project.config_files": str(config_file),
            },
            "Env": [
                f"CODEX_WORKER_POOL_API_TOKEN_FILE={module.TOKEN_DESTINATION}",
                "CODEX_WORKER_POOL_EXPECTED_RULES_SHA=" + ("a" * 40),
            ],
        }
    }
    seen: list[tuple[list[str], dict[str, str] | None, str]] = []

    def fake_docker(
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        failure_reason: str = "worker_pool_docker_command_failed",
    ) -> str:
        seen.append((args, env, failure_reason))
        return ""

    monkeypatch.setattr(module, "_docker", fake_docker)

    recovered = module._compose_recreate_service(container, token_file)

    assert recovered is False
    assert len(seen) == 1
    args, env, failure_reason = seen[0]
    assert args[:7] == [
        "compose",
        "--project-name",
        "reqsys",
        "--project-directory",
        str(working_dir),
        "--file",
        str(config_file),
    ]
    assert args[-6:] == [
        "up",
        "-d",
        "--force-recreate",
        "--no-deps",
        "--no-build",
        module.SERVICE,
    ]
    assert failure_reason == "worker_pool_compose_recreate_failed"
    assert env is not None
    assert env["CODEX_WORKER_POOL_API_TOKEN_FILE_HOST"] == str(token_file)
    assert env["CODEX_WORKER_POOL_EXPECTED_RULES_SHA"] == "a" * 40
    assert "x" * 48 not in json.dumps(args)
    assert "x" * 48 not in json.dumps(env)


def test_compose_recreate_recovers_stale_ephemeral_source_from_canonical_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "token"
    canonical_dir = tmp_path / "current"
    canonical_dir.mkdir()
    canonical = canonical_dir / "docker-compose.pc24x7-codex-worker-pool.yml"
    canonical.write_text(
        "\n".join(
            [
                "services:",
                "  codex-worker-pool:",
                "    restart: unless-stopped",
                '    ports: ["127.0.0.1:8097:8097"]',
                "    environment:",
                f"      CODEX_WORKER_POOL_API_TOKEN_FILE: {module.TOKEN_DESTINATION}",
                "      CODEX_WORKER_POOL_EXPECTED_RULES_SHA: x",
                "    volumes:",
                f'      - "${{CODEX_WORKER_POOL_API_TOKEN_FILE_HOST}}:{module.TOKEN_DESTINATION}:ro"',
                "      - codex-worker-pool-state:/data",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CANONICAL_COMPOSE_FILE", canonical)
    stale = Path("C:/dev/chatgpt-workers/wt-deleted") / canonical.name
    container = {
        "Config": {
            "Labels": {
                "com.docker.compose.project": "reqsys",
                "com.docker.compose.project.working_dir": str(stale.parent),
                "com.docker.compose.project.config_files": str(stale),
            },
            "Env": ["CODEX_WORKER_POOL_EXPECTED_RULES_SHA=" + ("b" * 40)],
        }
    }
    seen: list[tuple[list[str], str]] = []

    def fake_docker(
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        failure_reason: str = "worker_pool_docker_command_failed",
    ) -> str:
        seen.append((args, failure_reason))
        return ""

    monkeypatch.setattr(module, "_docker", fake_docker)

    recovered = module._compose_recreate_service(container, token_file)

    assert recovered is True
    args, failure_reason = seen[0]
    assert "--project-directory" in args
    assert args[args.index("--project-directory") + 1] == str(canonical.parent)
    assert "--file" in args
    assert args[args.index("--file") + 1] == str(canonical)
    assert "--no-build" in args
    assert failure_reason == "worker_pool_compose_recreate_failed"


def test_compose_recreate_rejects_stale_unexpected_compose_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = tmp_path / "docker-compose.pc24x7-codex-worker-pool.yml"
    canonical.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(module, "CANONICAL_COMPOSE_FILE", canonical)
    container = {
        "Config": {
            "Labels": {
                "com.docker.compose.project": "reqsys",
                "com.docker.compose.project.working_dir": "C:/deleted",
                "com.docker.compose.project.config_files": "C:/deleted/other-compose.yml",
            },
            "Env": ["CODEX_WORKER_POOL_EXPECTED_RULES_SHA=" + ("c" * 40)],
        }
    }

    with pytest.raises(module.RestoreError, match="worker_pool_compose_source_unavailable"):
        module._compose_recreate_service(container, tmp_path / "token")


def test_compose_recreate_fails_closed_without_compose_identity(
    tmp_path: Path,
) -> None:
    with pytest.raises(module.RestoreError, match="worker_pool_compose_identity_missing"):
        module._compose_recreate_service({"Config": {"Labels": {}, "Env": []}}, tmp_path / "token")


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
