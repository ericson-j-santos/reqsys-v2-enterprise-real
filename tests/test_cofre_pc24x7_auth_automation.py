from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pytest

from scripts import cofre_human_token as human
from scripts import cofre_runtime_evidence as runtime


def test_bootstrap_reader_with_token_persists_only_scoped_reader(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(human, "VAULT_TOKEN_DIR", tmp_path)
    monkeypatch.setattr(human, "_decode_jwt_exp", lambda token: int(time.time()) + 3600)

    captured: dict[str, object] = {}

    def fake_request(method: str, url: str, *, headers: dict[str, str], body: dict | None = None) -> dict:
        captured.update(method=method, url=url, headers=headers, body=body)
        return {"data": {"token": "scoped-reader-token"}}

    monkeypatch.setattr(human, "_http_request", fake_request)

    path = human._bootstrap_reader_with_token("dev", "http://localhost:8210", "admin.jwt.value")

    assert path == tmp_path / "vault-token-dev.local"
    assert path.read_text(encoding="utf-8").strip() == "scoped-reader-token"
    assert captured["url"] == "http://localhost:8210/v1/cofre/tokens"
    assert captured["body"] == {
        "label": "human-jwt-reader-dev",
        "key_patterns": ["human_admin_jwt:dev"],
    }
    assert "admin.jwt.value" not in path.read_text(encoding="utf-8")


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "phase": "before-restart",
        "base_url": "http://localhost:8210",
        "environment": "dev",
        "admin_jwt": "already-provided",
        "admin_jwt_reader_token_file": None,
        "state_key": "",
        "state_key_file": str(tmp_path / "runtime.fernet"),
        "timeout": 20,
        "correlation_id": "test-cofre-pc24x7",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_before_restart_generates_ephemeral_fernet_key_file(tmp_path: Path) -> None:
    args = _args(tmp_path)

    runtime._resolve_runtime_credentials(args)

    key_path = Path(args.state_key_file)
    assert key_path.exists()
    assert key_path.read_text(encoding="ascii").strip() == args.state_key
    runtime.Fernet(args.state_key.encode("ascii"))


def test_after_restart_requires_existing_ephemeral_key(tmp_path: Path) -> None:
    args = _args(tmp_path, phase="after-restart")

    with pytest.raises(runtime.GateError, match="não encontrado"):
        runtime._resolve_runtime_credentials(args)


def test_admin_jwt_is_loaded_from_scoped_reader_without_printing_secret(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reader = tmp_path / "vault-token-dev.local"
    reader.write_text("scoped-reader-token\n", encoding="utf-8")
    exp = int(time.time()) + 3600

    def fake_request(self, method: str, path: str, **kwargs: object) -> runtime.HttpResponse:
        assert method == "GET"
        assert path == "/v1/cofre/segredos/human_admin_jwt:dev"
        assert kwargs["vault_token"] == "scoped-reader-token"
        stored = json.dumps({"token": "fresh-admin-jwt", "exp": exp, "environment": "dev"})
        return runtime.HttpResponse(status=200, payload={"data": {"value": stored}})

    monkeypatch.setattr(runtime.ApiClient, "request", fake_request)
    args = _args(
        tmp_path,
        admin_jwt="",
        admin_jwt_reader_token_file=str(reader),
    )

    runtime._resolve_runtime_credentials(args)

    assert args.admin_jwt == "fresh-admin-jwt"
    output = capsys.readouterr()
    assert "fresh-admin-jwt" not in output.out
    assert "fresh-admin-jwt" not in output.err
