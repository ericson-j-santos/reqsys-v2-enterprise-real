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
    assert module.CONFIRM == "RECONCILE-NOTERI-STUDY-MODE-DEV"


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


def test_reconciler_rebuilds_frontend_when_runtime_bind_is_absent():
    raw = SCRIPT.read_text(encoding="utf-8")
    assert 'frontend_bind_source = rw_bind_source(frontend_before, "/app")' in raw
    assert 'frontend_source = frontend_bind_source or (working_dir / "frontend")' in raw
    assert 'stage="frontend_rebuild"' in raw
    assert '"--build"' in raw
    assert 'stage="rollback_frontend_rebuild"' in raw


def test_reconciler_refreshes_nginx_runtime_contract_before_e2e():
    raw = SCRIPT.read_text(encoding="utf-8")
    nginx = NGINX_DEV.read_text(encoding="utf-8")
    assert 'NGINX_CONFIG = Path("infra/nginx/default.dev.conf")' in raw
    assert 'stage="nginx_recreate"' in raw
    assert 'stage="rollback_nginx_recreate"' in raw
    assert 'http_json("GET", "/api/health")' in raw
    assert 'http_json("GET", "/api/runtime/health")' in raw
    assert '"nginx_runtime_contract_refreshed": True' in raw
    assert "location ~ ^/api/(runtime|" in nginx
    assert "proxy_pass http://api:8000;" in nginx


def test_reconciler_discovers_compose_runtime_from_dev_api_port():
    raw = SCRIPT.read_text(encoding="utf-8")
    assert '["docker", "ps", "--filter", f"publish={DEV_API_PORT}", "--format", "{{.ID}}"]' in raw
    assert "com.docker.compose.project" in raw
    assert "com.docker.compose.service" in raw
    assert "non_dev_compose_project_blocked" in raw
    assert '"runtime_discovery": "api_port_8210_compose_labels"' in raw
    assert '"compose_environment_files_preserved": bool(compose_environment_files)' in raw
    assert "com.docker.compose.project.environment_file" in raw
    assert "dev_api_8210_not_unique" in raw
    assert "dev_gateway_8083_not_unique" not in raw
    assert "reqsys-live-api-1" not in raw
    assert "reqsys-live-frontend-1" not in raw
    assert "reqsys-live-nginx-1" not in raw
