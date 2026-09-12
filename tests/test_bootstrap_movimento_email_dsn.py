from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "bootstrap_movimento_email_dsn.py"
spec = importlib.util.spec_from_file_location("bootstrap_movimento_email_dsn", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class Proc:
    def __init__(self, rc=0, out=""):
        self.returncode = rc
        self.stdout = out
        self.stderr = ""


def test_bloqueia_sem_credenciais(monkeypatch):
    monkeypatch.setattr(module, "_secret", lambda vault, name: "")
    result = module.bootstrap(
        vault="kv", server="sql", database="db",
        username_secret="user", password_secret="pass",
        dsn_secret_name="dsn", dry_run=True,
    )
    assert result.status == "blocked"
    assert result.username_secret_present is False
    assert result.password_secret_present is False


def test_dry_run_nao_grava_dsn(monkeypatch):
    monkeypatch.setattr(module, "_secret", lambda vault, name: "svc" if name == "user" else "super-secret")
    calls = []
    monkeypatch.setattr(module, "_run", lambda args, input_text=None: calls.append(args) or Proc())
    result = module.bootstrap(
        vault="kv", server="sql", database="db",
        username_secret="user", password_secret="pass",
        dsn_secret_name="dsn", dry_run=True,
    )
    assert result.status == "ready"
    assert calls == []


def test_grava_dsn_somente_no_keyvault(monkeypatch):
    monkeypatch.setattr(module, "_secret", lambda vault, name: "svc" if name == "user" else "super-secret")
    calls = []
    monkeypatch.setattr(module, "_run", lambda args, input_text=None: calls.append(args) or Proc())
    result = module.bootstrap(
        vault="kv", server="sql.internal", database="movimento",
        username_secret="user", password_secret="pass",
        dsn_secret_name="movimento-email-source-dsn", dry_run=False,
    )
    assert result.status == "ready"
    assert len(calls) == 1
    joined = " ".join(calls[0])
    assert "keyvault secret set" in joined
    assert "Encrypt=yes" in joined
    assert "TrustServerCertificate=no" in joined


def test_dsn_exige_todos_os_campos():
    with pytest.raises(module.BootstrapError, match="INPUT_INCOMPLETE"):
        module._build_dsn("sql", "db", "", "pwd")
