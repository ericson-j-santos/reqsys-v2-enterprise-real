"""
Testes de CRUD de Requisitos
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def auth_headers():
    resp = client.post("/v1/auth/login", json={"email": "ericsonjosedossantos@tieri659.onmicrosoft.com"})
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _payload(**kwargs):
    base = {
        "titulo": "Requisito de teste automatizado",
        "descricao": "Descrição detalhada do requisito criado em teste automatizado",
        "urgencia": "alta",
        "area": "TI",
        "sistema": "ReqSys",
        "solicitante": "pytest",
        "impacto_regulatorio": False,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# GET /v1/requisitos — listagem
# ---------------------------------------------------------------------------

class TestListarRequisitos:
    def test_listar_retorna_200(self, auth_headers):
        resp = client.get("/v1/requisitos", headers=auth_headers)
        assert resp.status_code == 200

    def test_listar_envelope_sucesso(self, auth_headers):
        resp = client.get("/v1/requisitos", headers=auth_headers)
        body = resp.json()
        assert body["success"] is True
        assert "data" in body

    def test_listar_retorna_lista(self, auth_headers):
        resp = client.get("/v1/requisitos", headers=auth_headers)
        assert isinstance(resp.json()["data"], list)

    def test_listar_sem_headers_ainda_200(self):
        """Endpoint não exige autenticação JWT no momento."""
        resp = client.get("/v1/requisitos")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /v1/requisitos — criação
# ---------------------------------------------------------------------------

class TestCriarRequisito:
    def test_criar_retorna_200(self, auth_headers):
        resp = client.post("/v1/requisitos", json=_payload(), headers=auth_headers)
        assert resp.status_code == 200

    def test_criar_envelope_sucesso(self, auth_headers):
        resp = client.post("/v1/requisitos", json=_payload(), headers=auth_headers)
        assert resp.json()["success"] is True

    def test_criar_retorna_id(self, auth_headers):
        resp = client.post("/v1/requisitos", json=_payload(), headers=auth_headers)
        data = resp.json()["data"]
        assert "id" in data
        assert isinstance(data["id"], int)
        assert data["id"] > 0

    def test_criar_retorna_codigo_req(self, auth_headers):
        resp = client.post("/v1/requisitos", json=_payload(), headers=auth_headers)
        codigo = resp.json()["data"]["codigo"]
        assert codigo.startswith("REQ-")

    def test_criar_titulo_persistido(self, auth_headers):
        titulo = "Título único para validação de persistência"
        resp = client.post("/v1/requisitos", json=_payload(titulo=titulo), headers=auth_headers)
        assert resp.json()["data"]["titulo"] == titulo

    def test_criar_area_persistida(self, auth_headers):
        resp = client.post("/v1/requisitos", json=_payload(area="Financeiro"), headers=auth_headers)
        assert resp.json()["data"]["area"] == "Financeiro"

    def test_criar_urgencia_alta(self, auth_headers):
        resp = client.post("/v1/requisitos", json=_payload(urgencia="alta"), headers=auth_headers)
        assert resp.json()["data"]["urgencia"] == "alta"

    def test_criar_impacto_regulatorio_true(self, auth_headers):
        resp = client.post("/v1/requisitos", json=_payload(impacto_regulatorio=True), headers=auth_headers)
        assert resp.json()["data"]["impacto_regulatorio"] is True

    def test_criar_com_correlation_id_header(self, auth_headers):
        headers = {**auth_headers, "x-correlation-id": "corr-req-001"}
        resp = client.post("/v1/requisitos", json=_payload(), headers=headers)
        assert resp.status_code == 200

    def test_criar_novo_requisito_aparece_na_listagem(self, auth_headers):
        titulo = "Requisito Rastreável Para Listagem"
        client.post("/v1/requisitos", json=_payload(titulo=titulo), headers=auth_headers)
        lista = client.get("/v1/requisitos", headers=auth_headers).json()["data"]
        titulos = [r["titulo"] for r in lista]
        assert titulo in titulos

    def test_criar_incrementa_total(self, auth_headers):
        total_antes = len(client.get("/v1/requisitos").json()["data"])
        client.post("/v1/requisitos", json=_payload(), headers=auth_headers)
        total_depois = len(client.get("/v1/requisitos").json()["data"])
        assert total_depois == total_antes + 1


# ---------------------------------------------------------------------------
# Validações de payload inválido
# ---------------------------------------------------------------------------

class TestCriarRequisitoInvalido:
    def test_titulo_muito_curto_retorna_422(self, auth_headers):
        resp = client.post("/v1/requisitos", json=_payload(titulo="abc"), headers=auth_headers)
        assert resp.status_code == 422

    def test_descricao_muito_curta_retorna_422(self, auth_headers):
        resp = client.post("/v1/requisitos", json=_payload(descricao="curta"), headers=auth_headers)
        assert resp.status_code == 422

    def test_payload_vazio_retorna_422(self, auth_headers):
        resp = client.post("/v1/requisitos", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_sem_campo_area_retorna_422(self, auth_headers):
        payload = _payload()
        del payload["area"]
        resp = client.post("/v1/requisitos", json=payload, headers=auth_headers)
        assert resp.status_code == 422

    def test_sem_campo_sistema_retorna_422(self, auth_headers):
        payload = _payload()
        del payload["sistema"]
        resp = client.post("/v1/requisitos", json=payload, headers=auth_headers)
        assert resp.status_code == 422

    def test_sem_campo_solicitante_retorna_422(self, auth_headers):
        payload = _payload()
        del payload["solicitante"]
        resp = client.post("/v1/requisitos", json=payload, headers=auth_headers)
        assert resp.status_code == 422

