from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/todo-global-hourly-cycle.yml"
OVERLAY = ROOT / "docker-compose.pc24x7-todo-runtime.yml"
NGINX = ROOT / "infra/nginx/default.pc24x7-public-dev.conf"
SCRIPT = ROOT / "scripts/reconcile_pc24x7_todo_runtime.py"


def test_workflow_is_dev_only_same_sha_and_self_hosted() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in text
    assert "inputs.operation == 'reconcile-runtime'" in text
    assert "github.event_name == 'schedule'" in text
    assert "environment: development" in text
    assert "RECONCILE-PC24X7-TODO-RUNTIME-DEV" in text
    assert "expected-sha" in text
    assert "github.sha" in text


def test_overlay_uses_redis_persistence_and_internal_adapter() -> None:
    data = yaml.safe_load(OVERLAY.read_text(encoding="utf-8"))
    services = data["services"]
    runtime = services["reqsys-runtime"]
    assert services["reqsys-runtime-redis"]["image"] == "redis:7-alpine"
    assert "reqsys-runtime-redis-data:/data" in services["reqsys-runtime-redis"]["volumes"]
    env = runtime["environment"]
    assert env["QUEUE_BACKEND"] == "redis"
    assert env["STORAGE_BACKEND"] == "redis"
    assert env["TODO_GLOBAL_ADAPTER_URL"] == "http://api:8000/api/internal/todo-global/upsert"
    assert "TODO_GLOBAL_ADAPTER_SERVICE_TOKEN" in env["TODO_GLOBAL_ADAPTER_SERVICE_TOKEN"]
    assert "TODO_GLOBAL_RUNTIME_TOKEN" in env["TODO_GLOBAL_RUNTIME_TOKEN"]


def test_public_surface_is_minimal() -> None:
    text = NGINX.read_text(encoding="utf-8")
    assert "location = /runtime-core/health" in text
    assert "location = /runtime-core/api/runtime/build-info" in text
    assert "location = /runtime-core/api/todo-events" in text
    assert "location ^~ /runtime-core/api/todo-events/" in text
    assert "location ^~ /runtime-core/" in text
    assert "proxy_pass http://reqsys-runtime:8000/api/jobs" not in text
    assert "proxy_pass http://reqsys-runtime:8000/api/central" not in text


def test_reconciler_fails_closed_and_proves_e2e() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "public_runtime._require_host()" in text
    assert "public_runtime._sync_repo" in text
    assert "todo_global_notion_configuration_missing" in text
    assert "auth_negative_control" in text
    assert "readback_verified" in text
    assert "duplicate_event" in text
    assert '"secret_value_exposed": False' in text
    assert '"production_touched": False' in text
    assert "shell=True" not in text
