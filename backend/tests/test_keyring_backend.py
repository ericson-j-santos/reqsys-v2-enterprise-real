"""Testes unitários para app.core.keyring_backend (FileEncryptedKeyring)."""
from __future__ import annotations

import json
import os

import keyring.errors
import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.keyring_backend import (
    _NONCE_BYTES,
    _derive_key,
    FileEncryptedKeyring,
)


def _backend(tmp_path, passphrase: str = 'senha-de-teste-bem-forte') -> FileEncryptedKeyring:
    return FileEncryptedKeyring(path=str(tmp_path), passphrase=passphrase)


def _write_legacy_file(tmp_path, passphrase: str, data: dict) -> bytes:
    nonce = os.urandom(_NONCE_BYTES)
    plaintext = json.dumps(data).encode('utf-8')
    ciphertext = AESGCM(_derive_key(passphrase)).encrypt(nonce, plaintext, None)
    raw = nonce + ciphertext
    (tmp_path / 'cofre-keyring.enc').write_bytes(raw)
    return raw


def test_get_password_sem_arquivo_retorna_none(tmp_path):
    backend = _backend(tmp_path)
    assert backend.get_password('svc', 'user') is None


def test_set_e_get_password_round_trip(tmp_path):
    backend = _backend(tmp_path)
    backend.set_password('svc', 'user', 'valor-secreto')
    assert backend.get_password('svc', 'user') == 'valor-secreto'


def test_set_password_multiplas_entradas_mesmo_servico(tmp_path):
    backend = _backend(tmp_path)
    backend.set_password('svc', 'user-a', 'valor-a')
    backend.set_password('svc', 'user-b', 'valor-b')
    assert backend.get_password('svc', 'user-a') == 'valor-a'
    assert backend.get_password('svc', 'user-b') == 'valor-b'


def test_set_password_persiste_entre_instancias(tmp_path):
    _backend(tmp_path).set_password('svc', 'user', 'valor-persistido')
    outra_instancia = _backend(tmp_path)
    assert outra_instancia.get_password('svc', 'user') == 'valor-persistido'


def test_delete_password_remove_entrada(tmp_path):
    backend = _backend(tmp_path)
    backend.set_password('svc', 'user', 'valor')
    backend.delete_password('svc', 'user')
    assert backend.get_password('svc', 'user') is None


def test_delete_password_inexistente_levanta_erro(tmp_path):
    backend = _backend(tmp_path)
    with pytest.raises(keyring.errors.PasswordDeleteError):
        backend.delete_password('svc', 'user')


def test_delete_password_servico_inexistente_levanta_erro(tmp_path):
    backend = _backend(tmp_path)
    backend.set_password('outro-svc', 'user', 'valor')
    with pytest.raises(keyring.errors.PasswordDeleteError):
        backend.delete_password('svc', 'user')


def test_sem_passphrase_levanta_keyring_error_ao_gravar(tmp_path):
    backend = _backend(tmp_path, passphrase='')
    with pytest.raises(keyring.errors.KeyringError):
        backend.set_password('svc', 'user', 'valor')


def test_get_password_com_passphrase_errada_retorna_none(tmp_path):
    _backend(tmp_path, passphrase='passphrase-correta').set_password('svc', 'user', 'valor')
    backend_errado = _backend(tmp_path, passphrase='passphrase-errada')
    assert backend_errado.get_password('svc', 'user') is None


def test_arquivo_e_criado_com_permissao_restrita(tmp_path):
    backend = _backend(tmp_path)
    backend.set_password('svc', 'user', 'valor')
    assert backend._path.exists()


def test_arquivo_vazio_e_tratado_como_vault_vazio(tmp_path):
    backend = _backend(tmp_path)
    backend._path.parent.mkdir(parents=True, exist_ok=True)
    backend._path.write_bytes(b'')
    assert backend.get_password('svc', 'user') is None


def test_delete_password_mantem_outras_entradas_do_mesmo_servico(tmp_path):
    backend = _backend(tmp_path)
    backend.set_password('svc', 'user-a', 'valor-a')
    backend.set_password('svc', 'user-b', 'valor-b')
    backend.delete_password('svc', 'user-a')
    assert backend.get_password('svc', 'user-a') is None
    assert backend.get_password('svc', 'user-b') == 'valor-b'


def test_set_password_com_arquivo_corrompido_falha_sem_sobrescrever(tmp_path):
    backend = _backend(tmp_path)
    backend._path.parent.mkdir(parents=True, exist_ok=True)
    original = b'lixo-nao-decifravel-0123456789ab'
    backend._path.write_bytes(original)

    with pytest.raises(InvalidTag):
        backend.set_password('svc', 'user', 'valor-novo')

    assert backend._path.read_bytes() == original


def test_legado_crlf_e_lido_com_passphrase_sem_cr(tmp_path):
    _write_legacy_file(
        tmp_path,
        'senha-legada\r',
        {'svc': {'user': 'valor-legado'}},
    )
    backend = _backend(tmp_path, passphrase='senha-legada')
    assert backend.get_password('svc', 'user') == 'valor-legado'


def test_legado_crlf_e_lido_quando_runtime_preserva_cr(tmp_path):
    _write_legacy_file(
        tmp_path,
        'senha-legada\r',
        {'svc': {'user': 'valor-legado'}},
    )
    backend = _backend(tmp_path, passphrase='senha-legada\r')
    assert backend.get_password('svc', 'user') == 'valor-legado'


def test_primeira_gravacao_migra_legado_crlf_para_forma_canonica(tmp_path):
    _write_legacy_file(
        tmp_path,
        'senha-legada\r',
        {'svc': {'user': 'valor-legado'}},
    )

    backend = _backend(tmp_path, passphrase='senha-legada\r')
    backend.set_password('svc', 'novo', 'valor-novo')

    raw = backend._path.read_bytes()
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    plaintext = AESGCM(_derive_key('senha-legada')).decrypt(nonce, ciphertext, None)
    data = json.loads(plaintext.decode('utf-8'))

    assert data['svc']['user'] == 'valor-legado'
    assert data['svc']['novo'] == 'valor-novo'
