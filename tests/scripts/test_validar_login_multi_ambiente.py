import json

import pytest

from scripts.runtime_url_policy import RuntimeURLPolicyError
from scripts.validar_login_multi_ambiente import (
    LoginProbeResult,
    _probe_demo_login,
    build_payload,
    validate_environment_login,
)


def test_probe_demo_login_blocks_non_dev(monkeypatch):
    def fake_post(url, payload, timeout):
        return {"detail": "Login demo desabilitado neste ambiente"}, 403, None

    monkeypatch.setattr("scripts.validar_login_multi_ambiente._post_json", fake_post)
    result = _probe_demo_login("https://api.example.com", timeout=1.0, expect_allowed=False)
    assert result.ok is True
    assert result.status_code == 403


def test_probe_demo_login_allows_dev(monkeypatch):
    def fake_post(url, payload, timeout):
        return {"success": True, "data": {"access_token": "token-demo"}}, 200, None

    monkeypatch.setattr("scripts.validar_login_multi_ambiente._post_json", fake_post)
    result = _probe_demo_login("https://api.example.com", timeout=1.0, expect_allowed=True)
    assert result.ok is True
    assert result.has_token is True


def test_validate_environment_login_compara_redirect_uri_com_origem_publica(monkeypatch):
    chamadas = []

    def fake_validar_config(api_url, expected_redirect_uri):
        chamadas.append((api_url, expected_redirect_uri))
        return {"success": True, "errors": [], "warnings": []}

    monkeypatch.setattr("scripts.validar_login_multi_ambiente.validar_config", fake_validar_config)
    monkeypatch.setattr(
        "scripts.validar_login_multi_ambiente.validate_public_frontend",
        lambda frontend_url: {"success": True, "errors": []},
    )
    monkeypatch.setattr(
        "scripts.validar_login_multi_ambiente._probe_demo_login",
        lambda api_url, timeout, expect_allowed: LoginProbeResult(
            name='demo_login', ok=True, status_code=200,
        ),
    )

    validate_environment_login(
        'prod',
        {'api_url': 'https://api.prod.example', 'frontend_url': 'https://app.prod.example', 'app_env': 'production'},
        timeout=1.0,
    )

    assert chamadas == [('https://api.prod.example', 'https://app.prod.example')]


def test_build_payload_uses_manifest(monkeypatch, tmp_path):
    def fake_validate(env_name, cfg, *, timeout):
        return {
            "environment": env_name,
            "app_env": cfg["app_env"],
            "api_url": cfg["api_url"],
            "frontend_url": cfg["frontend_url"],
            "expect_demo_allowed": env_name == "dev",
            "operational_status": "ready",
            "login_ready": env_name != "prod",
            "checks": {},
            "errors": [] if env_name != "prod" else ["API indisponível"],
            "warnings": [],
        }

    monkeypatch.setattr("scripts.validar_login_multi_ambiente.validate_environment_login", fake_validate)
    manifest = tmp_path / "environments.json"
    manifest.write_text(
        json.dumps(
            {
                "canonical_environments": ["dev", "hml", "prod"],
                "environments": {
                    name: {
                        "api_url": f"https://api.{name}.example",
                        "frontend_url": f"https://app.{name}.example",
                        "app_env": "production" if name == "prod" else "development",
                    }
                    for name in ("dev", "hml", "prod")
                },
            }
        ),
        encoding="utf-8",
    )
    payload = build_payload(
        manifest_path=manifest,
        environment=None,
        timeout=1.0,
    )
    assert payload["summary"]["environments_total"] == 3
    assert payload["ok"] is False
    assert any("prod" in issue for issue in payload["blocking_issues"])


def test_validate_environment_login_rejects_fly_before_downstream_calls(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "scripts.validar_login_multi_ambiente.validar_config",
        lambda *_args, **_kwargs: calls.append("azure"),
    )

    with pytest.raises(RuntimeURLPolicyError, match="Fly.io"):
        validate_environment_login(
            "prod",
            {
                "api_url": "https://reqsys-api.fly.dev",
                "frontend_url": "https://app.prod.example",
                "app_env": "production",
            },
            timeout=1.0,
        )

    assert calls == []
