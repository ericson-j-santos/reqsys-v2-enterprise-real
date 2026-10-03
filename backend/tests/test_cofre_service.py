"""Testes unitários para app.core.secrets (camada de serviço do cofre)."""
from __future__ import annotations

from base64 import b64decode, b64encode

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core import secrets as secrets_module
from app.core.secrets import (
    _MASTER_KEY_SLOT,
    _NONCE_BYTES,
    _vault_service_name,
    delete_secret_from_vault,
    describe_secret_resolution,
    get_secret,
    init_vault,
    read_secret_from_vault,
    vault_initialized,
    write_secret_to_vault,
)

SVC = 'test-cofre-service'


# ---------------------------------------------------------------------------
# Helpers de teste
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


def _init_fake_vault(fake: _FakeKeyring, service: str) -> bytes:
    master_key = AESGCM.generate_key(bit_length=256)
    fake.set_password(service, _MASTER_KEY_SLOT, b64encode(master_key).decode())
    return master_key


def _put_vault_secret(fake: _FakeKeyring, service: str, key: str, value: str) -> None:
    raw = fake.get_password(service, _MASTER_KEY_SLOT)
    master_key = b64decode(raw) if raw else _init_fake_vault(fake, service)
    nonce = b'\x00' * _NONCE_BYTES
    blob = AESGCM(master_key).encrypt(nonce, value.encode(), None)
    fake.set_password(service, key, b64encode(nonce + blob).decode())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fk(monkeypatch):
    """FakeKeyring injetado com keyring + crypto disponíveis e service name isolado."""
    fake = _FakeKeyring()
    monkeypatch.setattr(secrets_module, 'keyring', fake)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
    monkeypatch.setenv('REQSYS_VAULT_SERVICE_NAME', SVC)
    return fake


@pytest.fixture
def fk_init(fk):
    """FakeKeyring com vault já inicializado."""
    _init_fake_vault(fk, SVC)
    return fk


# ---------------------------------------------------------------------------
# _vault_service_name
# ---------------------------------------------------------------------------

class TestVaultServiceName:
    def test_retorna_default_sem_env(self, monkeypatch):
        monkeypatch.delenv('REQSYS_VAULT_SERVICE_NAME', raising=False)
        assert _vault_service_name() == 'mvp-intelligence-vault'

    def test_usa_valor_da_env(self, monkeypatch):
        monkeypatch.setenv('REQSYS_VAULT_SERVICE_NAME', 'meu-vault')
        assert _vault_service_name() == 'meu-vault'

    def test_env_vazia_usa_default(self, monkeypatch):
        monkeypatch.setenv('REQSYS_VAULT_SERVICE_NAME', '')
        assert _vault_service_name() == 'mvp-intelligence-vault'

    def test_env_so_espacos_usa_default(self, monkeypatch):
        monkeypatch.setenv('REQSYS_VAULT_SERVICE_NAME', '   ')
        assert _vault_service_name() == 'mvp-intelligence-vault'


# ---------------------------------------------------------------------------
# init_vault
# ---------------------------------------------------------------------------

class TestInitVault:
    def test_cria_master_key_retorna_true(self, fk):
        assert init_vault(service_name=SVC) is True

    def test_master_key_gravada_como_256_bits(self, fk):
        init_vault(service_name=SVC)
        raw = fk.get_password(SVC, _MASTER_KEY_SLOT)
        assert raw is not None
        assert len(b64decode(raw)) == 32

    def test_segunda_chamada_sem_overwrite_retorna_false(self, fk):
        init_vault(service_name=SVC)
        assert init_vault(service_name=SVC) is False

    def test_segunda_chamada_sem_overwrite_preserva_master_key(self, fk):
        init_vault(service_name=SVC)
        original = fk.get_password(SVC, _MASTER_KEY_SLOT)
        init_vault(service_name=SVC)
        assert fk.get_password(SVC, _MASTER_KEY_SLOT) == original

    def test_overwrite_true_retorna_true(self, fk):
        init_vault(service_name=SVC)
        assert init_vault(service_name=SVC, overwrite=True) is True

    def test_sem_keyring_retorna_false(self, monkeypatch):
        monkeypatch.setattr(secrets_module, '_KEYRING_OK', False)
        assert init_vault(service_name=SVC) is False

    def test_sem_crypto_retorna_false(self, monkeypatch):
        monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
        monkeypatch.setattr(secrets_module, '_CRYPTO_OK', False)
        assert init_vault(service_name=SVC) is False


# ---------------------------------------------------------------------------
# vault_initialized
# ---------------------------------------------------------------------------

class TestVaultInitialized:
    def test_false_sem_master_key(self, fk):
        assert vault_initialized(service_name=SVC) is False

    def test_true_apos_init(self, fk):
        init_vault(service_name=SVC)
        assert vault_initialized(service_name=SVC) is True

    def test_false_sem_keyring(self, monkeypatch):
        monkeypatch.setattr(secrets_module, '_KEYRING_OK', False)
        assert vault_initialized(service_name=SVC) is False


# ---------------------------------------------------------------------------
# write_secret_to_vault
# ---------------------------------------------------------------------------

class TestWriteSecretToVault:
    def test_grava_blob_no_keyring(self, fk_init):
        write_secret_to_vault('MINHA_KEY', 'valor', service_name=SVC)
        assert fk_init.get_password(SVC, 'MINHA_KEY') is not None

    def test_blob_nao_contem_texto_em_claro(self, fk_init):
        write_secret_to_vault('KEY_CIFRADA', 'segredo-super-secreto', service_name=SVC)
        blob = fk_init.get_password(SVC, 'KEY_CIFRADA')
        assert 'segredo-super-secreto' not in blob

    def test_levanta_runtime_sem_vault_inicializado(self, fk):
        with pytest.raises(RuntimeError, match='não inicializado'):
            write_secret_to_vault('KEY', 'valor', service_name=SVC)

    def test_levanta_runtime_sem_keyring(self, monkeypatch):
        monkeypatch.setattr(secrets_module, '_KEYRING_OK', False)
        monkeypatch.setattr(secrets_module, '_CRYPTO_OK', False)
        with pytest.raises(RuntimeError, match='não disponível'):
            write_secret_to_vault('KEY', 'valor', service_name=SVC)

    def test_levanta_valueerror_chave_vazia(self, fk_init):
        with pytest.raises((ValueError, RuntimeError)):
            write_secret_to_vault('', 'valor', service_name=SVC)

    def test_levanta_valueerror_chave_so_espacos(self, fk_init):
        with pytest.raises((ValueError, RuntimeError)):
            write_secret_to_vault('   ', 'valor', service_name=SVC)


# ---------------------------------------------------------------------------
# read_secret_from_vault
# ---------------------------------------------------------------------------

class TestReadSecretFromVault:
    def test_retorna_valor_descriptografado(self, fk_init):
        write_secret_to_vault('READ_KEY', 'valor-correto', service_name=SVC)
        assert read_secret_from_vault('READ_KEY', service_name=SVC) == 'valor-correto'

    def test_none_para_chave_inexistente(self, fk_init):
        assert read_secret_from_vault('NAO_EXISTE', service_name=SVC) is None

    def test_none_sem_vault_inicializado(self, fk):
        assert read_secret_from_vault('QUALQUER', service_name=SVC) is None

    def test_none_para_chave_vazia(self, fk_init):
        assert read_secret_from_vault('', service_name=SVC) is None

    def test_none_sem_keyring(self, monkeypatch):
        monkeypatch.setattr(secrets_module, '_KEYRING_OK', False)
        assert read_secret_from_vault('KEY', service_name=SVC) is None

    def test_none_sem_crypto(self, fk_init, monkeypatch):
        monkeypatch.setattr(secrets_module, '_CRYPTO_OK', False)
        assert read_secret_from_vault('KEY', service_name=SVC) is None

    def test_none_para_blob_corrompido(self, fk_init):
        fk_init.set_password(SVC, 'BLOB_RUIM', 'nao-e-base64-valido!!!')
        assert read_secret_from_vault('BLOB_RUIM', service_name=SVC) is None

    def test_preserva_caracteres_especiais(self, fk_init):
        valor = 'senha@!#$%^&*()-_=+[]{}|;:,.<>?/~`'
        write_secret_to_vault('CHARS', valor, service_name=SVC)
        assert read_secret_from_vault('CHARS', service_name=SVC) == valor

    def test_preserva_unicode(self, fk_init):
        valor = 'segredo-çãõé-🔐'
        write_secret_to_vault('UNICODE', valor, service_name=SVC)
        assert read_secret_from_vault('UNICODE', service_name=SVC) == valor

    def test_write_read_round_trip(self, fk_init):
        for key, val in [('A', 'x'), ('B', 'y' * 100), ('C', '0' * 1)]:
            write_secret_to_vault(key, val, service_name=SVC)
            assert read_secret_from_vault(key, service_name=SVC) == val


# ---------------------------------------------------------------------------
# delete_secret_from_vault
# ---------------------------------------------------------------------------

class TestDeleteSecretFromVault:
    def test_retorna_true_para_chave_existente(self, fk_init):
        write_secret_to_vault('DEL_KEY', 'valor', service_name=SVC)
        assert delete_secret_from_vault('DEL_KEY', service_name=SVC) is True

    def test_chave_removida_nao_e_mais_lida(self, fk_init):
        write_secret_to_vault('DEL_KEY2', 'valor', service_name=SVC)
        delete_secret_from_vault('DEL_KEY2', service_name=SVC)
        assert read_secret_from_vault('DEL_KEY2', service_name=SVC) is None

    def test_retorna_false_para_chave_inexistente(self, fk_init):
        assert delete_secret_from_vault('NAO_EXISTE', service_name=SVC) is False

    def test_retorna_false_sem_keyring(self, monkeypatch):
        monkeypatch.setattr(secrets_module, '_KEYRING_OK', False)
        assert delete_secret_from_vault('KEY', service_name=SVC) is False

    def test_idempotente_duplo_delete(self, fk_init):
        write_secret_to_vault('IDEM_KEY', 'valor', service_name=SVC)
        assert delete_secret_from_vault('IDEM_KEY', service_name=SVC) is True
        assert delete_secret_from_vault('IDEM_KEY', service_name=SVC) is False


# ---------------------------------------------------------------------------
# get_secret
# ---------------------------------------------------------------------------

class TestGetSecret:
    def test_env_vence_vault_por_padrao(self, fk_init, monkeypatch):
        monkeypatch.setenv('GS_KEY1', 'de-env')
        _put_vault_secret(fk_init, SVC, 'GS_KEY1', 'do-vault')
        assert get_secret('GS_KEY1') == 'de-env'

    def test_vault_como_fallback_sem_env(self, fk_init, monkeypatch):
        monkeypatch.delenv('GS_KEY2', raising=False)
        _put_vault_secret(fk_init, SVC, 'GS_KEY2', 'do-vault')
        assert get_secret('GS_KEY2') == 'do-vault'

    def test_default_quando_ambos_ausentes(self, fk, monkeypatch):
        monkeypatch.delenv('GS_KEY3', raising=False)
        assert get_secret('GS_KEY3', default='padrao') == 'padrao'

    def test_none_quando_tudo_ausente(self, fk, monkeypatch):
        monkeypatch.delenv('GS_KEY4', raising=False)
        assert get_secret('GS_KEY4') is None

    def test_prefer_vault_vault_vence_env(self, fk_init, monkeypatch):
        monkeypatch.setenv('GS_KEY5', 'de-env')
        _put_vault_secret(fk_init, SVC, 'GS_KEY5', 'do-vault')
        assert get_secret('GS_KEY5', prefer_vault=True) == 'do-vault'

    def test_prefer_vault_cai_em_env_se_vault_ausente(self, fk_init, monkeypatch):
        monkeypatch.setenv('GS_KEY6', 'de-env')
        assert get_secret('GS_KEY6', prefer_vault=True) == 'de-env'

    def test_env_vazia_tratada_como_ausente(self, fk_init, monkeypatch):
        monkeypatch.setenv('GS_KEY7', '')
        _put_vault_secret(fk_init, SVC, 'GS_KEY7', 'do-vault')
        assert get_secret('GS_KEY7') == 'do-vault'

    def test_vault_vazio_tratado_como_ausente(self, fk_init, monkeypatch):
        monkeypatch.delenv('GS_KEY8', raising=False)
        _put_vault_secret(fk_init, SVC, 'GS_KEY8', '')
        assert get_secret('GS_KEY8', default='padrao') == 'padrao'

    def test_env_name_override(self, fk, monkeypatch):
        monkeypatch.setenv('CUSTOM_ENV', 'valor-custom')
        assert get_secret('NOME_LOGICO', env_name='CUSTOM_ENV') == 'valor-custom'

    def test_vault_key_override(self, fk_init, monkeypatch):
        monkeypatch.delenv('NOME_LOGICO2', raising=False)
        _put_vault_secret(fk_init, SVC, 'CHAVE_VAULT_ALT', 'do-vault')
        assert get_secret('NOME_LOGICO2', vault_key='CHAVE_VAULT_ALT') == 'do-vault'


# ---------------------------------------------------------------------------
# describe_secret_resolution
# ---------------------------------------------------------------------------

class TestDescribeSecretResolution:
    def test_source_env_quando_so_env(self, fk, monkeypatch):
        monkeypatch.setenv('DR_KEY1', 'valor')
        result = describe_secret_resolution('DR_KEY1')
        assert result['source'] == 'env'
        assert result['configured'] is True

    def test_source_vault_quando_so_vault(self, fk_init, monkeypatch):
        monkeypatch.delenv('DR_KEY2', raising=False)
        _put_vault_secret(fk_init, SVC, 'DR_KEY2', 'valor')
        result = describe_secret_resolution('DR_KEY2')
        assert result['source'] == 'vault'
        assert result['configured'] is True

    def test_source_default_quando_apenas_default(self, fk, monkeypatch):
        monkeypatch.delenv('DR_KEY3', raising=False)
        result = describe_secret_resolution('DR_KEY3', default='padrao')
        assert result['source'] == 'default'
        assert result['using_default'] is True
        assert result['configured'] is True

    def test_source_absent_quando_tudo_ausente(self, fk, monkeypatch):
        monkeypatch.delenv('DR_KEY4', raising=False)
        result = describe_secret_resolution('DR_KEY4')
        assert result['source'] == 'absent'
        assert result['configured'] is False

    def test_value_exposed_sempre_false(self, fk_init, monkeypatch):
        monkeypatch.setenv('DR_KEY5', 'segredo')
        assert describe_secret_resolution('DR_KEY5')['value_exposed'] is False

    def test_resolved_espelha_configured(self, fk, monkeypatch):
        monkeypatch.setenv('DR_KEY10', 'valor')
        result = describe_secret_resolution('DR_KEY10')
        assert result['resolved'] is True
        assert result['resolved'] == result['configured']

    def test_resolved_false_quando_absent(self, fk, monkeypatch):
        monkeypatch.delenv('DR_KEY11', raising=False)
        result = describe_secret_resolution('DR_KEY11')
        assert result['resolved'] is False
        assert result['configured'] is False

    def test_env_vence_vault_sem_prefer_vault(self, fk_init, monkeypatch):
        monkeypatch.setenv('DR_KEY6', 'de-env')
        _put_vault_secret(fk_init, SVC, 'DR_KEY6', 'do-vault')
        assert describe_secret_resolution('DR_KEY6')['source'] == 'env'

    def test_vault_vence_env_com_prefer_vault(self, fk_init, monkeypatch):
        monkeypatch.setenv('DR_KEY7', 'de-env')
        _put_vault_secret(fk_init, SVC, 'DR_KEY7', 'do-vault')
        assert describe_secret_resolution('DR_KEY7', prefer_vault=True)['source'] == 'vault'

    def test_prefer_vault_refletido_no_resultado(self, fk, monkeypatch):
        monkeypatch.delenv('DR_KEY8', raising=False)
        assert describe_secret_resolution('DR_KEY8', prefer_vault=True)['prefer_vault'] is True

    def test_vault_service_name_refletido(self, fk, monkeypatch):
        monkeypatch.delenv('DR_KEY9', raising=False)
        assert describe_secret_resolution('DR_KEY9')['vault_service_name'] == SVC
