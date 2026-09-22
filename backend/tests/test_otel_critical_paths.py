"""Caminhos críticos — OpenTelemetry bootstrap."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import app.core.otel as module
from app.core.otel import (
    _signal_endpoint,
    anotar_span_correlation,
    configurar_opentelemetry,
    otel_ativo,
    registrar_http_metricas,
)


def test_configurar_opentelemetry_desabilitado_quando_flag_off(monkeypatch):
    monkeypatch.setattr(module, '_otel_configured', False)
    monkeypatch.setattr(module.settings, 'otel_enabled', False)
    app = MagicMock()
    assert configurar_opentelemetry(app) is False
    assert otel_ativo() is False


def test_configurar_opentelemetry_retorna_true_quando_ja_configurado(monkeypatch):
    monkeypatch.setattr(module, '_otel_configured', True)
    monkeypatch.setattr(module.settings, 'otel_enabled', True)
    assert configurar_opentelemetry(MagicMock()) is True


def test_configurar_opentelemetry_import_error_desativa_tracing(monkeypatch):
    monkeypatch.setattr(module, '_otel_configured', False)
    monkeypatch.setattr(module.settings, 'otel_enabled', True)
    with patch.dict('sys.modules', {'opentelemetry': None}):
        with patch('builtins.__import__', side_effect=ImportError('missing otel')):
            assert configurar_opentelemetry(MagicMock()) is False


def test_anotar_span_correlation_noop_quando_otel_inativo(monkeypatch):
    monkeypatch.setattr(module, '_otel_configured', False)
    anotar_span_correlation()


def test_anotar_span_correlation_define_atributo(monkeypatch):
    monkeypatch.setattr(module, '_otel_configured', True)
    span = MagicMock()
    span.is_recording.return_value = True
    fake_trace = MagicMock()
    fake_trace.get_current_span.return_value = span
    with patch.dict('sys.modules', {'opentelemetry': MagicMock(trace=fake_trace)}):
        with patch('opentelemetry.trace', fake_trace, create=True):
            anotar_span_correlation()
    span.set_attribute.assert_called_once()


def test_signal_endpoint_normaliza_base_e_signal_path():
    assert _signal_endpoint('http://collector:4318', 'traces') == 'http://collector:4318/v1/traces'
    assert _signal_endpoint('http://collector:4318/v1/traces', 'metrics') == 'http://collector:4318/v1/metrics'
    assert _signal_endpoint('http://collector:4318/v1/metrics/', 'traces') == 'http://collector:4318/v1/traces'


def test_registrar_http_metricas_noop_quando_inativo(monkeypatch):
    monkeypatch.setattr(module, '_otel_configured', False)
    registrar_http_metricas(method='GET', route='/health', status_code=200, duration_ms=5)


def test_registrar_http_metricas_registra_counter_e_histograma(monkeypatch):
    counter = MagicMock()
    histogram = MagicMock()
    monkeypatch.setattr(module, '_otel_configured', True)
    monkeypatch.setattr(module, '_http_request_counter', counter)
    monkeypatch.setattr(module, '_http_duration_histogram', histogram)

    registrar_http_metricas(
        method='get',
        route='/api/requisitos/{codigo}',
        status_code=200,
        duration_ms=12.4,
    )

    attributes = {
        'http.request.method': 'GET',
        'http.route': '/api/requisitos/{codigo}',
        'http.response.status_code': 200,
    }
    counter.add.assert_called_once_with(1, attributes)
    histogram.record.assert_called_once_with(12.4, attributes)
