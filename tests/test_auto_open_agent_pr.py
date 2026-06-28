from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.auto_open_agent_pr import build_body, is_permission_error, main, sync_existing_pr


def test_build_body_contains_increment_type():
    body = build_body("cursor/padrao-ouro-ciclos-88ba", "main")
    assert "increment-type: consolidate" in body
    assert "cursor/padrao-ouro-ciclos-88ba" in body
    assert "Padrão Ouro Delivery Automation" in body


def test_is_permission_error_detects_403():
    assert is_permission_error(RuntimeError('GitHub API PATCH /pulls/461 failed (403): {"message":"forbidden"}'))


def test_sync_existing_pr_ignora_403_quando_pr_ja_existe(tmp_path, monkeypatch):
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    client = MagicMock()
    client.update_pr.side_effect = RuntimeError(
        'GitHub API PATCH /pulls/461 failed (403): {"message":"Resource not accessible by personal access token"}'
    )
    existing = {"number": 461, "html_url": "https://github.com/example/repo/pull/461"}

    exit_code = sync_existing_pr(
        client,
        existing,
        branch="cursor/consume-governance-cards-monitoramento-36e0",
        base="main",
        title="feat: teste",
        body="body",
    )

    assert exit_code == 0
    artifact = (tmp_path / "auto-pr-request.json").read_text(encoding="utf-8")
    assert "skipped_permission" in artifact
    assert "461" in artifact


def test_sync_existing_pr_atualiza_quando_token_tem_permissao(tmp_path, monkeypatch):
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    client = MagicMock()
    existing = {"number": 12, "html_url": "https://github.com/example/repo/pull/12"}

    exit_code = sync_existing_pr(
        client,
        existing,
        branch="cursor/test-branch",
        base="main",
        title="feat: teste",
        body="body",
    )

    assert exit_code == 0
    client.update_pr.assert_called_once()
    artifact = json.loads((tmp_path / "auto-pr-request.json").read_text(encoding="utf-8"))
    assert artifact["status"] == "updated"
    assert artifact["pr_number"] == 12


def test_sync_existing_pr_propaga_erros_nao_relacionados_a_permissao():
    client = MagicMock()
    client.update_pr.side_effect = RuntimeError("GitHub API PATCH /pulls/12 failed (422): invalid")
    existing = {"number": 12, "html_url": "https://github.com/example/repo/pull/12"}

    with pytest.raises(RuntimeError, match="422"):
        sync_existing_pr(
            client,
            existing,
            branch="cursor/test-branch",
            base="main",
            title="feat: teste",
            body="body",
        )


def test_main_sucesso_quando_pr_ja_existe_mas_update_retorna_403(monkeypatch, tmp_path):
    class FakeClient:
        def find_open_pr(self, head: str, base: str):
            return {"number": 469, "html_url": "https://github.com/example/repo/pull/469"}

        def update_pr(self, number: int, *, title: str, body: str):
            raise RuntimeError("GitHub API PATCH /pulls/469 failed (403): forbidden")

        def add_labels(self, number: int, labels: list[str]):
            return None

    monkeypatch.setenv("GITHUB_REPOSITORY", "ericson-j-santos/reqsys-v2-enterprise-real")
    monkeypatch.setenv("GITHUB_REF_NAME", "cursor/coverage-targeted-tests-ddbb")
    monkeypatch.setenv("GH_TOKEN", "token-teste")
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr("scripts.auto_open_agent_pr.GitHubClient", lambda token, repo: FakeClient())
    monkeypatch.setattr("sys.argv", ["auto_open_agent_pr.py", "--base", "main"])

    assert main() == 0
    artifact = json.loads((tmp_path / "auto-pr-request.json").read_text(encoding="utf-8"))
    assert artifact["branch"] == "cursor/coverage-targeted-tests-ddbb"
    assert artifact["status"] == "skipped_permission"
