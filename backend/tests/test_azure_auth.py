"""Testes automatizados para o fluxo de autenticação Azure AD."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ─── GET /v1/auth/config ──────────────────────────────────────────────────────

class TestAuthConfig:
    def test_config_retorna_200(self):
        r = client.get('/v1/auth/config')
        assert r.status_code == 200

    def test_config_envelope_sucesso(self):
        r = client.get('/v1/auth/config')
        assert r.json()['success'] is True

    def test_config_tem_campo_azure_enabled(self):
        r = client.get('/v1/auth/config')
        data = r.json()['data']
        assert 'azure_enabled' in data

    def test_config_sem_client_id_azure_disabled(self):
        """Sem AZURE_CLIENT_ID configurado, azure_enabled deve ser False."""
        from app.core.config import settings
        original = settings.azure_client_id
        settings.azure_client_id = ''
        try:
            r = client.get('/v1/auth/config')
            assert r.json()['data']['azure_enabled'] is False
        finally:
            settings.azure_client_id = original

    def test_config_nao_exige_autenticacao(self):
        """Endpoint público — não deve exigir JWT."""
        r = client.get('/v1/auth/config', headers={})
        assert r.status_code == 200


# ─── POST /v1/auth/login (demo) ───────────────────────────────────────────────

class TestLoginDemo:
    def test_login_demo_200(self):
        r = client.post('/v1/auth/login', json={'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'})
        assert r.status_code == 200

    def test_login_demo_retorna_token(self):
        r = client.post('/v1/auth/login', json={'email': 'test@example.com'})
        assert 'access_token' in r.json()['data']

    def test_login_demo_nome_derivado_do_email(self):
        r = client.post('/v1/auth/login', json={'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'})
        assert r.json()['data']['usuario']['nome'] == 'Ericson Santos'

    def test_login_demo_papel_admin(self):
        r = client.post('/v1/auth/login', json={'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'})
        assert r.json()['data']['usuario']['papel'] == 'admin'

    def test_login_demo_papel_analista_para_email_comum(self):
        r = client.post('/v1/auth/login', json={'email': 'joao.silva@empresa.com'})
        assert r.json()['data']['usuario']['papel'] == 'analista'

    def test_login_demo_permissoes_admin_nao_vazias(self):
        r = client.post('/v1/auth/login', json={'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'})
        assert len(r.json()['data']['usuario']['permissoes']) > 0

    def test_login_demo_dashboard_read_em_permissoes_admin(self):
        r = client.post('/v1/auth/login', json={'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'})
        assert 'dashboard:read' in r.json()['data']['usuario']['permissoes']


# ─── POST /v1/auth/azure ─────────────────────────────────────────────────────

class TestLoginAzure:
    def test_azure_sem_configuracao_retorna_503(self):
        """Sem AZURE_CLIENT_ID, endpoint retorna 503."""
        from app.core.config import settings
        original_tenant = settings.azure_tenant_id
        original_client = settings.azure_client_id
        settings.azure_tenant_id = ''
        settings.azure_client_id = ''
        try:
            r = client.post('/v1/auth/azure', json={'id_token': 'qualquer'})
            assert r.status_code == 503
        finally:
            settings.azure_tenant_id = original_tenant
            settings.azure_client_id = original_client

    def test_azure_token_invalido_retorna_401(self):
        """Token mal-formado deve retornar 401."""
        from app.core.config import settings
        if not settings.azure_client_id:
            pytest.skip('AZURE_CLIENT_ID não configurado')
        r = client.post('/v1/auth/azure', json={'id_token': 'token.invalido.aqui'})
        assert r.status_code == 401

    def test_azure_token_vazio_retorna_422(self):
        """Payload sem id_token deve retornar 422 (validação Pydantic)."""
        r = client.post('/v1/auth/azure', json={})
        assert r.status_code == 422

    def test_azure_token_valido_com_mock(self):
        """Simula token Azure válido usando mock do validador."""
        from app.core.config import settings
        if not settings.azure_client_id:
            pytest.skip('AZURE_CLIENT_ID não configurado')

        claims_mock = {
            'sub': 'abc-123',
            'upn': 'ericsonjosedossantos@tieri659.onmicrosoft.com',
            'name': 'Ericson Santos',
            'aud': settings.azure_client_id,
        }
        with patch('app.api.auth.validar_token_azure', return_value=claims_mock):
            r = client.post('/v1/auth/azure', json={'id_token': 'mock.token.valido'})
        assert r.status_code == 200
        data = r.json()['data']
        assert 'access_token' in data
        assert data['usuario']['nome'] == 'Ericson Santos'
        assert data['usuario']['email'] == 'ericsonjosedossantos@tieri659.onmicrosoft.com'
        assert data['usuario']['papel'] == 'admin'

    def test_azure_token_valido_retorna_permissoes(self):
        """Token válido deve retornar permissões do papel."""
        from app.core.config import settings
        if not settings.azure_client_id:
            pytest.skip('AZURE_CLIENT_ID não configurado')

        claims_mock = {
            'sub': 'xyz',
            'upn': 'analista@tieri659.onmicrosoft.com',
            'name': 'Ana Silva',
        }
        with patch('app.api.auth.validar_token_azure', return_value=claims_mock):
            r = client.post('/v1/auth/azure', json={'id_token': 'mock.token'})
        assert r.status_code == 200
        assert 'dashboard:read' in r.json()['data']['usuario']['permissoes']


# ─── Serviço azure_auth.py ───────────────────────────────────────────────────

class TestAzureAuthService:
    def test_extrair_usuario_usa_upn(self):
        from app.services.azure_auth import extrair_usuario
        claims = {'upn': 'user@tieri659.onmicrosoft.com', 'name': 'User Test'}
        result = extrair_usuario(claims)
        assert result['email'] == 'user@tieri659.onmicrosoft.com'
        assert result['nome'] == 'User Test'

    def test_extrair_usuario_fallback_preferred_username(self):
        from app.services.azure_auth import extrair_usuario
        claims = {'preferred_username': 'fallback@tieri659.onmicrosoft.com', 'name': 'Fallback'}
        result = extrair_usuario(claims)
        assert result['email'] == 'fallback@tieri659.onmicrosoft.com'

    def test_extrair_usuario_sem_nome_deriva_do_email(self):
        from app.services.azure_auth import extrair_usuario
        claims = {'upn': 'joao.silva@tieri659.onmicrosoft.com'}
        result = extrair_usuario(claims)
        assert result['email'] == 'joao.silva@tieri659.onmicrosoft.com'
        assert result['nome']  # Não deve ser vazio

    def test_validar_token_azure_token_malformado(self):
        from app.services.azure_auth import validar_token_azure
        with pytest.raises(ValueError, match='inválido|invalid|não reconhecido'):
            validar_token_azure('nao.e.um.jwt.valido', 'tenant-id', 'client-id')
