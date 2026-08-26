"""Testes unitários para app.core.keyring_backend (FileEncryptedKeyring)."""
from __future__ import annotations

import keyring.errors
import pytest

from app.core.keyring_backend import FileEncryptedKeyring


def _backend(tmp_path, passphrase: str = 'senha-de-teste-bem-forte') -> FileEncryptedKeyring:
    return FileEncryptedKeyring(path=str(tmp_path), passphrase=passphrase)


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


def test_set_password_com_arquivo_corrompido_reinicia_vault(tmp_path):
    backend = _backend(tmp_path)
    backend._path.parent.mkdir(parents=True, exist_ok=True)
    backend._path.write_bytes(b'lixo-nao-decifravel-0123456789ab')
    backend.set_password('svc', 'user', 'valor-novo')
    assert backend.get_password('svc', 'user') == 'valor-novo'
