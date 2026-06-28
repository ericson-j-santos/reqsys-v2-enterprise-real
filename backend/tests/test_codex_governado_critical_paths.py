"""Testes de caminhos críticos — API Codex Governado."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _auth_headers():
    login = client.post(
        "/v1/auth/login",
        json={"email": "ericsonjosedossantos@tieri659.onmicrosoft.com"},
    )
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Correlation-Id": "corr-codex-critical"}


def test_codex_status_expoe_guard_rails():
    res = client.get("/v1/codex/status", headers=_auth_headers())

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["servico"] == "codex-governado"
    assert "rate_limit" in data["guard_rails"]


def test_codex_operational_summary_retorna_dashboard():
    res = client.get("/v1/codex/operational-summary?limite=5", headers=_auth_headers())

    assert res.status_code == 200
    body = res.json()["data"]
    assert "dashboard" in body
    assert body["dashboard"]["total"] >= 0


def test_codex_analyze_sucesso_mock():
    resultado = {
        "bloqueado": False,
        "provider": "mock",
        "correlation_id": "corr-codex-critical",
        "score_confianca": 88,
    }
    with patch("app.api.codex_governado.analisar_governado", return_value=resultado):
        res = client.post(
            "/v1/codex/analyze",
            headers=_auth_headers(),
            json={
                "provider": "mock",
                "contexto": "validar endpoint",
                "entrada": "conteudo seguro para teste",
            },
        )

    assert res.status_code == 200
    assert res.json()["data"]["provider"] == "mock"


def test_codex_analyze_rate_limit_retorna_429():
    bloqueio = {"bloqueado": True, "motivo": "rate_limit", "retry_after_seconds": 45}
    with patch("app.api.codex_governado.analisar_governado", return_value=bloqueio):
        res = client.post(
            "/v1/codex/analyze",
            headers=_auth_headers(),
            json={
                "provider": "mock",
                "contexto": "validar rate limit",
                "entrada": "conteudo",
            },
        )

    assert res.status_code == 429
    assert res.headers.get("Retry-After") == "45"


def test_codex_analyze_conteudo_bloqueado_retorna_400():
    bloqueio = {"bloqueado": True, "motivo": "conteudo_sensivel", "achados": ["senha"]}
    with patch("app.api.codex_governado.analisar_governado", return_value=bloqueio):
        res = client.post(
            "/v1/codex/analyze",
            headers=_auth_headers(),
            json={
                "provider": "mock",
                "contexto": "validar bloqueio",
                "entrada": "texto com segredo",
            },
        )

    assert res.status_code == 400
