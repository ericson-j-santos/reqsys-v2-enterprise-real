from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "collector" / "config.yaml").read_text(encoding="utf-8")
COMPOSE = (ROOT / "compose.collector.yml").read_text(encoding="utf-8")


def test_collector_has_health_queue_retry_and_internal_metrics() -> None:
    assert "health_check:" in CONFIG
    assert "endpoint: 0.0.0.0:13133" in CONFIG
    assert "file_storage:" in CONFIG
    assert "storage: file_storage" in CONFIG
    assert "sending_queue:" in CONFIG
    assert "retry_on_failure:" in CONFIG
    assert "max_elapsed_time: 300s" in CONFIG
    assert "port: 8888" in CONFIG


def test_collector_requires_explicit_upstream_and_environment() -> None:
    assert "${env:OTEL_UPSTREAM_ENDPOINT}" in CONFIG
    assert "${env:APP_ENV}" in CONFIG
    assert "deployment.environment.name" in CONFIG
    assert "OTEL_UPSTREAM_ENDPOINT: ${OTEL_UPSTREAM_ENDPOINT:?" in COMPOSE
    assert "APP_ENV: ${APP_ENV:-development}" in COMPOSE


def test_collector_is_hardened_and_queue_isolated_by_environment() -> None:
    assert "read_only: true" in COMPOSE
    assert "no-new-privileges:true" in COMPOSE
    assert "cap_drop:" in COMPOSE
    assert "- ALL" in COMPOSE
    assert "127.0.0.1:4317:4317" in COMPOSE
    assert "127.0.0.1:4318:4318" in COMPOSE
    assert "environment-observability-otel-queue-${APP_ENV:-development}" in COMPOSE


def test_collector_avoids_sensitive_resource_attributes() -> None:
    lowered = CONFIG.lower()
    forbidden = ("correlation_id", "authorization.resource", "cookie", "cpf", "email", "payload")
    for item in forbidden:
        assert item not in lowered
