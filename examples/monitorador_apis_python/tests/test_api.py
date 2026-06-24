from fastapi.testclient import TestClient

from app.api import app


client = TestClient(app)


def test_health_deve_retornar_ok():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "monitorador-apis-python"


def test_home_deve_retornar_html():
    response = client.get("/")

    assert response.status_code == 200
    assert "Monitorador de APIs Python" in response.text
    assert "/dashboard" in response.text


def test_resultados_deve_retornar_lista():
    response = client.get("/api/resultados?limite=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["limite"] == 5
    assert "resultados" in payload
