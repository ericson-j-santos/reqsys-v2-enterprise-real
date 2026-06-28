"""Testes de caminhos críticos — autenticação Azure PKCE e helpers."""

from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.api.auth import _nome_from_email, _papel_from_email
from app.main import app

client = TestClient(app)


def test_papel_from_email_admin_e_analista():
    assert _papel_from_email("ericsonjosedossantos@empresa.com") == "admin"
    assert _papel_from_email("joao.silva@empresa.com") == "analista"


def test_nome_from_email_composto_e_mapeado():
    assert _nome_from_email("ericsonjosedossantos@empresa.com") == "Ericson Santos"
    assert _nome_from_email("maria.souza@empresa.com") == "Maria Souza"
    assert _nome_from_email("unico@empresa.com") == "Unico"


def test_demo_login_bloqueado_em_producao():
    from app.core.config import settings

    original_env = settings.app_environment
    original_demo = settings.allow_demo_login
    settings.app_environment = "production"
    settings.allow_demo_login = True
    try:
        res = client.post("/v1/auth/login", json={"email": "test@example.com"})
        assert res.status_code == 403
    finally:
        settings.app_environment = original_env
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
            "upn": "ericsonjosedossantos@tieri659.onmicrosoft.com",
            "name": "Ericson Santos",
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
    finally:
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client
