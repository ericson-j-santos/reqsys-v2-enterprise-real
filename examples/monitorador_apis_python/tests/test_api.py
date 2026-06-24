from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import app


client = TestClient(app)


def test_health_deve_retornar_ok():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "monitorador-apis-python"
    assert payload["version"] == "1.1.0"
    assert "checked_at" in payload


def test_home_deve_retornar_html():
    response = client.get("/")

    assert response.status_code == 200
    assert "Monitorador de APIs Python" in response.text
    assert "/dashboard" in response.text
    assert "/docs" in response.text


def test_resultados_deve_retornar_lista():
    response = client.get("/api/resultados?limite=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["limite"] == 5
    assert "resultados" in payload


def test_resultados_deve_normalizar_limite_minimo():
    response = client.get("/api/resultados?limite=0")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["limite"] == 1


def test_resultados_deve_normalizar_limite_maximo():
    response = client.get("/api/resultados?limite=999")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["limite"] == 100


def test_monitorar_deve_retornar_resultados_mockados(monkeypatch):
    async def executar_mock(apis):
        assert apis
        return [
            SimpleNamespace(
                nome="API Teste",
                url="https://example.com/health",
                status_code=200,
                sucesso=True,
                tempo_resposta_ms=42.5,
                status_operacional="ok",
                erro=None,
                consultado_em=datetime(2026, 1, 1, 12, 0, 0),
            )
        ]

    monkeypatch.setattr("app.api.service.executar", executar_mock)

    response = client.get("/api/monitorar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["total"] == 1
    assert payload["resultados"][0]["nome"] == "API Teste"
    assert payload["resultados"][0]["sucesso"] is True
    assert payload["resultados"][0]["status_operacional"] == "ok"


def test_dashboard_deve_retornar_html_gerado(monkeypatch, tmp_path):
    async def executar_mock(apis):
        assert apis
        return []

    def gerar_relatorio_mock(resultados, caminho):
        assert resultados == []
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text("<html><body>Dashboard Mockado</body></html>", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app.api.service.executar", executar_mock)
    monkeypatch.setattr("app.api.gerar_relatorio_html", gerar_relatorio_mock)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Dashboard Mockado" in response.text
