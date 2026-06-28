"""Testes de caminhos críticos — envelope, telemetria e OpenTelemetry."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from app.core import otel as otel_module
from app.core.correlation import definir_correlation_id
from app.core.envelope import erro, ok
from app.core.otel import anotar_span_correlation, configurar_opentelemetry, otel_ativo
from app.core.telemetry import log_erro, log_evento, medir_operacao


@pytest.fixture(autouse=True)
def _reset_otel_state():
    otel_module._otel_configured = False
    yield
    otel_module._otel_configured = False


def test_envelope_ok_propaga_correlation_id_e_meta():
    definir_correlation_id("corr-envelope-ok")
    payload = ok({"valor": 1}, meta={"origem": "teste"})

    assert payload["success"] is True
    assert payload["data"] == {"valor": 1}
    assert payload["meta"]["correlation_id"] == "corr-envelope-ok"
    assert payload["meta"]["origem"] == "teste"


def test_envelope_erro_formata_codigo_e_mensagem():
    payload = erro("falha controlada", code="FALHA_TESTE", correlation_id="corr-envelope-erro")

    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["errors"] == [{"code": "FALHA_TESTE", "message": "falha controlada"}]
    assert payload["meta"]["correlation_id"] == "corr-envelope-erro"


def test_telemetry_log_evento_e_erro(caplog):
    definir_correlation_id("corr-telemetry-1")
    caplog.set_level(logging.INFO, logger="reqsys.telemetry")

    log_evento("operacao.teste", modulo="governance")
    log_erro("operacao.falhou", ValueError("detalhe"), modulo="governance")

    assert any("operacao.teste" in record.message for record in caplog.records)
    assert any("operacao.falhou" in record.message for record in caplog.records)


def test_telemetry_medir_operacao_sucesso_e_falha(caplog):
    caplog.set_level(logging.INFO, logger="reqsys.telemetry")

    with medir_operacao("job.critico", ambiente="test"):
        pass

    with pytest.raises(RuntimeError):
        with medir_operacao("job.critico", ambiente="test"):
            raise RuntimeError("falha simulada")

    started = [r for r in caplog.records if "job.critico.started" in r.message]
    completed = [r for r in caplog.records if "job.critico.completed" in r.message]
    failed = [r for r in caplog.records if "job.critico.failed" in r.message]

    assert started
    assert completed
    assert failed


def test_otel_desabilitado_nao_configura_tracing():
    app = FastAPI()

    assert configurar_opentelemetry(app) is False
    assert otel_ativo() is False
    anotar_span_correlation()


@patch("app.core.otel.settings")
def test_otel_habilitado_configura_com_console_exporter(mock_settings):
    mock_settings.otel_enabled = True
    mock_settings.otel_exporter_endpoint = ""
    mock_settings.otel_service_name = "reqsys-test"
    mock_settings.app_version = "test"
    mock_settings.normalized_environment = "test"
    app = FastAPI()

    assert configurar_opentelemetry(app) is True
    assert otel_ativo() is True


@patch("app.core.otel.settings")
def test_otel_anotar_span_correlation_quando_span_ativo(mock_settings):
    mock_settings.otel_enabled = True
    mock_settings.otel_exporter_endpoint = ""
    mock_settings.otel_service_name = "reqsys-test"
    mock_settings.app_version = "test"
    mock_settings.normalized_environment = "test"
    definir_correlation_id("corr-otel-span")
    app = FastAPI()
    configurar_opentelemetry(app)

    span = MagicMock()
    span.is_recording.return_value = True
    with patch("opentelemetry.trace.get_current_span", return_value=span):
        anotar_span_correlation()

    span.set_attribute.assert_called_once_with("reqsys.correlation_id", "corr-otel-span")


@patch("app.core.otel.settings")
def test_otel_anotar_span_correlation_ignora_excecao(mock_settings):
    mock_settings.otel_enabled = True
    mock_settings.otel_exporter_endpoint = ""
    mock_settings.otel_service_name = "reqsys-test"
    mock_settings.app_version = "test"
    mock_settings.normalized_environment = "test"
    app = FastAPI()
    configurar_opentelemetry(app)

    with patch("opentelemetry.trace.get_current_span", side_effect=RuntimeError("span indisponível")):
        anotar_span_correlation()


@patch("app.core.otel.settings")
def test_otel_habilitado_usa_exporter_otlp_quando_configurado(mock_settings):
    mock_settings.otel_enabled = True
    mock_settings.otel_exporter_endpoint = "http://otel-collector:4318/v1/traces"
    mock_settings.otel_service_name = "reqsys-test"
    mock_settings.app_version = "test"
    mock_settings.normalized_environment = "test"
    app = FastAPI()

    with patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter") as exporter_cls:
        exporter_cls.return_value = MagicMock()
        assert configurar_opentelemetry(app) is True

    exporter_cls.assert_called_once_with(endpoint=mock_settings.otel_exporter_endpoint)
