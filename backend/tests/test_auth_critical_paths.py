"""Testes de caminhos críticos — autenticação Azure PKCE e helpers."""

from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.api.auth import _nome_from_email
from app.main import app
from app.services.role_resolution import resolver_papel

client = TestClient(app)


def test_resolvedor_papel_binding_admin_e_fallback_analista():
    def segredo(nome, default=''):
        if nome == 'REQSYS_ROLE_BINDINGS':
            return '{"admin.teste@example.com":"admin"}'
        return default

    with patch('app.services.role_resolution.get_secret', side_effect=segredo):
        assert resolver_papel('ADMIN.TESTE@example.com').papel == 'admin'
        assert resolver_papel('joao.silva@empresa.com').papel == 'analista'


def test_nome_from_email_composto_e_mapeado():
    assert _nome_from_email("ericsonjosedossantos@empresa.com") == "Ericson Santos"
    assert _nome_from_email("maria.souza@empresa.com") == "Maria Souza"
    assert _nome_from_email("unico@empresa.com") == "Unico"


def test_demo_login_bloqueado_em_producao():
    from app.core.config import settings

    original_env = settings.app_environment
    original_public_env = settings.public_environment
    original_demo = settings.allow_demo_login
    settings.app_environment = "production"
    settings.public_environment = "production"
    settings.allow_demo_login = True
    try:
        res = client.post("/v1/auth/login", json={"email": "test@example.com"})
        assert res.status_code == 403
    finally:
        settings.app_environment = original_env
        settings.public_environment = original_public_env
        settings.allow_demo_login = original_demo


def test_azure_code_sem_configuracao_retorna_503():
    from app.core.config import settings

    original_tenant = settings.azure_tenant_id
    original_client = settings.azure_client_id
    settings.azure_tenant_id = ""
    settings.azure_client_id = ""
    try:
        res = client.post(
            "/v1/auth/azure-code",
            json={"code": "c", "verifier": "v", "redirectUri": "https://app.example/callback"},
        )
        assert res.status_code == 503
    finally:
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client


def test_azure_code_falha_rede_retorna_502():
    from app.core.config import settings

    original_tenant = settings.azure_tenant_id
    original_client = settings.azure_client_id
    settings.azure_tenant_id = "tenant-teste"
    settings.azure_client_id = "client-teste"
    try:
        with patch("app.api.auth.httpx.post", side_effect=httpx.RequestError("timeout")):
            res = client.post(
                "/v1/auth/azure-code",
                json={"code": "c", "verifier": "v", "redirectUri": "https://app.example/callback"},
            )
        assert res.status_code == 502
    finally:
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client


def test_azure_code_exchange_falho_retorna_401():
    from app.core.config import settings

    original_tenant = settings.azure_tenant_id
    original_client = settings.azure_client_id
    settings.azure_tenant_id = "tenant-teste"
    settings.azure_client_id = "client-teste"
    try:
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.json.return_value = {"error_description": "code expirado"}
        mock_response.text = "code expirado"

        with patch("app.api.auth.httpx.post", return_value=mock_response):
            res = client.post(
                "/v1/auth/azure-code",
                json={"code": "c", "verifier": "v", "redirectUri": "https://app.example/callback"},
            )
        assert res.status_code == 401
    finally:
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client


def test_azure_code_sem_id_token_retorna_401():
    from app.core.config import settings

    original_tenant = settings.azure_tenant_id
    original_client = settings.azure_client_id
    settings.azure_tenant_id = "tenant-teste"
    settings.azure_client_id = "client-teste"
    try:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"access_token": "sem-id-token"}

        with patch("app.api.auth.httpx.post", return_value=mock_response):
            res = client.post(
                "/v1/auth/azure-code",
                json={"code": "c", "verifier": "v", "redirectUri": "https://app.example/callback"},
            )
        assert res.status_code == 401
    finally:
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client


def test_azure_code_sucesso_com_mock():
    from app.core.config import settings

    original_tenant = settings.azure_tenant_id
    original_client = settings.azure_client_id
    settings.azure_tenant_id = "tenant-teste"
    settings.azure_client_id = "client-teste"
    try:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"id_token": "mock.id.token"}

        claims_mock = {
            "sub": "pkce-user",
            "upn": "usuario.admin@example.com",
            "name": "Usuario Admin",
            "roles": ["ReqSys.Admin"],
        }
        with patch("app.api.auth.httpx.post", return_value=mock_response):
            with patch("app.api.auth.validar_token_azure", return_value=claims_mock):
                res = client.post(
                    "/v1/auth/azure-code",
                    json={"code": "c", "verifier": "v", "redirectUri": "https://app.example/callback"},
                )

        assert res.status_code == 200
        data = res.json()["data"]
        assert data["usuario"]["papel"] == "admin"
        assert data["usuario"]["role_source"] == "entra_app_role"
        assert "access_token" in data
    finally:
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client


def test_login_azure_sucesso_com_mock():
    from app.core.config import settings

    original_tenant = settings.azure_tenant_id
    original_client = settings.azure_client_id
    settings.azure_tenant_id = "tenant-teste"
    settings.azure_client_id = "client-teste"
    try:
        claims_mock = {
            "sub": "azure-user",
            "upn": "analista@tieri659.onmicrosoft.com",
            "name": "Ana Silva",
        }
        with patch("app.api.auth.validar_token_azure", return_value=claims_mock):
            res = client.post("/v1/auth/azure", json={"id_token": "mock.token.valido"})

        assert res.status_code == 200
        data = res.json()["data"]
        assert data["usuario"]["email"] == "analista@tieri659.onmicrosoft.com"
        assert data["usuario"]["papel"] == "analista"
        assert data["usuario"]["role_source"] == "default_fail_closed"
    finally:
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client
