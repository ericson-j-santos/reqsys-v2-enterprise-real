from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "sitecustomize.py"


def load_module(monkeypatch, **environment):
    for name in (
        "OTEL_TRACING_ENABLED",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "SERVICE_NAME",
        "APP_ENV",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("service_sitecustomize", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_telemetry_is_disabled_by_default(monkeypatch) -> None:
    module = load_module(monkeypatch)
    assert module.OTEL_CONFIGURED is False


def test_telemetry_requires_explicit_endpoint(monkeypatch) -> None:
    module = load_module(monkeypatch, OTEL_TRACING_ENABLED="true")
    assert module.OTEL_CONFIGURED is False


def test_invalid_exporter_configuration_does_not_break_startup(monkeypatch) -> None:
    module = load_module(
        monkeypatch,
        OTEL_TRACING_ENABLED="true",
        OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="not-a-valid-endpoint",
    )
    assert isinstance(module.OTEL_CONFIGURED, bool)
