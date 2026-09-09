from __future__ import annotations

import base64
import os

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.secrets import get_secret

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover - dependência obrigatória em produção segura
    AESGCM = None  # type: ignore[assignment]

_ENVELOPE_PREFIX = 'enc:v1:'
_NONCE_BYTES = 12


class EncryptedTextConfigurationError(RuntimeError):
    pass


def encryption_mode() -> str:
    mode = (os.getenv('AI_CONVERSATION_ENCRYPTION_MODE', 'off') or 'off').strip().lower()
    if mode in {'off', 'disabled', 'legacy'}:
        return 'off'
    if mode == 'enforce':
        return 'enforce'
    raise EncryptedTextConfigurationError(
        'AI_CONVERSATION_ENCRYPTION_MODE inválido; use off ou enforce.'
    )


def _resolve_key() -> bytes | None:
    encoded = get_secret(
        'AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64',
        '',
        prefer_vault=True,
    ) or ''
    if not encoded:
        return None
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise EncryptedTextConfigurationError('Chave de criptografia do histórico não é base64 válida.') from exc
    if len(key) != 32:
        raise EncryptedTextConfigurationError('Chave de criptografia do histórico deve conter 32 bytes.')
    return key


def encrypt_text(value: str) -> str:
    if encryption_mode() == 'off':
        return value
    if AESGCM is None:
        raise EncryptedTextConfigurationError('cryptography/AESGCM indisponível.')
    key = _resolve_key()
    if key is None:
        raise EncryptedTextConfigurationError(
            'AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64 ausente no cofre/configuração.'
        )
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, value.encode('utf-8'), None)
    envelope = base64.b64encode(nonce + ciphertext).decode('ascii')
    return f'{_ENVELOPE_PREFIX}{envelope}'


def decrypt_text(value: str) -> str:
    if not value.startswith(_ENVELOPE_PREFIX):
        return value
    if AESGCM is None:
        raise EncryptedTextConfigurationError('cryptography/AESGCM indisponível.')
    key = _resolve_key()
    if key is None:
        raise EncryptedTextConfigurationError(
            'Chave de criptografia necessária para ler o histórico não foi resolvida.'
        )
    try:
        raw = base64.b64decode(value[len(_ENVELOPE_PREFIX):], validate=True)
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        return AESGCM(key).decrypt(nonce, ciphertext, None).decode('utf-8')
    except EncryptedTextConfigurationError:
        raise
    except Exception as exc:
        raise EncryptedTextConfigurationError('Falha de integridade ao descriptografar histórico de IA.') from exc


class EncryptedText(TypeDecorator[str]):
    """Mantém Text no banco e criptografa/descriptografa no limite ORM."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect):
        if value is None:
            return None
        return encrypt_text(str(value))

    def process_result_value(self, value: str | None, dialect):
        if value is None:
            return None
        return decrypt_text(str(value))
