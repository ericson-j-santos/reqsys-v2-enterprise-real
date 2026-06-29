from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validar_login_multi_ambiente import _probe_demo_login, build_payload


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
