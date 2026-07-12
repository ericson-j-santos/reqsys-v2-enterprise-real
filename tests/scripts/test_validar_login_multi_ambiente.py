import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

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


def test_validate_environment_login_compara_redirect_uri_com_sufixo_callback(monkeypatch):
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
        {'api_url': 'https://reqsys-api.fly.dev', 'frontend_url': 'https://reqsys-app.fly.dev', 'app_env': 'production'},
        timeout=1.0,
    )

    assert chamadas == [('https://reqsys-api.fly.dev', 'https://reqsys-app.fly.dev/auth/callback.html')]


def test_validate_environment_login_usa_demo_login_publicado_quando_dev_desabilita_demo(monkeypatch):
    expect_allowed_calls = []

    monkeypatch.setattr(
        "scripts.validar_login_multi_ambiente.validar_config",
        lambda api_url, expected_redirect_uri: {
            "success": True,
            "errors": [],
            "warnings": [],
            "data": {"demo_login_enabled": False},
        },
    )
    monkeypatch.setattr(
        "scripts.validar_login_multi_ambiente.validate_public_frontend",
        lambda frontend_url: {"success": True, "errors": []},
    )

    def fake_probe(api_url, timeout, expect_allowed):
        expect_allowed_calls.append(expect_allowed)
        return LoginProbeResult(name="demo_login", ok=True, status_code=403)

    monkeypatch.setattr("scripts.validar_login_multi_ambiente._probe_demo_login", fake_probe)

    result = validate_environment_login(
        "dev",
        {
            "api_url": "https://reqsys-api-dev.fly.dev",
            "frontend_url": "https://reqsys-app-dev.fly.dev",
            "app_env": "development",
        },
        timeout=1.0,
    )

    assert result["login_ready"] is True
    assert expect_allowed_calls == [False]
    assert any("demo_login_enabled está false em desenvolvimento" in warning for warning in result["warnings"])


def test_build_payload_uses_manifest(monkeypatch):
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
    payload = build_payload(
        manifest_path=ROOT / "infra" / "fly-environments.json",
        environment=None,
        timeout=1.0,
    )
    assert payload["summary"]["environments_total"] == 3
    assert payload["ok"] is False
    assert any("prod" in issue for issue in payload["blocking_issues"])
