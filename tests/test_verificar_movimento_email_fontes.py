from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verificar_movimento_email_fontes.py"

spec = importlib.util.spec_from_file_location("verificar_movimento_email_fontes", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_le_dsn_e_timeout_diretamente_do_ambiente(monkeypatch) -> None:
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_DSN", "  Driver=ODBC;Server=sql  ")
    monkeypatch.setenv("MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS", "12.5")

    assert module._source_dsn() == "Driver=ODBC;Server=sql"
    assert module._query_timeout_seconds() == 12.5


def test_timeout_invalido_volta_ao_padrao(monkeypatch) -> None:
    monkeypatch.setenv("MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS", "invalido")

    assert module._query_timeout_seconds() == 30.0


def test_status_sem_dsn_falha_sem_depender_do_backend(monkeypatch, capsys) -> None:
    monkeypatch.delenv("MOVIMENTO_EMAIL_SOURCE_DSN", raising=False)

    assert module.cmd_status(None) == 1
    saida = capsys.readouterr().out

    assert "MOVIMENTO_EMAIL_SOURCE_DSN não configurado" in saida


def test_status_com_dsn_nao_expoe_valor(monkeypatch, capsys) -> None:
    dsn = "Driver=ODBC;Server=sql;UID=svc;PWD=segredo"
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_DSN", dsn)

    assert module.cmd_status(None) == 0
    saida = capsys.readouterr().out

    assert "MOVIMENTO_EMAIL_SOURCE_DSN configurado" in saida
    assert dsn not in saida
    assert "segredo" not in saida
