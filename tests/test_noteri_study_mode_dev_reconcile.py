from __future__ import annotations

import importlib.util
import json
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


def test_reconciler_is_fixed_to_pc24x7_dev_and_reqsys_live():
    assert module.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert module.PROJECT == "reqsys-live"
    assert module.API_CONTAINER == "reqsys-live-api-1"
    assert module.FRONTEND_CONTAINER == "reqsys-live-frontend-1"
    assert module.NGINX_CONTAINER == "reqsys-live-nginx-1"
    assert module.GATEWAY == "http://127.0.0.1:8083"
    assert module.CONFIRM == "RECONCILE-NOTERI-STUDY-MODE-DEV"


def test_windows_path_normalizes_docker_desktop_mounts():
    assert str(module.windows_path("/run/desktop/mnt/host/c/dev/reqsys")).replace("\\", "/") == "C:/dev/reqsys"
    assert str(module.windows_path("/host_mnt/c/dev/reqsys")).replace("\\", "/") == "C:/dev/reqsys"


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
    assert 'str(exc)' not in raw


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
