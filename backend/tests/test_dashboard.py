"""
Testes do Dashboard e endpoints de sistema
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    resp = client.post("/v1/auth/login", json={"email": "ericsonjosedossantos@tieri659.onmicrosoft.com"})
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /v1/dashboard/requisitos
# ---------------------------------------------------------------------------

class TestDashboardMetricas:
    def test_metricas_retorna_200(self, auth_headers):
        resp = client.get("/v1/dashboard/requisitos", headers=auth_headers)
        assert resp.status_code == 200

    def test_metricas_envelope_sucesso(self, auth_headers):
        resp = client.get("/v1/dashboard/requisitos", headers=auth_headers)
        assert resp.json()["success"] is True

    def test_metricas_campo_total(self, auth_headers):
        resp = client.get("/v1/dashboard/requisitos", headers=auth_headers)
        data = resp.json()["data"]
        assert "total" in data
        assert isinstance(data["total"], int)

    def test_metricas_campo_aprovados(self, auth_headers):
        resp = client.get("/v1/dashboard/requisitos", headers=auth_headers)
        data = resp.json()["data"]
        assert "aprovados" in data

    def test_metricas_campo_pendentes(self, auth_headers):
        resp = client.get("/v1/dashboard/requisitos", headers=auth_headers)
        data = resp.json()["data"]
        assert "pendentes" in data

    def test_metricas_endpoints_disponiveis(self, auth_headers):
        resp = client.get("/v1/dashboard/requisitos", headers=auth_headers)
        data = resp.json()["data"]
        assert "endpoints_disponiveis" in data
        assert isinstance(data["endpoints_disponiveis"], list)
        assert len(data["endpoints_disponiveis"]) > 0

    def test_metricas_credenciais_demo_presentes(self, auth_headers):
        resp = client.get("/v1/dashboard/requisitos", headers=auth_headers)
        data = resp.json()["data"]
        assert "credenciais_demo" in data
        assert "email" in data["credenciais_demo"]

    def test_metricas_total_nao_negativo(self, auth_headers):
        resp = client.get("/v1/dashboard/requisitos", headers=auth_headers)
        data = resp.json()["data"]
        assert data["total"] >= 0


# ---------------------------------------------------------------------------
# GET /v1/dashboard/info
# ---------------------------------------------------------------------------

class TestDashboardInfo:
    def test_info_retorna_200(self, auth_headers):
        resp = client.get("/v1/dashboard/info", headers=auth_headers)
        assert resp.status_code == 200

    def test_info_campo_timestamp(self, auth_headers):
        resp = client.get("/v1/dashboard/info", headers=auth_headers)
        data = resp.json()["data"]
        assert "timestamp" in data

    def test_info_campo_resumo(self, auth_headers):
        resp = client.get("/v1/dashboard/info", headers=auth_headers)
        data = resp.json()["data"]
        assert "resumo" in data
        assert "total_requisitos" in data["resumo"]

    def test_info_sistema_status_operacional(self, auth_headers):
        resp = client.get("/v1/dashboard/info", headers=auth_headers)
        data = resp.json()["data"]
        assert data["resumo"]["sistema_status"] == "operacional"


# ---------------------------------------------------------------------------
# GET /v1/sistema/info
# ---------------------------------------------------------------------------

class TestSistemaInfo:
    def test_sistema_info_retorna_200(self, auth_headers):
        resp = client.get("/v1/sistema/info", headers=auth_headers)
        assert resp.status_code == 200

    def test_sistema_info_envelope_sucesso(self, auth_headers):
        resp = client.get("/v1/sistema/info", headers=auth_headers)
        assert resp.json()["success"] is True

    def test_sistema_info_sem_headers_200(self):
        resp = client.get("/v1/sistema/info")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /v1/sistema/health-check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_health_check_retorna_200(self):
        resp = client.get("/v1/sistema/health-check")
        assert resp.status_code == 200

    def test_health_check_success_true(self):
        resp = client.get("/v1/sistema/health-check")
        assert resp.json()["success"] is True

    def test_health_check_sem_auth(self):
        resp = client.get("/v1/sistema/health-check")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /health (raiz)
# ---------------------------------------------------------------------------

class TestHealthRaiz:
    def test_health_raiz_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_raiz_success_true(self):
        resp = client.get("/health")
        assert resp.json()["success"] is True

