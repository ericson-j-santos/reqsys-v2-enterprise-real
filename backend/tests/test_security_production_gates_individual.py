from __future__ import annotations

from security_gate_helpers import assert_gate_blocks, new_secure_prod_settings


def test_gate_prod_bloqueia_jwt_secret_fraco(monkeypatch):
    assert_gate_blocks(monkeypatch, 'JWT_SECRET', JWT_SECRET='segredo-fraco')


def test_gate_prod_bloqueia_cors_wildcard(monkeypatch):
    assert_gate_blocks(monkeypatch, 'CORS_ORIGINS', CORS_ORIGINS='*')


def test_gate_prod_exige_jwt_issuer(monkeypatch):
    assert_gate_blocks(monkeypatch, 'JWT_ISSUER', JWT_ISSUER='')


def test_gate_prod_exige_jwt_audience(monkeypatch):
    assert_gate_blocks(monkeypatch, 'JWT_AUDIENCE', JWT_AUDIENCE='')


def test_gate_prod_bloqueia_login_demo(monkeypatch):
    assert_gate_blocks(monkeypatch, 'ALLOW_DEMO_LOGIN', ALLOW_DEMO_LOGIN='true')


def test_gate_prod_bloqueia_jwt_exp_minutes_zero(monkeypatch):
    assert_gate_blocks(monkeypatch, 'JWT_EXP_MINUTES', JWT_EXP_MINUTES='0')


def test_gate_prod_bloqueia_jwt_exp_minutes_negativo(monkeypatch):
    assert_gate_blocks(monkeypatch, 'JWT_EXP_MINUTES', JWT_EXP_MINUTES='-1')


def test_gate_prod_configuracao_segura_nao_falha(monkeypatch):
    settings = new_secure_prod_settings(monkeypatch)
    settings.validate_production_gates()
    assert settings.is_production is True
    assert settings.is_jwt_secret_weak is False
