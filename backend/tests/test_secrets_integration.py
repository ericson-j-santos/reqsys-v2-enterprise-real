from __future__ import annotations

from base64 import b64decode, b64encode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.api import relatorios
from app.core.config import Settings
from app.core import secrets as secrets_module
from app.services import github_redmine


class _FakeKeyring:
    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password


def _put_vault_secret(fake_keyring: _FakeKeyring, service: str, key: str, value: str) -> None:
    raw_master_key = fake_keyring.get_password(service, secrets_module._MASTER_KEY_SLOT)
    if raw_master_key:
        master_key = b64decode(raw_master_key)
    else:
        master_key = AESGCM.generate_key(bit_length=256)
        fake_keyring.set_password(service, secrets_module._MASTER_KEY_SLOT, b64encode(master_key).decode())
    nonce = b'0' * secrets_module._NONCE_BYTES
    blob = AESGCM(master_key).encrypt(nonce, value.encode(), None)
    fake_keyring.set_password(service, key, b64encode(nonce + blob).decode())


def test_settings_uses_vault_as_fallback(monkeypatch):
    fake_keyring = _FakeKeyring()
    monkeypatch.setattr(secrets_module, 'keyring', fake_keyring)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
    monkeypatch.delenv('JWT_SECRET', raising=False)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    _put_vault_secret(fake_keyring, 'mvp-intelligence-vault', 'JWT_SECRET', 'jwt-from-vault')
    _put_vault_secret(fake_keyring, 'mvp-intelligence-vault', 'DATABASE_URL', 'sqlite:///./vault.db')

    settings = Settings()

    assert settings.jwt_secret == 'jwt-from-vault'
    assert settings.database_url == 'sqlite:///./vault.db'


def test_env_still_wins_over_vault(monkeypatch):
    fake_keyring = _FakeKeyring()
    monkeypatch.setattr(secrets_module, 'keyring', fake_keyring)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
    monkeypatch.setenv('JWT_SECRET', 'jwt-from-env')
    _put_vault_secret(fake_keyring, 'mvp-intelligence-vault', 'JWT_SECRET', 'jwt-from-vault')

    settings = Settings()

    assert settings.jwt_secret == 'jwt-from-env'


def test_github_redmine_reads_github_token_from_vault(monkeypatch):
    fake_keyring = _FakeKeyring()
    monkeypatch.setattr(secrets_module, 'keyring', fake_keyring)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    _put_vault_secret(fake_keyring, 'mvp-intelligence-vault', 'GITHUB_TOKEN', 'gh-vault-token')

    captured: dict[str, object] = {}

    def _fake_request_json(method, url, headers=None, payload=None):
        captured['method'] = method
        captured['url'] = url
        captured['headers'] = headers or {}
        return []

    monkeypatch.setattr(github_redmine, '_request_json', _fake_request_json)

    github_redmine.fetch_github_issues('owner/repo')

    assert captured['method'] == 'GET'
    assert captured['headers']['Authorization'] == 'Bearer gh-vault-token'


def test_relatorios_reads_ssrs_base_from_vault(monkeypatch):
    fake_keyring = _FakeKeyring()
    monkeypatch.setattr(secrets_module, 'keyring', fake_keyring)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
    monkeypatch.delenv('SSRS_BASE_URL', raising=False)
    _put_vault_secret(fake_keyring, 'mvp-intelligence-vault', 'SSRS_BASE_URL', 'http://ssrs.local/ReportServer')

    response = relatorios.ssrs_links()
    data = response['data']

    assert data['enabled'] is True
    assert data['report_server_base_url'] == 'http://ssrs.local/ReportServer'