"""Caminhos críticos — OpenTelemetry bootstrap."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import app.core.otel as module
from app.core.otel import anotar_span_correlation, configurar_opentelemetry, otel_ativo


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
