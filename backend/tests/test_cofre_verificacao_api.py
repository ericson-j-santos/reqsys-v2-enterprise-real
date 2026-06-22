from __future__ import annotations

from base64 import b64encode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

from app.core import secrets as secrets_module
from app.core.cofre_verificador_cego import CHAVE_OPERACIONAL_VERIFICADOR
from app.core.config import settings as _settings
from app.main import app

SVC = 'test-api-vault-verificacao-cega'
TOKEN = 'vault-token-verificar-teste'
VALOR_OPERACIONAL = 'valor-operacional-com-no-minimo-32-caracteres'

client = TestClient(app)


class _FakeKeyring:
    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._store.pop((service, username), None)


def _vault_patch(monkeypatch) -> _FakeKeyring:
    fk = _FakeKeyring()
    monkeypatch.setattr(secrets_module, 'keyring', fk)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
    monkeypatch.setenv('REQSYS_VAULT_SERVICE_NAME', SVC)
    monkeypatch.setattr(_settings, 'vault_api_token', TOKEN)
    return fk


def _setup_vault_value(fk: _FakeKeyring, key: str, value: str) -> None:
    master_key = AESGCM.generate_key(bit_length=256)
    fk.set_password(SVC, secrets_module._MASTER_KEY_SLOT, b64encode(master_key).decode())
    nonce = b'\x00' * secrets_module._NONCE_BYTES
    blob = AESGCM(master_key).encrypt(nonce, value.encode(), None)
    fk.set_password(SVC, key, b64encode(nonce + blob).decode())


def test_verificar_retorna_true_sem_expor_valor(monkeypatch):
    fk = _vault_patch(monkeypatch)
    _setup_vault_value(fk, 'API_KEY_SEGURA', 'valor-correto')
    _setup_vault_value(fk, CHAVE_OPERACIONAL_VERIFICADOR, VALOR_OPERACIONAL)

    resp = client.post(
        '/v1/cofre/verificar',
        json={'key': 'API_KEY_SEGURA', 'value': 'valor-correto'},
        headers={'X-Vault-Token': TOKEN},
    )

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['match'] is True
    assert data['value_exposed'] is False
    assert 'value' not in data
    assert 'digest' not in data


def test_verificar_retorna_false_sem_expor_valor(monkeypatch):
    fk = _vault_patch(monkeypatch)
    _setup_vault_value(fk, 'API_KEY_SEGURA', 'valor-correto')
    _setup_vault_value(fk, CHAVE_OPERACIONAL_VERIFICADOR, VALOR_OPERACIONAL)

    resp = client.post(
        '/v1/cofre/verificar',
        json={'key': 'API_KEY_SEGURA', 'value': 'valor-incorreto'},
        headers={'X-Vault-Token': TOKEN},
    )

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['match'] is False
    assert 'value' not in data


def test_verificar_sem_valor_operacional_retorna_503(monkeypatch):
    fk = _vault_patch(monkeypatch)
    _setup_vault_value(fk, 'API_KEY_SEGURA', 'valor-correto')

    resp = client.post(
        '/v1/cofre/verificar',
        json={'key': 'API_KEY_SEGURA', 'value': 'valor-correto'},
        headers={'X-Vault-Token': TOKEN},
    )

    assert resp.status_code == 503


def test_verificar_bloqueia_chave_operacional(monkeypatch):
    _vault_patch(monkeypatch)

    resp = client.post(
        '/v1/cofre/verificar',
        json={'key': CHAVE_OPERACIONAL_VERIFICADOR, 'value': 'qualquer'},
        headers={'X-Vault-Token': TOKEN},
    )

    assert resp.status_code == 422


def test_resolver_bloqueia_chave_operacional(monkeypatch):
    _vault_patch(monkeypatch)

    resp = client.post(
        '/v1/cofre/resolver',
        json={'key': CHAVE_OPERACIONAL_VERIFICADOR},
        headers={'X-Vault-Token': TOKEN},
    )

    assert resp.status_code == 400
