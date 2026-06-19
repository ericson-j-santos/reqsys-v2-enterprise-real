"""
Testes dos gates bloqueantes de produção.

Esses testes garantem que a API não suba em modo produtivo quando houver
configuração insegura de autenticação, CORS ou claims JWT obrigatórias.
"""

from types import SimpleNamespace

import pytest

from app.core.production_gates import validar_gates_producao


def _settings(**overrides):
    base = {
        'app_env': 'production',
        'jwt_secret': 'segredo-forte-com-mais-de-32-caracteres',
        'cors_origins_list': ['https://reqsys-app.fly.dev'],
        'jwt_issuer': 'reqsys-api',
        'jwt_audience': 'reqsys-web',
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_gates_nao_bloqueiam_fora_de_producao():
    validar_gates_producao(_settings(app_env='development', jwt_secret='fraco', cors_origins_list=['*']))


def test_gates_aprovam_configuracao_produtiva_segura():
    validar_gates_producao(_settings())


def test_gates_bloqueiam_jwt_fraco_em_producao():
    with pytest.raises(RuntimeError, match='jwt_secret fraco'):
        validar_gates_producao(_settings(jwt_secret='fraco'))


def test_gates_bloqueiam_cors_wildcard_em_producao():
    with pytest.raises(RuntimeError, match='cors_origins'):
        validar_gates_producao(_settings(cors_origins_list=['*']))


def test_gates_bloqueiam_claims_jwt_obrigatorias_ausentes():
    with pytest.raises(RuntimeError, match='jwt_issuer'):
        validar_gates_producao(_settings(jwt_issuer=''))

    with pytest.raises(RuntimeError, match='jwt_audience'):
        validar_gates_producao(_settings(jwt_audience=''))
