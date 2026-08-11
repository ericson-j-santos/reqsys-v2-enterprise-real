"""Testes do cofre standalone (scripts/cofre_vault_standalone.py).

Usa um FakeKeyring em memoria (monkeypatch) - nunca toca o Credential
Manager/Secret Service real da maquina que roda os testes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cofre_vault_standalone as cofre  # noqa: E402


class FakeKeyring:
    """Substituto em memoria para o modulo `keyring`, isolado por teste."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, key: str):
        return self._store.get((service, key))

    def set_password(self, service: str, key: str, value: str) -> None:
        self._store[(service, key)] = value

    def delete_password(self, service: str, key: str) -> None:
        if (service, key) not in self._store:
            raise RuntimeError("credential not found")
        del self._store[(service, key)]


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(cofre, "keyring", fake)
    monkeypatch.setenv("REQSYS_VAULT_SERVICE_NAME", "teste-cofre-pytest")
    return fake


def test_vault_starts_uninitialized():
    assert cofre.vault_initialized() is False


def test_init_vault_creates_master_key():
    assert cofre.init_vault() is True
    assert cofre.vault_initialized() is True


def test_init_vault_without_force_does_not_overwrite():
    cofre.init_vault()
    assert cofre.init_vault() is False


def test_init_vault_with_force_overwrites():
    cofre.init_vault()
    cofre.write_secret("FOO", "valor-antigo")
    assert cofre.init_vault(overwrite=True) is True
    # master key nova -> segredo gravado com a chave antiga nao decripta mais
    assert cofre.read_secret("FOO") is None


def test_write_before_init_raises():
    with pytest.raises(RuntimeError):
        cofre.write_secret("FOO", "bar")


def test_write_empty_key_raises():
    cofre.init_vault()
    with pytest.raises(ValueError):
        cofre.write_secret("", "valor")


def test_write_reserved_key_raises():
    cofre.init_vault()
    with pytest.raises(ValueError):
        cofre.write_secret("__master_key__", "valor")
    with pytest.raises(ValueError):
        cofre.write_secret("__index__", "valor")


def test_write_and_read_roundtrip():
    cofre.init_vault()
    cofre.write_secret("FOO", "bar-secreto")
    assert cofre.read_secret("FOO") == "bar-secreto"


def test_read_missing_key_returns_none():
    cofre.init_vault()
    assert cofre.read_secret("NAO_EXISTE") is None


def test_read_without_init_returns_none():
    assert cofre.read_secret("QUALQUER") is None


def test_list_secrets_tracks_writes_and_deletes():
    cofre.init_vault()
    cofre.write_secret("A", "1")
    cofre.write_secret("B", "2")
    assert cofre.list_secrets() == ["A", "B"]
    cofre.delete_secret("A")
    assert cofre.list_secrets() == ["B"]


def test_list_secrets_no_duplicates_on_rewrite():
    cofre.init_vault()
    cofre.write_secret("A", "1")
    cofre.write_secret("A", "2")  # sobrescreve valor, nao deve duplicar no indice
    assert cofre.list_secrets() == ["A"]
    assert cofre.read_secret("A") == "2"


def test_delete_missing_key_returns_false():
    cofre.init_vault()
    assert cofre.delete_secret("NAO_EXISTE") is False


def test_delete_existing_key_returns_true():
    cofre.init_vault()
    cofre.write_secret("A", "1")
    assert cofre.delete_secret("A") is True
    assert cofre.read_secret("A") is None


def test_dashboard_html_lists_keys_not_values():
    cofre.init_vault()
    marcador_secreto = "SEGREDO-UNICO-NAO-DEVE-VAZAR-9f8e7d"
    cofre.write_secret("JWT_SECRET", marcador_secreto)
    html_out = cofre._build_dashboard_html(
        cofre._service_name(), True, cofre.list_secrets()
    )
    assert "JWT_SECRET" in html_out
    assert marcador_secreto not in html_out
    assert "<html" in html_out and "</html>" in html_out


def test_dashboard_html_uninitialized_state():
    html_out = cofre._build_dashboard_html(cofre._service_name(), False, [])
    assert "NAO INICIALIZADO" in html_out
    assert "Nenhum segredo gravado" in html_out


def test_dashboard_command_writes_file(tmp_path):
    cofre.init_vault()
    marcador_secreto = "OUTRO-MARCADOR-SECRETO-XYZ123"
    cofre.write_secret("API_KEY", marcador_secreto)

    output = tmp_path / "dashboard.html"
    args = type("Args", (), {"output": str(output)})()
    cofre.cmd_dashboard(args)

    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "API_KEY" in content
    assert marcador_secreto not in content


def test_cmd_gen_token_prints_urlsafe_token(capsys):
    cofre.cmd_gen_token(None)
    out = capsys.readouterr().out
    assert out.startswith("VAULT_API_TOKEN=")
    token = out.strip().split("=", 1)[1]
    assert len(token) >= 32
