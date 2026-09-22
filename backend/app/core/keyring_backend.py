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
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_NONCE_BYTES = 12
_KDF_SALT = b'reqsys-cofre-file-keyring-v1'
_KDF_ITERATIONS = 200_000


def _derive_key(passphrase: str) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_KDF_SALT, iterations=_KDF_ITERATIONS)
    return kdf.derive(passphrase.encode('utf-8'))


def _canonical_passphrase(passphrase: str) -> str:
    """Normaliza somente o CR residual introduzido por arquivo CRLF + $(cat ...).

    Command substitution remove o LF final, mas preserva o CR. Passphrases
    geradas pelo ReqSys nao usam CR como caractere de dados, portanto removemos
    um unico CR terminal para tornar LF/CRLF equivalentes.
    """
    return passphrase[:-1] if passphrase.endswith('\r') else passphrase


class FileEncryptedKeyring(keyring.backend.KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self, path: str | None = None, passphrase: str | None = None):
        super().__init__()
        data_dir = path or os.getenv('REQSYS_DATA_DIR', '/data')
        self._path = Path(data_dir) / 'cofre-keyring.enc'
        self._passphrase = passphrase if passphrase is not None else os.getenv('COFRE_KEYRING_PASSPHRASE', '')

    def _canonical_key(self) -> bytes:
        canonical = _canonical_passphrase(self._passphrase)
        if not canonical:
            raise keyring.errors.KeyringError('COFRE_KEYRING_PASSPHRASE não configurada')
        return _derive_key(canonical)

    def _candidate_keys(self) -> list[bytes]:
        """Retorna chave canonica e um unico fallback legado CRLF, sem duplicatas."""
        canonical = _canonical_passphrase(self._passphrase)
        if not canonical:
            raise keyring.errors.KeyringError('COFRE_KEYRING_PASSPHRASE não configurada')

        candidates = [canonical]
        legacy = self._passphrase if self._passphrase != canonical else canonical + '\r'
        if legacy and legacy not in candidates:
            candidates.append(legacy)
        return [_derive_key(candidate) for candidate in candidates]

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        raw = self._path.read_bytes()
        if not raw:
            return {}

        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        last_invalid_tag: InvalidTag | None = None
        for key in self._candidate_keys():
            try:
                plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
            except InvalidTag as exc:
                last_invalid_tag = exc
                continue
            return json.loads(plaintext.decode('utf-8'))

        assert last_invalid_tag is not None
        raise last_invalid_tag

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        nonce = os.urandom(_NONCE_BYTES)
        plaintext = json.dumps(data).encode('utf-8')
        ciphertext = AESGCM(self._canonical_key()).encrypt(nonce, plaintext, None)
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
        # Fail-closed: se um arquivo existente nao puder ser descriptografado,
        # nunca o trate como vault vazio nem o sobrescreva silenciosamente.
        data = self._load()
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
