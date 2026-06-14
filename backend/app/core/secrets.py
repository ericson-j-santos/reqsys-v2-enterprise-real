from __future__ import annotations

import logging
import os
import secrets as _secrets
from base64 import b64decode, b64encode

_logger = logging.getLogger(__name__)

try:
    import keyring  # type: ignore
    _KEYRING_OK = True
except ImportError:
    keyring = None
    _KEYRING_OK = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False


_DEFAULT_VAULT_SERVICE = 'mvp-intelligence-vault'
_MASTER_KEY_SLOT = '__master_key__'
_NONCE_BYTES = 12


def _vault_service_name() -> str:
    return os.getenv('REQSYS_VAULT_SERVICE_NAME', _DEFAULT_VAULT_SERVICE).strip() or _DEFAULT_VAULT_SERVICE


def init_vault(service_name: str | None = None, overwrite: bool = False) -> bool:
    """Cria master key no keyring. Retorna True se criada, False se já existia."""
    if not (_KEYRING_OK and _CRYPTO_OK):
        return False
    service = service_name or _vault_service_name()
    existing = keyring.get_password(service, _MASTER_KEY_SLOT)
    if existing and not overwrite:
        return False
    master_key = _secrets.token_bytes(32)
    keyring.set_password(service, _MASTER_KEY_SLOT, b64encode(master_key).decode())
    return True


def read_secret_from_vault(key: str, service_name: str | None = None) -> str | None:
    if not key or not (_KEYRING_OK and _CRYPTO_OK):
        return None

    service = service_name or _vault_service_name()
    try:
        raw_master_key = keyring.get_password(service, _MASTER_KEY_SLOT)
        if not raw_master_key:
            return None

        blob = keyring.get_password(service, key)
        if blob is None:
            return None

        master_key = b64decode(raw_master_key)
        raw = b64decode(blob)
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        return AESGCM(master_key).decrypt(nonce, ciphertext, None).decode()
    except Exception:
        _logger.warning('Falha ao descriptografar segredo "%s" no vault "%s"', key, service)
        return None


def write_secret_to_vault(key: str, value: str, service_name: str | None = None) -> None:
    """Criptografa e grava segredo no keyring."""
    if not key or not key.strip():
        raise ValueError('Chave não pode ser vazia')
    if not (_KEYRING_OK and _CRYPTO_OK):
        raise RuntimeError('Vault não disponível: keyring ou cryptography não instalados')
    service = service_name or _vault_service_name()
    raw_master_key = keyring.get_password(service, _MASTER_KEY_SLOT)
    if not raw_master_key:
        raise RuntimeError('Vault não inicializado. Chame init_vault() ou POST /v1/cofre/init primeiro')
    master_key = b64decode(raw_master_key)
    nonce = _secrets.token_bytes(_NONCE_BYTES)
    ciphertext = AESGCM(master_key).encrypt(nonce, value.encode(), None)
    blob = b64encode(nonce + ciphertext).decode()
    keyring.set_password(service, key, blob)


def delete_secret_from_vault(key: str, service_name: str | None = None) -> bool:
    """Remove segredo do keyring. Retorna True se existia."""
    if not _KEYRING_OK:
        return False
    service = service_name or _vault_service_name()
    try:
        existing = keyring.get_password(service, key)
        if existing is None:
            return False
        keyring.delete_password(service, key)
        return True
    except Exception:
        return False


def vault_initialized(service_name: str | None = None) -> bool:
    if not _KEYRING_OK:
        return False
    service = service_name or _vault_service_name()
    try:
        return bool(keyring.get_password(service, _MASTER_KEY_SLOT))
    except Exception:
        return False


def get_secret(
    name: str,
    default: str | None = None,
    *,
    env_name: str | None = None,
    vault_key: str | None = None,
    prefer_vault: bool = False,
) -> str | None:
    env_key = env_name or name
    secret_key = vault_key or name
    env_value = os.getenv(env_key)

    if prefer_vault:
        vault_value = read_secret_from_vault(secret_key)
        if vault_value not in (None, ''):
            return vault_value
        if env_value not in (None, ''):
            return env_value
        return default

    if env_value not in (None, ''):
        return env_value

    vault_value = read_secret_from_vault(secret_key)
    if vault_value not in (None, ''):
        return vault_value

    return default


def describe_secret_resolution(
    name: str,
    default: str | None = None,
    *,
    env_name: str | None = None,
    vault_key: str | None = None,
    prefer_vault: bool = False,
) -> dict[str, object]:
    env_key = env_name or name
    secret_key = vault_key or name
    env_value = os.getenv(env_key)
    vault_value = read_secret_from_vault(secret_key)

    has_vault = vault_value not in (None, '')
    has_env = env_value not in (None, '')

    if prefer_vault and has_vault:
        source = 'vault'
    elif has_env:
        source = 'env'
    elif has_vault:
        source = 'vault'
    elif default is not None:
        source = 'default'
    else:
        source = 'absent'

    configured = source != 'absent'

    return {
        'name': name,
        'env_name': env_key,
        'vault_key': secret_key,
        'source': source,
        'configured': configured,
        'using_default': source == 'default',
        'prefer_vault': prefer_vault,
        'vault_service_name': _vault_service_name(),
        'value_exposed': False,
    }
