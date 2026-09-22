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

spec = importlib.util.spec_from_file_location("noteri_study_mode_dev_reconcile", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reconciler_is_fixed_to_noteri_dev_and_reqsys_live():
    assert module.EXPECTED_HOST == "Noteri"
    assert module.PROJECT == "reqsys-live"
    assert module.API_CONTAINER == "reqsys-live-api-1"
    assert module.FRONTEND_CONTAINER == "reqsys-live-frontend-1"
    assert module.NGINX_CONTAINER == "reqsys-live-nginx-1"
    assert module.GATEWAY == "http://127.0.0.1:8083"
    assert module.CONFIRM == "RECONCILE-NOTERI-STUDY-MODE-DEV"


def test_windows_path_normalizes_docker_desktop_mounts():
    assert str(module.windows_path("/run/desktop/mnt/host/c/dev/reqsys")).replace("\\", "/") == "C:/dev/reqsys"
    assert str(module.windows_path("/host_mnt/c/dev/reqsys")).replace("\\", "/") == "C:/dev/reqsys"


def test_overlay_mounts_only_canonical_noteri_profile_into_api():
    raw = OVERLAY.read_text(encoding="utf-8")
    assert "NOTERI_HOST_PROFILE_PATH=/noteri-runtime/host-profile.json" in raw
    assert "NOTERI_HOST_PROFILE_AUDIT_PATH=/noteri-runtime/host-profile-api-audit.jsonl" in raw
    assert "NOTERI_HOST_PROFILE_EXPECTED_HOST=Noteri" in raw
    assert "TodoGlobal24x7" in raw
    assert "target: /noteri-runtime" in raw
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


def test_workflow_is_inputless_noteri_only_and_no_production():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in raw
    assert "inputs:" not in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
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
    assert 'read_profile_file(profile_path, "ESTUDO")' in raw
    assert 'read_profile_file(profile_path, "NORMAL")' in raw
    assert "rollback_files(changes)" in raw
    assert "loopback_agent_exposed" in raw
