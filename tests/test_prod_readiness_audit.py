from __future__ import annotations

import json
from pathlib import Path

from scripts import prod_readiness_audit as audit


def _auth_payload(redirect: str = "https://reqsys-app.fly.dev/auth/callback.html"):
    return {
        "success": True,
        "data": {
            "azure_enabled": True,
            "auth_status": "ready",
            "missing_fields": [],
            "expected_redirect_uri": redirect,
            "demo_login_enabled": False,
            "environment": "production",
        },
    }


def test_build_audit_ready_sem_fly_quando_smoke_publico_ok(monkeypatch):
    def fake_get_json(url: str, timeout: float):
        if url.endswith("/v1/auth/config"):
            return 200, _auth_payload(), None, 10
        return 200, {"status": "ok"}, None, 5

    monkeypatch.setattr(audit, "get_json", fake_get_json)

    report = audit.build_audit(
        "https://reqsys-api.fly.dev",
        "https://reqsys-app.fly.dev",
        "reqsys-api",
        timeout=1,
        check_fly=False,
    )

    assert report["blocked_count"] == 0
    assert any(c["id"] == "azure_redirect_uri" and c["status"] == "ok" for c in report["checks"])
    assert any(c["id"] == "fly_secrets_presence" and c["status"] == "manual" for c in report["checks"])


def test_build_audit_bloqueia_redirect_demo_e_smoke(monkeypatch):
    def fake_get_json(url: str, timeout: float):
        if url.endswith("/v1/auth/config"):
            payload = _auth_payload("https://reqsys-app.fly.dev")
            payload["data"]["demo_login_enabled"] = True
            return 200, payload, None, 10
        if url.endswith("/api/runtime/status"):
            return 503, None, "http_503", 12
        return 200, {"status": "ok"}, None, 5

    monkeypatch.setattr(audit, "get_json", fake_get_json)

    report = audit.build_audit(
        "https://reqsys-api.fly.dev",
        "https://reqsys-app.fly.dev",
        "reqsys-api",
        timeout=1,
        check_fly=False,
    )

    statuses = {c["id"]: c["status"] for c in report["checks"]}
    assert statuses["azure_redirect_uri"] == "action_required"
    assert statuses["auth_demo_disabled"] == "blocked"
    assert statuses["public_smoke"] == "blocked"
    assert report["status"] == "blocked"


def test_build_audit_valida_presenca_nominal_de_secrets(monkeypatch):
    monkeypatch.setattr(audit, "get_json", lambda url, timeout: (200, _auth_payload(), None, 1) if url.endswith("/v1/auth/config") else (200, {"status": "ok"}, None, 1))
    monkeypatch.setattr(audit, "fly_secret_names", lambda app: (set(audit.REQUIRED_SECRET_KEYS), None))

    report = audit.build_audit(
        "https://reqsys-api.fly.dev",
        "https://reqsys-app.fly.dev",
        "reqsys-api",
        timeout=1,
        check_fly=True,
    )

    assert any(c["id"] == "fly_secrets_presence" and c["status"] == "ok" for c in report["checks"])


def test_main_gera_json_e_markdown(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(audit, "build_audit", lambda *args, **kwargs: {"schema_version": "1.0.0", "source": "prod-readiness-audit", "validated_at": "2026-07-01T00:00:00Z", "status": "ready", "blocked_count": 0, "action_required_count": 0, "checks": []})
    output = tmp_path / "audit.json"
    markdown = tmp_path / "audit.md"

    code = audit.main(["--output", str(output), "--markdown-output", str(markdown), "--strict"])

    assert code == 0
    assert json.loads(output.read_text())["status"] == "ready"
    assert "Levantamento automatizado" in markdown.read_text(encoding="utf-8")
