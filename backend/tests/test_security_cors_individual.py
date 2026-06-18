from __future__ import annotations

from security_gate_helpers import assert_gate_blocks, new_secure_prod_settings


def test_gate_cors_asterisco_em_producao_falha_individualmente(monkeypatch):
    assert_gate_blocks(monkeypatch, 'CORS_ORIGINS não pode conter *', CORS_ORIGINS='*')


def test_gate_cors_origem_explicita_em_producao_eh_aceita(monkeypatch):
    settings = new_secure_prod_settings(monkeypatch, CORS_ORIGINS='https://tieriprod.duckdns.org')
    settings.validate_production_gates()
    assert settings.cors_origins_list == ['https://tieriprod.duckdns.org']
