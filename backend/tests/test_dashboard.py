"""
Testes do Dashboard e endpoints de sistema
"""
from datetime import datetime
from base64 import b64encode

import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core import secrets as secrets_module
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

    def test_metricas_soma_consistente_com_total(self, auth_headers):
        resp = client.get("/v1/dashboard/requisitos", headers=auth_headers)
        data = resp.json()["data"]
        soma = data["em_analise"] + data["aprovados"] + data.get("rejeitados", 0) + data["pendentes"]
        assert soma == data["total"]


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

    def test_info_timestamp_timezone_utc(self, auth_headers):
        resp = client.get("/v1/dashboard/info", headers=auth_headers)
        data = resp.json()["data"]
        parsed = datetime.fromisoformat(data["timestamp"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0

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

    def test_health_check_timestamp_timezone_utc(self):
        resp = client.get("/v1/sistema/health-check")
        data = resp.json()["data"]
        parsed = datetime.fromisoformat(data["timestamp"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0

    def test_health_check_sem_auth(self):
        resp = client.get("/v1/sistema/health-check")
        assert resp.status_code == 200


class _FakeKeyring:
    def __init__(self):
        self._store = {}

    def get_password(self, service, username):
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        self._store[(service, username)] = password


def _put_vault_secret(fake_keyring, service, key, value):
    raw_master_key = fake_keyring.get_password(service, secrets_module._MASTER_KEY_SLOT)
    if raw_master_key:
        from base64 import b64decode
        master_key = b64decode(raw_master_key)
    else:
        master_key = AESGCM.generate_key(bit_length=256)
        fake_keyring.set_password(service, secrets_module._MASTER_KEY_SLOT, b64encode(master_key).decode())
    nonce = b'0' * secrets_module._NONCE_BYTES
    blob = AESGCM(master_key).encrypt(nonce, value.encode(), None)
    fake_keyring.set_password(service, key, b64encode(nonce + blob).decode())


class TestSistemaSegredosStatus:
    def test_segredos_status_retorna_200(self):
        resp = client.get('/v1/sistema/segredos-status')
        assert resp.status_code == 200

    def test_segredos_status_envelope_sucesso(self):
        resp = client.get('/v1/sistema/segredos-status')
        assert resp.json()['success'] is True

    def test_segredos_status_nao_expoe_valores(self):
        resp = client.get('/v1/sistema/segredos-status')
        segredo = resp.json()['data']['segredos'][0]
        assert 'value' not in segredo
        assert segredo['value_exposed'] is False

    def test_segredo_mostra_fonte_env(self, monkeypatch):
        monkeypatch.setenv('JWT_SECRET', 'jwt-from-env')
        resp = client.get('/v1/sistema/segredos-status')
        segredos = resp.json()['data']['segredos']
        jwt = next(item for item in segredos if item['name'] == 'JWT_SECRET')
        assert jwt['source'] == 'env'

    def test_segredo_mostra_fonte_vault(self, monkeypatch):
        fake_keyring = _FakeKeyring()
        monkeypatch.setattr(secrets_module, 'keyring', fake_keyring)
        monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
        monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
        monkeypatch.delenv('GITHUB_TOKEN', raising=False)
        _put_vault_secret(fake_keyring, 'mvp-intelligence-vault', 'GITHUB_TOKEN', 'gh-vault-token')

        resp = client.get('/v1/sistema/segredos-status')
        segredos = resp.json()['data']['segredos']
        token = next(item for item in segredos if item['name'] == 'GITHUB_TOKEN')
        assert token['source'] == 'vault'

    def test_segredo_mostra_fonte_default(self, monkeypatch):
        monkeypatch.delenv('SSRS_REQUIRE_HTTPS', raising=False)
        resp = client.get('/v1/sistema/segredos-status')
        segredos = resp.json()['data']['segredos']
        item = next(entry for entry in segredos if entry['name'] == 'SSRS_REQUIRE_HTTPS')
        assert item['source'] == 'default'


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

