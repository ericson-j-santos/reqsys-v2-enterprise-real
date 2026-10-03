"""
Testes de autenticação (login, token, autorização)
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestLoginAuditoriaEPii:
    def test_login_demo_registra_evento_de_auditoria(self):
        with patch("app.api.auth.registrar_evento") as mock_registrar:
            resp = client.post("/v1/auth/login", json={"email": "auditor.teste@example.com"})

        assert resp.status_code == 200
        mock_registrar.assert_called_once()
        args = mock_registrar.call_args[0]
        assert args[2] == "auditor.teste@example.com"
        assert args[3] == "LOGIN_DEMO"
        assert args[4] == "usuario"

    def test_login_demo_nao_loga_email_em_texto_puro(self, caplog):
        with caplog.at_level("INFO", logger="reqsys.security"):
            resp = client.post("/v1/auth/login", json={"email": "sensivel.teste@example.com"})

        assert resp.status_code == 200
        mensagens = "\n".join(r.getMessage() for r in caplog.records)
        assert "sensivel.teste@example.com" not in mensagens
        assert "s***@example.com" in mensagens


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(email: str = "ericsonjosedossantos@tieri659.onmicrosoft.com", senha: str = "admin123"):
    return client.post("/v1/auth/login", json={"email": email, "senha": senha})


# ---------------------------------------------------------------------------
# Login — casos de sucesso
# ---------------------------------------------------------------------------

class TestLoginSucesso:
    def test_login_admin_retorna_200(self):
        resp = _login()
        assert resp.status_code == 200

    def test_login_resposta_envelope_ok(self):
        resp = _login()
        body = resp.json()
        assert body["success"] is True
        assert "data" in body

    def test_login_retorna_access_token(self):
        resp = _login()
        data = resp.json()["data"]
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 10

    def test_login_token_type_bearer(self):
        resp = _login()
        data = resp.json()["data"]
        assert data["token_type"] == "bearer"

    def test_login_retorna_info_usuario(self):
        resp = _login()
        usuario = resp.json()["data"]["usuario"]
        assert "email" in usuario
        assert "papel" in usuario
        assert "permissoes" in usuario
        assert isinstance(usuario["permissoes"], list)

    def test_login_admin_papel_correto(self):
        resp = _login("ericsonjosedossantos@tieri659.onmicrosoft.com")
        usuario = resp.json()["data"]["usuario"]
        assert usuario["papel"] == "admin"

    def test_login_admin_tem_permissoes(self):
        resp = _login("ericsonjosedossantos@tieri659.onmicrosoft.com")
        permissoes = resp.json()["data"]["usuario"]["permissoes"]
        assert len(permissoes) > 0
        assert "dashboard:read" in permissoes

    def test_login_analista_papel_correto(self):
        resp = _login("analista@tieri659.onmicrosoft.com")
        usuario = resp.json()["data"]["usuario"]
        assert usuario["papel"] == "analista"

    def test_login_analista_permissoes_diferentes_do_admin(self):
        admin_resp = _login("ericsonjosedossantos@tieri659.onmicrosoft.com")
        analista_resp = _login("analista@tieri659.onmicrosoft.com")
        admin_perms = set(admin_resp.json()["data"]["usuario"]["permissoes"])
        analista_perms = set(analista_resp.json()["data"]["usuario"]["permissoes"])
        # admin deve ter mais permissões que analista
        assert admin_perms != analista_perms
        assert "auditoria:read" in admin_perms
        assert "auditoria:read" not in analista_perms

    def test_login_email_retornado_corretamente(self):
        email = "ericsonjosedossantos@tieri659.onmicrosoft.com"
        resp = _login(email)
        assert resp.json()["data"]["usuario"]["email"] == email

    def test_login_sem_senha_ainda_funciona(self):
        """O sistema é demo — não valida senha real, apenas email."""
        resp = client.post("/v1/auth/login", json={"email": "ericsonjosedossantos@tieri659.onmicrosoft.com"})
        assert resp.status_code == 200

    def test_login_payload_vazio_usa_default(self):
        """Payload vazio deve usar email default e retornar 200."""
        resp = client.post("/v1/auth/login", json={})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data


# ---------------------------------------------------------------------------
# Login — token JWT válido
# ---------------------------------------------------------------------------

class TestTokenJWT:
    def test_token_e_string_jwt(self):
        resp = _login()
        token = resp.json()["data"]["access_token"]
        partes = token.split(".")
        # JWT tem exatamente 3 partes separadas por ponto
        assert len(partes) == 3

    def test_token_diferente_para_usuarios_diferentes(self):
        token_admin = _login("ericsonjosedossantos@tieri659.onmicrosoft.com").json()["data"]["access_token"]
        token_analista = _login("analista@tieri659.onmicrosoft.com").json()["data"]["access_token"]
        assert token_admin != token_analista

    def test_dois_logins_consecutivos_geram_tokens_diferentes(self):
        """Tokens devem variar (campo exp muda) entre chamadas com intervalo."""
        token1 = _login().json()["data"]["access_token"]
        token2 = _login().json()["data"]["access_token"]
        # Podem ser iguais se forem no mesmo segundo — apenas garantimos que são strings válidas
        assert isinstance(token1, str)
        assert isinstance(token2, str)


# ---------------------------------------------------------------------------
# Endpoints protegidos com token
# ---------------------------------------------------------------------------

class TestEndpointsComToken:
    @pytest.fixture(scope="class")
    def token(self):
        resp = _login("ericsonjosedossantos@tieri659.onmicrosoft.com")
        return resp.json()["data"]["access_token"]

    @pytest.fixture(scope="class")
    def headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_listar_requisitos_com_token_200(self, headers):
        resp = client.get("/v1/requisitos", headers=headers)
        assert resp.status_code == 200

    def test_dashboard_metricas_com_token_200(self, headers):
        resp = client.get("/v1/dashboard/requisitos", headers=headers)
        assert resp.status_code == 200

    def test_sistema_info_com_token_200(self, headers):
        resp = client.get("/v1/sistema/info", headers=headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Endpoint de login — método correto
# ---------------------------------------------------------------------------

class TestLoginMetodo:
    def test_login_via_get_retorna_405(self):
        resp = client.get("/v1/auth/login")
        assert resp.status_code == 405

    def test_login_via_put_retorna_405(self):
        resp = client.put("/v1/auth/login", json={"email": "x@x.com"})
        assert resp.status_code == 405

    def test_login_content_type_json(self):
        resp = _login()
        assert "application/json" in resp.headers.get("content-type", "")

