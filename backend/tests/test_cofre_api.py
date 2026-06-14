"""Testes de integração para os endpoints REST do cofre (app/api/cofre.py)."""
from __future__ import annotations

from base64 import b64encode

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

from app.core import secrets as secrets_module
from app.core.config import settings as _settings
from app.main import app

SVC = 'test-api-vault'

client = TestClient(app)
ADMIN_EMAIL = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
ANALISTA_EMAIL = 'analista@tieri659.onmicrosoft.com'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeKeyring:
    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._store.pop((service, username), None)


def _token(email: str) -> str:
    resp = client.post('/v1/auth/login', json={'email': email})
    return resp.json()['data']['access_token']


def _admin_headers() -> dict[str, str]:
    return {'Authorization': f'Bearer {_token(ADMIN_EMAIL)}'}


def _vault_patch(monkeypatch) -> _FakeKeyring:
    """Injeta FakeKeyring e define service name isolado. Retorna o fake."""
    fk = _FakeKeyring()
    monkeypatch.setattr(secrets_module, 'keyring', fk)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
    monkeypatch.setenv('REQSYS_VAULT_SERVICE_NAME', SVC)
    return fk


def _setup_vault_secret(fk: _FakeKeyring, key: str, value: str) -> None:
    """Inicializa vault e insere segredo diretamente no FakeKeyring."""
    master_key = AESGCM.generate_key(bit_length=256)
    fk.set_password(SVC, secrets_module._MASTER_KEY_SLOT, b64encode(master_key).decode())
    nonce = b'\x00' * secrets_module._NONCE_BYTES
    blob = AESGCM(master_key).encrypt(nonce, value.encode(), None)
    fk.set_password(SVC, key, b64encode(nonce + blob).decode())


# ---------------------------------------------------------------------------
# POST /v1/cofre/init
# ---------------------------------------------------------------------------

class TestCofreInit:
    def test_sem_jwt_retorna_401(self):
        resp = client.post('/v1/cofre/init')
        assert resp.status_code == 401

    def test_analista_bloqueado_403(self):
        headers = {'Authorization': f'Bearer {_token(ANALISTA_EMAIL)}'}
        resp = client.post('/v1/cofre/init', headers=headers)
        assert resp.status_code == 403

    def test_admin_inicializa_com_sucesso(self, monkeypatch):
        _vault_patch(monkeypatch)
        resp = client.post('/v1/cofre/init', headers=_admin_headers())
        assert resp.status_code == 200
        assert resp.json()['success'] is True
        assert resp.json()['data']['status'] == 'inicializado'

    def test_service_name_retornado_na_resposta(self, monkeypatch):
        _vault_patch(monkeypatch)
        resp = client.post('/v1/cofre/init', headers=_admin_headers())
        assert resp.json()['data']['service'] == SVC

    def test_segunda_chamada_retorna_ja_inicializado(self, monkeypatch):
        _vault_patch(monkeypatch)
        h = _admin_headers()
        client.post('/v1/cofre/init', headers=h)
        resp = client.post('/v1/cofre/init', headers=h)
        assert resp.json()['data']['status'] == 'ja_inicializado'

    def test_overwrite_true_reinicializa(self, monkeypatch):
        _vault_patch(monkeypatch)
        h = _admin_headers()
        client.post('/v1/cofre/init', headers=h)
        resp = client.post('/v1/cofre/init?overwrite=true', headers=h)
        assert resp.json()['data']['status'] == 'inicializado'


# ---------------------------------------------------------------------------
# GET /v1/cofre/status
# ---------------------------------------------------------------------------

class TestCofreStatus:
    def test_sem_jwt_retorna_401(self):
        resp = client.get('/v1/cofre/status')
        assert resp.status_code == 401

    def test_analista_bloqueado_403(self):
        headers = {'Authorization': f'Bearer {_token(ANALISTA_EMAIL)}'}
        resp = client.get('/v1/cofre/status', headers=headers)
        assert resp.status_code == 403

    def test_status_nao_inicializado(self, monkeypatch):
        _vault_patch(monkeypatch)
        resp = client.get('/v1/cofre/status', headers=_admin_headers())
        assert resp.status_code == 200
        assert resp.json()['data']['inicializado'] is False

    def test_status_inicializado_apos_init(self, monkeypatch):
        _vault_patch(monkeypatch)
        h = _admin_headers()
        client.post('/v1/cofre/init', headers=h)
        resp = client.get('/v1/cofre/status', headers=h)
        data = resp.json()['data']
        assert data['inicializado'] is True
        assert data['service'] == SVC

    def test_status_contem_flag_vault_api_token(self, monkeypatch):
        _vault_patch(monkeypatch)
        resp = client.get('/v1/cofre/status', headers=_admin_headers())
        assert 'vault_api_token_configurado' in resp.json()['data']


# ---------------------------------------------------------------------------
# POST /v1/cofre/segredos
# ---------------------------------------------------------------------------

class TestCofreGravarSegredo:
    def test_sem_jwt_retorna_401(self):
        resp = client.post('/v1/cofre/segredos', json={'key': 'K', 'value': 'V'})
        assert resp.status_code == 401

    def test_grava_com_sucesso(self, monkeypatch):
        _vault_patch(monkeypatch)
        h = _admin_headers()
        client.post('/v1/cofre/init', headers=h)
        resp = client.post('/v1/cofre/segredos', json={'key': 'MINHA_KEY', 'value': 'meu-valor'}, headers=h)
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['key'] == 'MINHA_KEY'
        assert data['gravado'] is True

    def test_chave_reservada_retorna_422(self):
        resp = client.post('/v1/cofre/segredos', json={'key': '__master_key__', 'value': 'x'}, headers=_admin_headers())
        assert resp.status_code == 422

    def test_chave_vazia_retorna_422(self):
        resp = client.post('/v1/cofre/segredos', json={'key': '', 'value': 'x'}, headers=_admin_headers())
        assert resp.status_code == 422

    def test_chave_so_espacos_retorna_422(self):
        resp = client.post('/v1/cofre/segredos', json={'key': '   ', 'value': 'x'}, headers=_admin_headers())
        assert resp.status_code == 422

    def test_value_vazio_retorna_422(self):
        resp = client.post('/v1/cofre/segredos', json={'key': 'K', 'value': ''}, headers=_admin_headers())
        assert resp.status_code == 422

    def test_vault_nao_inicializado_retorna_400(self, monkeypatch):
        _vault_patch(monkeypatch)
        resp = client.post('/v1/cofre/segredos', json={'key': 'KEY', 'value': 'val'}, headers=_admin_headers())
        assert resp.status_code == 400
        assert 'não inicializado' in resp.json()['detail']

    def test_chave_stripped_no_retorno(self, monkeypatch):
        _vault_patch(monkeypatch)
        h = _admin_headers()
        client.post('/v1/cofre/init', headers=h)
        resp = client.post('/v1/cofre/segredos', json={'key': '  PADDED_KEY  ', 'value': 'val'}, headers=h)
        assert resp.json()['data']['key'] == 'PADDED_KEY'


# ---------------------------------------------------------------------------
# DELETE /v1/cofre/segredos/{key}
# ---------------------------------------------------------------------------

class TestCofreRemoverSegredo:
    def test_sem_jwt_retorna_401(self):
        resp = client.delete('/v1/cofre/segredos/ALGUMA_CHAVE')
        assert resp.status_code == 401

    def test_chave_reservada_retorna_400(self):
        resp = client.delete('/v1/cofre/segredos/__master_key__', headers=_admin_headers())
        assert resp.status_code == 400
        assert 'reservada' in resp.json()['detail']

    def test_remove_chave_existente(self, monkeypatch):
        _vault_patch(monkeypatch)
        h = _admin_headers()
        client.post('/v1/cofre/init', headers=h)
        client.post('/v1/cofre/segredos', json={'key': 'DEL_KEY', 'value': 'val'}, headers=h)
        resp = client.delete('/v1/cofre/segredos/DEL_KEY', headers=h)
        assert resp.status_code == 200
        assert resp.json()['data']['removido'] is True

    def test_chave_inexistente_removido_false(self, monkeypatch):
        _vault_patch(monkeypatch)
        resp = client.delete('/v1/cofre/segredos/NAO_EXISTE', headers=_admin_headers())
        assert resp.status_code == 200
        assert resp.json()['data']['removido'] is False

    def test_key_retornado_na_resposta(self, monkeypatch):
        _vault_patch(monkeypatch)
        resp = client.delete('/v1/cofre/segredos/MINHA_CHAVE', headers=_admin_headers())
        assert resp.json()['data']['key'] == 'MINHA_CHAVE'


# ---------------------------------------------------------------------------
# POST /v1/cofre/resolver
# ---------------------------------------------------------------------------

class TestCofreResolver:
    TOKEN = 'vault-token-de-teste-seguro'

    def test_sem_x_vault_token_retorna_401(self, monkeypatch):
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        resp = client.post('/v1/cofre/resolver', json={'key': 'K'})
        assert resp.status_code == 401

    def test_token_errado_retorna_401(self, monkeypatch):
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        resp = client.post('/v1/cofre/resolver', json={'key': 'K'}, headers={'X-Vault-Token': 'errado'})
        assert resp.status_code == 401

    def test_vault_api_token_nao_configurado_retorna_503(self, monkeypatch):
        monkeypatch.setattr(_settings, 'vault_api_token', '')
        resp = client.post('/v1/cofre/resolver', json={'key': 'K'}, headers={'X-Vault-Token': 'qualquer'})
        assert resp.status_code == 503

    def test_chave_reservada_retorna_400(self, monkeypatch):
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        resp = client.post(
            '/v1/cofre/resolver',
            json={'key': '__master_key__'},
            headers={'X-Vault-Token': self.TOKEN},
        )
        assert resp.status_code == 400

    def test_chave_inexistente_retorna_404(self, monkeypatch):
        fk = _vault_patch(monkeypatch)
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        resp = client.post(
            '/v1/cofre/resolver',
            json={'key': 'NAO_EXISTE'},
            headers={'X-Vault-Token': self.TOKEN},
        )
        assert resp.status_code == 404

    def test_retorna_valor_descriptografado(self, monkeypatch):
        fk = _vault_patch(monkeypatch)
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        _setup_vault_secret(fk, 'SEGREDO_TESTE', 'valor-secreto')

        resp = client.post(
            '/v1/cofre/resolver',
            json={'key': 'SEGREDO_TESTE'},
            headers={'X-Vault-Token': self.TOKEN},
        )
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['key'] == 'SEGREDO_TESTE'
        assert data['value'] == 'valor-secreto'

    def test_resposta_nao_expoe_outros_campos(self, monkeypatch):
        fk = _vault_patch(monkeypatch)
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        _setup_vault_secret(fk, 'SEGREDO_CAMPO', 'val')

        resp = client.post(
            '/v1/cofre/resolver',
            json={'key': 'SEGREDO_CAMPO'},
            headers={'X-Vault-Token': self.TOKEN},
        )
        data = resp.json()['data']
        assert set(data.keys()) == {'key', 'value'}


# ---------------------------------------------------------------------------
# GET /v1/cofre/segredos/{key}
# ---------------------------------------------------------------------------

class TestCofreGetSegredo:
    TOKEN = 'vault-token-get-teste'

    def test_sem_x_vault_token_retorna_401(self, monkeypatch):
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        resp = client.get('/v1/cofre/segredos/QUALQUER_KEY')
        assert resp.status_code == 401

    def test_token_errado_retorna_401(self, monkeypatch):
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        resp = client.get('/v1/cofre/segredos/KEY', headers={'X-Vault-Token': 'errado'})
        assert resp.status_code == 401

    def test_vault_api_token_nao_configurado_retorna_503(self, monkeypatch):
        monkeypatch.setattr(_settings, 'vault_api_token', '')
        resp = client.get('/v1/cofre/segredos/KEY', headers={'X-Vault-Token': 'qualquer'})
        assert resp.status_code == 503

    def test_chave_reservada_retorna_400(self, monkeypatch):
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        resp = client.get('/v1/cofre/segredos/__master_key__', headers={'X-Vault-Token': self.TOKEN})
        assert resp.status_code == 400

    def test_chave_inexistente_retorna_404(self, monkeypatch):
        _vault_patch(monkeypatch)
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        resp = client.get('/v1/cofre/segredos/NAO_EXISTE', headers={'X-Vault-Token': self.TOKEN})
        assert resp.status_code == 404

    def test_retorna_valor_descriptografado(self, monkeypatch):
        fk = _vault_patch(monkeypatch)
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        _setup_vault_secret(fk, 'DB_PASSWORD', 'senha-super-secreta')

        resp = client.get('/v1/cofre/segredos/DB_PASSWORD', headers={'X-Vault-Token': self.TOKEN})
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['key'] == 'DB_PASSWORD'
        assert data['value'] == 'senha-super-secreta'

    def test_resposta_contem_apenas_key_e_value(self, monkeypatch):
        fk = _vault_patch(monkeypatch)
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        _setup_vault_secret(fk, 'API_KEY', 'tok123')

        resp = client.get('/v1/cofre/segredos/API_KEY', headers={'X-Vault-Token': self.TOKEN})
        assert set(resp.json()['data'].keys()) == {'key', 'value'}

    def test_equivalente_ao_post_resolver(self, monkeypatch):
        """GET /segredos/{key} e POST /resolver devem retornar o mesmo valor."""
        fk = _vault_patch(monkeypatch)
        monkeypatch.setattr(_settings, 'vault_api_token', self.TOKEN)
        _setup_vault_secret(fk, 'SHARED_KEY', 'valor-compartilhado')
        headers = {'X-Vault-Token': self.TOKEN}

        get_resp = client.get('/v1/cofre/segredos/SHARED_KEY', headers=headers)
        post_resp = client.post('/v1/cofre/resolver', json={'key': 'SHARED_KEY'}, headers=headers)

        assert get_resp.json()['data']['value'] == post_resp.json()['data']['value']
