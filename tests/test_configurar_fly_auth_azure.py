from __future__ import annotations

from argparse import Namespace

from scripts import configurar_fly_auth_azure as modulo


def _args(**overrides) -> Namespace:
    base = dict(
        app_public_url="https://reqsys-app.fly.dev",
        api_public_url="https://reqsys-api.fly.dev",
        validation_attempts=1,
        validation_interval_seconds=0,
    )
    base.update(overrides)
    return Namespace(**base)


def _payload(expected_redirect_uri: str) -> dict:
    return {
        "success": True,
        "data": {
            "azure_enabled": True,
            "auth_status": "ready",
            "missing_fields": [],
            "expected_redirect_uri": expected_redirect_uri,
        },
    }


def test_validar_aceita_redirect_uri_com_sufixo_callback(monkeypatch):
    monkeypatch.setattr(
        modulo,
        "_get_json",
        lambda url: _payload("https://reqsys-app.fly.dev/auth/callback.html"),
    )

    resultado = modulo.validar(_args())

    assert resultado["success"] is True


def test_validar_rejeita_redirect_uri_sem_callback_ou_divergente(monkeypatch):
    monkeypatch.setattr(
        modulo,
        "_get_json",
        lambda url: _payload("https://reqsys-app.fly.dev"),
    )

    resultado = modulo.validar(_args())

    assert resultado["success"] is False
