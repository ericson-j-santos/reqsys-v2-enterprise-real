"""
Gates de produção do ReqSys.

Este módulo centraliza validações que impedem a aplicação de subir em modo
produtivo com configurações inseguras. Ele evita acoplamento direto ao arquivo
de configuração e permite cobertura isolada em testes.
"""

from __future__ import annotations

import os
from typing import Iterable


_PRODUCTION_ENVS = {'prod', 'production'}
_WEAK_VALUES = {'', 'secret', 'changeme', 'trocar-em-producao', 'TROQUE-POR-UM-SEGREDO-FORTE-MINIMO-32-CHARS'}


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or '').split(',') if item.strip()]


def _setting(settings_obj, attr: str, env_name: str, default=None):
    value = getattr(settings_obj, attr, None)
    if value not in (None, ''):
        return value
    return os.getenv(env_name, default)


def _is_production(app_env: str | None) -> bool:
    return (app_env or '').strip().lower() in _PRODUCTION_ENVS


def validar_gates_producao(settings_obj) -> None:
    """Levanta RuntimeError quando houver configuração insegura em produção."""
    app_env = _setting(settings_obj, 'app_env', 'APP_ENV', 'development')
    if not _is_production(app_env):
        return

    violations: list[str] = []
    jwt_value = _setting(settings_obj, 'jwt_secret', 'JWT_SECRET', '')
    cors_values: Iterable[str] = getattr(settings_obj, 'cors_origins_list', _split_csv(os.getenv('CORS_ORIGINS', '')))
    jwt_issuer = _setting(settings_obj, 'jwt_issuer', 'JWT_ISSUER', '')
    jwt_audience = _setting(settings_obj, 'jwt_audience', 'JWT_AUDIENCE', '')

    if jwt_value in _WEAK_VALUES or len(jwt_value) < 32:
        violations.append('jwt_secret fraco ou ausente')
    if '*' in cors_values:
        violations.append('cors_origins não pode conter wildcard em produção')
    if not jwt_issuer:
        violations.append('jwt_issuer obrigatório em produção')
    if not jwt_audience:
        violations.append('jwt_audience obrigatório em produção')

    if violations:
        raise RuntimeError('Gates de produção bloqueados: ' + '; '.join(violations))
