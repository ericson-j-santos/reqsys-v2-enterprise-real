from __future__ import annotations

import os
from base64 import b64decode

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
        return None


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

    if prefer_vault and vault_value not in (None, ''):
        source = 'vault'
        configured = True
    elif env_value not in (None, ''):
        source = 'env'
        configured = True
    elif vault_value not in (None, ''):
        source = 'vault'
        configured = True
    elif default is not None:
        source = 'default'
        configured = True
    else:
        source = 'absent'
        configured = False

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