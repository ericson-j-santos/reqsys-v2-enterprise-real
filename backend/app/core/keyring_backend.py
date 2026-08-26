"""Backend de keyring baseado em arquivo, para containers headless sem OS keyring.

O container Linux do Fly nao tem D-Bus/Secret Service disponivel, entao o
backend padrao do pacote `keyring` fica indisponivel (ou falha silenciosamente
via ImportError quando o pacote nem esta instalado). Esta classe persiste
todas as entradas (service, username) -> password num unico arquivo no volume
persistente (`/data`), com o conteudo inteiro cifrado (AES-GCM) por uma chave
derivada da passphrase em COFRE_KEYRING_PASSPHRASE.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import keyring.backend
import keyring.errors
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_NONCE_BYTES = 12
_KDF_SALT = b'reqsys-cofre-file-keyring-v1'
_KDF_ITERATIONS = 200_000


def _derive_key(passphrase: str) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_KDF_SALT, iterations=_KDF_ITERATIONS)
    return kdf.derive(passphrase.encode('utf-8'))


class FileEncryptedKeyring(keyring.backend.KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self, path: str | None = None, passphrase: str | None = None):
        super().__init__()
        data_dir = path or os.getenv('REQSYS_DATA_DIR', '/data')
        self._path = Path(data_dir) / 'cofre-keyring.enc'
        self._passphrase = passphrase if passphrase is not None else os.getenv('COFRE_KEYRING_PASSPHRASE', '')

    def _key(self) -> bytes:
        if not self._passphrase:
            raise keyring.errors.KeyringError('COFRE_KEYRING_PASSPHRASE não configurada')
        return _derive_key(self._passphrase)

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        raw = self._path.read_bytes()
        if not raw:
            return {}
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        plaintext = AESGCM(self._key()).decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode('utf-8'))

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        nonce = os.urandom(_NONCE_BYTES)
        plaintext = json.dumps(data).encode('utf-8')
        ciphertext = AESGCM(self._key()).encrypt(nonce, plaintext, None)
        tmp = self._path.with_suffix('.tmp')
        tmp.write_bytes(nonce + ciphertext)
        os.replace(tmp, self._path)
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    def get_password(self, service: str, username: str) -> str | None:
        try:
            data = self._load()
        except Exception:
            return None
        return data.get(service, {}).get(username)

    def set_password(self, service: str, username: str, password: str) -> None:
        try:
            data = self._load()
        except Exception:
            data = {}
        data.setdefault(service, {})[username] = password
        self._save(data)

    def delete_password(self, service: str, username: str) -> None:
        data = self._load()
        if service not in data or username not in data[service]:
            raise keyring.errors.PasswordDeleteError('not found')
        del data[service][username]
        if not data[service]:
            del data[service]
        self._save(data)
