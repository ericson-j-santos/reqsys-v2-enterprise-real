from __future__ import annotations

import pytest

from app.core.config import Settings

_SECURE_SECRET = 'reqsys-ci-secret-with-at-least-thirty-two-characters'


def configure_secure_prod(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    """Define um baseline produtivo seguro e permite sobrescrever um gate por teste."""
    for key in [
        'APP_ENV',
        'ENVIRONMENT',
        'ALLOW_DEMO_LOGIN',
        'JWT_SECRET',
        'JWT_ISSUER',
        'JWT_AUDIENCE',
        'JWT_EXP_MINUTES',
        'CORS_ORIGINS',
        'AZURE_TENANT_ID',
        'AZURE_CLIENT_ID',
        'AZURE_CLIENT_SECRET',
    ]:
        monkeypatch.delenv(key, raising=False)

    values = {
        'APP_ENV': 'production',
        'ALLOW_DEMO_LOGIN': 'false',
        'JWT_SECRET': _SECURE_SECRET,
        'JWT_ISSUER': 'reqsys-api',
        'JWT_AUDIENCE': 'reqsys-frontend',
        'JWT_EXP_MINUTES': '60',
        'CORS_ORIGINS': 'https://tieriprod.duckdns.org',
        'AZURE_TENANT_ID': '00000000-0000-0000-0000-000000000000',
        'AZURE_CLIENT_ID': '11111111-1111-1111-1111-111111111111',
        'AZURE_CLIENT_SECRET': 'ci-placeholder-not-used-by-gate',
    }
    values.update({key: str(value) for key, value in overrides.items()})

    for key, value in values.items():
        monkeypatch.setenv(key, value)


def new_secure_prod_settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    configure_secure_prod(monkeypatch, **overrides)
    return Settings()


def assert_gate_blocks(monkeypatch: pytest.MonkeyPatch, expected_fragment: str, **overrides: str) -> None:
    settings = new_secure_prod_settings(monkeypatch, **overrides)
    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_production_gates()
    assert expected_fragment in str(exc_info.value)
