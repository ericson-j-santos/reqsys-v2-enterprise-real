from __future__ import annotations

import importlib.util
import json

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "noteri_study_mode_dev_reconcile.py"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-study-mode-dev-reconcile.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"
OVERLAY = ROOT / "docker-compose.noteri-study-mode.yml"
COMPOSE_DEV = ROOT / "docker-compose.dev.yml"
FRONTEND = ROOT / "frontend" / "src" / "services" / "hostProfileLocalAgent.js"
BACKEND_API = ROOT / "backend" / "app" / "api" / "noteri_host_profile.py"
NGINX_DEV = ROOT / "infra" / "nginx" / "default.dev.conf"

spec = importlib.util.spec_from_file_location("noteri_study_mode_dev_reconcile", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reconciler_is_fixed_to_pc24x7_dev_gateway():
    assert module.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert module.DEV_GATEWAY_PORT == "8083"
    assert module.DEV_API_PORT == "8210"
    assert module.GATEWAY == "http://127.0.0.1:8083"
    assert module.DIRECT_API == "http://127.0.0.1:8210"
    assert module.CONFIRM == "RECONCILE-NOTERI-STUDY-MODE-DEV"


def test_dev_compose_defaults_gateway_to_canonical_8083():
    raw = COMPOSE_DEV.read_text(encoding="utf-8")
    assert "${GATEWAY_PORT:-8083}:80" in raw
    assert "${GATEWAY_PORT:-8081}:80" not in raw


def test_gateway_port_repair_compose_is_nginx_only_and_secret_free(tmp_path, monkeypatch):
    working_dir = tmp_path / "runtime"
    nginx_bind = working_dir / "infra" / "nginx" / "default.dev.conf"
    nginx_bind.parent.mkdir(parents=True)
    nginx_bind.write_text("server {}\n", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-leak")
    monkeypatch.setenv("PATH", "C:\\Windows\\System32")
    item = {
        "Config": {
            "Image": "nginx:alpine",
            "Labels": {
                "com.docker.compose.project": "reqsys-live",
                "com.docker.compose.project.working_dir": str(working_dir),
            },
        },
        "HostConfig": {"RestartPolicy": {"Name": "unless-stopped"}},
        "NetworkSettings": {"Networks": {"reqsys-live_reqsys-net": {}}},
    }

    observed_working_dir, compose_path = module.write_nginx_gateway_repair_compose(
        item,
        "reqsys-live",
        nginx_bind,
        "8083",
    )
    payload = json.loads(compose_path.read_text(encoding="utf-8"))

    assert observed_working_dir == working_dir
    assert list(payload["services"]) == ["nginx"]
    service = payload["services"]["nginx"]
    assert service["image"] == "nginx:alpine"
    assert service["restart"] == "unless-stopped"
    assert service["ports"] == ["8083:80"]
    assert "environment" not in service
    assert "build" not in service
    assert "depends_on" not in service
    assert service["volumes"][0]["target"] == "/etc/nginx/conf.d/default.conf"
    assert service["volumes"][0]["read_only"] is True
    assert payload["networks"]["runtime"] == {
        "external": True,
        "name": "reqsys-live_reqsys-net",
    }
    assert "GITHUB_TOKEN" not in module.minimal_process_env()
    assert "must-not-leak" not in compose_path.read_text(encoding="utf-8")


def test_gateway_port_repair_is_targeted_and_rollback_capable():
    raw = SCRIPT.read_text(encoding="utf-8")
    assert '"--no-deps"' in raw
    assert '"--force-recreate"' in raw
    assert '"--pull"' in raw
    assert '"never"' in raw
    assert 'env["COMPOSE_DISABLE_ENV_FILE"] = "true"' in raw
    assert 'stage="nginx_gateway_port_repair"' in raw
    assert 'stage="nginx_gateway_port_rollback"' in raw
    assert "docker-compose.gateway-repair-" in raw
    assert '"gateway_port_repair_applied": gateway_port_repaired' in raw
    assert '"nginx_only_generated_no_env"' in raw


def test_windows_path_normalizes_docker_desktop_mounts():
    assert str(module.windows_path("/run/desktop/mnt/host/c/dev/reqsys")).replace("\\", "/") == "C:/dev/reqsys"
    assert str(module.windows_path("/host_mnt/c/dev/reqsys")).replace("\\", "/") == "C:/dev/reqsys"


def test_compose_environment_file_from_runtime_label_is_replayed_without_reading_value(tmp_path):
    env_file = tmp_path / "stack.env"
    env_file.write_text("TOKEN=must-not-be-read\n", encoding="utf-8")
    item = {
        "Config": {
            "Labels": {
                "com.docker.compose.project.environment_file": str(env_file),
            }
        }
    }

    environment_files = module.compose_environment_files(item, tmp_path)

    assert environment_files == [env_file.resolve()]
    command = module.compose_base(
        "reqsys-live",
        [tmp_path / "docker-compose.yml"],
        tmp_path,
        environment_files,
    )
    assert command.count("--env-file") == 1
    assert str(env_file.resolve()) in command
    assert "must-not-be-read" not in " ".join(command)


def test_compose_environment_file_label_supports_multiple_files_and_fails_closed(tmp_path):
    first = tmp_path / "base.env"
    second = tmp_path / "dev.env"
    first.write_text("A=1\n", encoding="utf-8")
    second.write_text("B=2\n", encoding="utf-8")
    item = {
        "Config": {
            "Labels": {
                "com.docker.compose.project.environment_file": f"{first},{second}",
            }
        }
    }
    assert module.compose_environment_files(item, tmp_path) == [
        first.resolve(),
        second.resolve(),
    ]

    missing = {
        "Config": {
            "Labels": {
                "com.docker.compose.project.environment_file": str(tmp_path / "missing.env"),
            }
        }
    }
    with pytest.raises(module.ReconcileError) as exc:
        module.compose_environment_files(missing, tmp_path)
    assert exc.value.code == "compose_environment_file_missing"
    assert exc.value.stage == "compose_context"


def test_bind_source_accepts_read_only_nginx_but_rw_bind_remains_strict(tmp_path):
    item = {
        "Mounts": [
            {
                "Destination": "/etc/nginx/conf.d/default.conf",
                "Type": "bind",
                "RW": False,
                "Source": str(tmp_path / "default.dev.conf"),
            }
        ]
    }
    assert module.bind_source(item, "/etc/nginx/conf.d/default.conf") == tmp_path / "default.dev.conf"
    assert module.rw_bind_source(item, "/etc/nginx/conf.d/default.conf") is None


def test_required_nginx_bind_source_uses_nginx_own_compose_working_dir(tmp_path):
    working_dir = tmp_path / "runtime-nginx"
    config = working_dir / "infra" / "nginx" / "default.dev.conf"
    config.parent.mkdir(parents=True)
    config.write_text("server {}\n", encoding="utf-8")
    item = {
        "Config": {
            "Labels": {
                "com.docker.compose.project": "reqsys-dev",
                "com.docker.compose.project.working_dir": str(working_dir),
            }
        },
        "Mounts": [
            {
                "Destination": "/etc/nginx/conf.d/default.conf",
                "Type": "bind",
                "RW": False,
                "Source": str(config),
            }
        ],
    }

    assert module.required_nginx_bind_source(item, "reqsys-dev") == config

    foreign = tmp_path / "other-runtime" / "infra" / "nginx" / "default.dev.conf"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("server {}\n", encoding="utf-8")
    item["Mounts"][0]["Source"] = str(foreign)
    with pytest.raises(module.ReconcileError) as exc:
        module.required_nginx_bind_source(item, "reqsys-dev")
    assert exc.value.code == "nginx_config_bind_mismatch"
    assert exc.value.stage == "nginx_source_bind"


def test_overlay_routes_profile_through_allowlisted_control_plane():
    raw = OVERLAY.read_text(encoding="utf-8")
    assert "NOTERI_CONTROL_PLANE_URL=http://host.docker.internal:8787" in raw
    assert "NOTERI_HOST_PROFILE_EXPECTED_HOST=Noteri" in raw
    assert "NOTERI_HOST_PROFILE_PATH" not in raw
    assert "TodoGlobal24x7" not in raw
    assert "/noteri-runtime" not in raw
    assert "frontend:" not in raw
    assert "prod" not in raw.lower()


def test_frontend_uses_same_origin_backend_not_browser_loopback():
    raw = FRONTEND.read_text(encoding="utf-8")
    assert "api.get('/v1/noteri/profile'" in raw
    assert "api.post('/v1/noteri/profile'" in raw
    assert "127.0.0.1:8765" not in raw
    assert "fetch(" not in raw


def test_backend_requires_auth_for_read_and_admin_for_write():
    raw = BACKEND_API.read_text(encoding="utf-8")
    assert "Depends(get_current_user)" in raw
    assert "Depends(require_admin)" in raw
    assert 'prefix="/v1/noteri"' in raw
    assert '@router.get("/profile")' in raw
    assert '@router.post("/profile")' in raw
    assert "correlation_id_mismatch" in raw


def test_workflow_is_inputless_pc24x7_only_and_no_production():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in raw
    assert "inputs:" not in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "environment: development" in raw
    assert "--confirm RECONCILE-NOTERI-STUDY-MODE-DEV" in raw
    assert "production_touched" in raw
    assert "secrets." not in raw


def test_workflow_reexecutes_when_gateway_or_runtime_contract_changes():
    raw = WORKFLOW.read_text(encoding="utf-8")
    for path in (
        "backend/app/api/monitoramento_operacional.py",
        "backend/app/api/noteri_host_profile.py",
        "backend/app/main.py",
        "docker-compose.dev.yml",
        "infra/nginx/default.dev.conf",
    ):
        assert f"- '{path}'" in raw


def test_policy_and_gateway_allow_only_fixed_reconcile_command():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert ".github/workflows/noteri-study-mode-dev-reconcile.yml" in policy["approved_workflows"]
    raw = GATEWAY.read_text(encoding="utf-8")
    assert "/reqsys run noteri-study-mode-dev-reconcile" in raw
    assert "target='noteri-study-mode-dev-reconcile.yml'" in raw
    assert "noteri-study-mode-dev-reconcile.yml" in raw


def test_reconciler_has_positive_negative_idempotency_and_restore_controls():
    raw = SCRIPT.read_text(encoding="utf-8")
    assert 'expected={401}' in raw
    assert '"profile": "ESTUDO"' in raw
    assert "estudo_idempotency_failed" in raw
    assert '"profile": "NORMAL"' in raw
    assert "NOTERI_CONTROL_PLANE_URL" in OVERLAY.read_text(encoding="utf-8")
    assert '"control_plane_bridge": True' in raw
    assert "rollback_files(changes)" in raw
    assert "loopback_agent_exposed" in raw


def test_http_e2e_failures_expose_only_safe_stage_and_status():
    err = module.ReconcileError(
        "http_unexpected",
        stage="api_admin_login",
        diagnostic_code="http_status_403",
    )
    assert err.code == "http_unexpected"
    assert err.stage == "api_admin_login"
    assert err.diagnostic_code == "http_status_403"

    raw = SCRIPT.read_text(encoding="utf-8")
    for stage in (
        "api_auth_config",
        "api_negative_auth_profile",
        "api_admin_login",
        "api_profile_before",
        "api_set_estudo",
        "api_estudo_readback",
        "api_estudo_replay",
        "api_restore_normal",
        "browser_admin_login",
    ):
        assert f'stage="{stage}"' in raw
    assert 'diagnostic_code=f"http_status_{status}"' in raw
    assert '"frontend_same_origin_source_ready"' in raw
    assert "response.read()" not in raw[raw.index("if status not in allowed:"):raw.index("return status, payload")]


def test_reconcile_failure_is_sanitized_and_stage_aware():
    err = module.ReconcileError("command_failed:docker:exit_1", stage="inspect_runtime")
    assert err.code == "command_failed:docker"
    assert err.stage == "inspect_runtime"

    raw = SCRIPT.read_text(encoding="utf-8")
    assert '"error_code"' in raw
    assert '"failure_stage"' in raw
    assert '"diagnostic_code"' in raw
    assert '"diagnostic_markers"' in raw
    assert 'str(exc)' not in raw


def test_compose_failure_diagnostic_is_allowlisted_and_secret_safe():
    cases = {
        "permission denied while trying to connect": "docker_permission_denied",
        "error during connect: docker engine is not running": "docker_daemon_unavailable",
        "env file C:\\secret\\runtime.env not found; TOKEN=should-not-leak": "compose_env_file_missing",
        "no configuration file provided: not found": "compose_config_file_missing",
        "service api has neither an image nor a build context specified": "compose_service_definition_incomplete",
        "invalid interpolation format for services.api.environment": "compose_interpolation_invalid",
        "required variable POSTGRES_PASSWORD is not set": "compose_required_environment_missing",
        "services.api Additional property bogus is not allowed": "compose_schema_invalid",
        "failed to read compose file: no such file or directory": "compose_file_read_failed",
        "some unknown docker compose failure TOKEN=should-not-leak": "compose_config_failed_unclassified",
    }
    for stderr, expected in cases.items():
        assert module.classify_command_failure(stderr, stage="compose_config") == expected
    assert module.classify_command_failure("permission denied", stage="api_recreate") is None

    assert module.classify_command_failure(
        'unexpected character "x" in variable name',
        stage="compose_config",
    ) == "compose_dotenv_parse_invalid"
    assert module.classify_command_failure(
        "unable to prepare context: build context does not exist",
        stage="compose_config",
    ) == "compose_build_context_invalid"
    assert module.classify_command_failure(
        "services must be a mapping",
        stage="compose_config",
    ) == "compose_schema_invalid"
    assert module.classify_command_failure(
        "yaml: mapping values are not allowed",
        stage="compose_config",
    ) == "compose_yaml_invalid"
    assert module.classify_command_failure(
        "project name must contain only lowercase letters",
        stage="compose_config",
    ) == "compose_project_name_invalid"
    assert module.classify_command_failure(
        "duplicate mount point /app",
        stage="compose_config",
    ) == "compose_mount_conflict"
    assert module.classify_command_failure(
        "CreateFile compose.yml: The system cannot find the file specified",
        stage="compose_config",
    ) == "compose_file_read_failed"

    markers = module.safe_command_failure_markers(
        "CreateFile compose.yml: The system cannot find the file specified",
        stage="compose_config",
    )
    assert markers == ("windows_file_missing", "createfile", "not_found")
    assert module.safe_command_failure_markers(
        "permission denied",
        stage="api_recreate",
    ) == ()


def test_reconciler_requires_live_binds_and_limits_compose_to_nginx_port_repair():
    raw = SCRIPT.read_text(encoding="utf-8")
    assert 'frontend_source = required_bind_source(' in raw
    assert 'stage="frontend_source_bind"' in raw
    assert 'nginx_bind = required_nginx_bind_source(nginx_before, project)' in raw
    assert 'expected_nginx_bind = (working_dir / NGINX_CONFIG).resolve()' not in raw
    assert 'frontend_source,\n        nginx_bind,\n        args.expected_sha' in raw
    assert '"compose_invoked": gateway_port_repaired' in raw
    assert '"bind_mounts_plus_api_restart_plus_nginx_bind_sync_reload"' in raw
    assert 'restart_container(api_container, repo_root, stage="api_restart")' in raw
    assert 'stage="rollback_api_restart"' in raw
    assert '["docker", "restart", container]' in raw
    assert 'direct_api_contract = wait_direct_api_contract()' in raw
    assert '"noteri_profile": "/v1/noteri/profile" in last_paths' in raw
    assert '"runtime_health": "/api/runtime/health" in last_paths' in raw
    assert '"direct_api_contract": direct_api_contract' in raw
    assert 'runtime_monitoring_module_missing' in raw
    assert 'app.include_router(monitoramento_operacional.router)' in raw
    assert 'nginx_rendered_contract = reload_nginx(' in raw
    assert 'container_host_port(nginx_before, "80/tcp") != DEV_GATEWAY_PORT' in raw
    assert '"gateway_8083_not_bound"' in raw


def test_gateway_probe_http_status_parser_is_sanitized_and_deterministic():
    rendered = """
Connecting to api:8000 (172.18.0.4:8000)
  HTTP/1.1 502 Bad Gateway
"""
    assert module._http_status_from_probe_output(rendered) == 502
    assert module._http_status_from_probe_output("connection refused") is None


def test_gateway_timeout_preserves_failing_path_and_last_status():
    with pytest.raises(module.ReconcileError) as exc:
        module.wait_gateway_status(
            "/api/runtime/health",
            {200},
            timeout_seconds=0,
        )

    assert exc.value.code == "gateway_status_timeout"
    assert exc.value.stage == "live_bind_refresh"
    assert exc.value.diagnostic_markers == ("runtime_health_not_observed",)
    assert exc.value.diagnostics == {
        "gateway_path": "/api/runtime/health",
        "gateway_last_http_status": None,
    }

    raw = SCRIPT.read_text(encoding="utf-8")
    assert "**dict(exc.diagnostics)" in raw


def test_gateway_failure_evidence_captures_four_independent_probes():
    raw = SCRIPT.read_text(encoding="utf-8")
    assert '"gateway_tcp_8083": probe_gateway_tcp()' in raw
    assert '"gateway_http_api_health": probe_gateway_http("/api/health")' in raw
    assert '"nginx_to_api_health": probe_nginx_upstream_api(container, repo_root)' in raw
    assert '"nginx_active_contract": probe_active_nginx_contract(container, repo_root)' in raw
    assert '"gateway_diagnostics"' in raw
    assert '"direct_api_contract_ready"' in raw
    assert '"nginx_contract_ready"' in raw
    assert "shell=False" in raw
    assert "str(exc)" not in raw


def test_reconciler_refreshes_nginx_runtime_contract_before_e2e():
    raw = SCRIPT.read_text(encoding="utf-8")
    nginx = NGINX_DEV.read_text(encoding="utf-8")
    assert 'NGINX_CONFIG = Path("infra/nginx/default.dev.conf")' in raw
    assert '["docker", "exec", container, "nginx", "-t"]' in raw
    assert '"cat",' in raw
    assert '"/etc/nginx/conf.d/default.conf"' in raw
    assert 'stage="nginx_bind_visibility"' in raw
    assert '["docker", "exec", container, "nginx", "-s", "reload"]' in raw
    assert 'stage_prefix="rollback_nginx_reload"' in raw
    assert 'require_contract=False' in raw
    assert 'refresh_nginx(' not in raw
    assert 'wait_direct_api_contract()' in raw
    assert 'stage="api_direct_contract"' in raw
    assert 'wait_gateway_status("/api/health", {200})' in raw
    assert 'wait_gateway_status("/api/runtime/health", {200})' in raw
    assert 'wait_gateway_status("/api/v1/noteri/profile", {401})' in raw
    assert '"nginx_runtime_contract_refreshed": True' in raw
    assert '"nginx_gateway_port_confirmed": True' in raw
    assert '"nginx_bind_visibility_confirmed": nginx_rendered_contract.get("bind_visible") is True' in raw
    assert '"nginx_rendered_contract": nginx_rendered_contract' in raw
    assert '"runtime_route": "location ~ ^/api/(runtime|" in observed' in raw
    assert '"api_prefix_route": "location /api/" in observed' in raw
    assert '"nginx_bind_not_visible"' in raw
    assert "location ~ ^/api/(runtime|" in nginx
    assert "proxy_pass http://api:8000;" in nginx
    assert '"runtime_health_not_observed"' in raw
    assert '"noteri_profile_not_observed"' in raw


def test_reconciler_discovers_compose_runtime_from_dev_api_port():
    raw = SCRIPT.read_text(encoding="utf-8")
    assert '["docker", "ps", "--filter", f"publish={DEV_API_PORT}", "--format", "{{.ID}}"]' in raw
    assert "com.docker.compose.project" in raw
    assert "com.docker.compose.service" in raw
    assert "non_dev_compose_project_blocked" in raw
    assert '"runtime_discovery": "api_port_8210_compose_labels"' in raw
    assert '"compose_invoked": gateway_port_repaired' in raw
    assert '"bind_mounts_plus_api_restart_plus_nginx_bind_sync_reload"' in raw
    assert "dev_api_8210_not_unique" in raw
    assert "dev_gateway_8083_not_unique" not in raw
    assert "reqsys-live-api-1" not in raw
    assert "reqsys-live-frontend-1" not in raw
    assert "reqsys-live-nginx-1" not in raw
