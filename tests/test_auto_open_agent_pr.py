from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from scripts.auto_open_agent_pr import (
    GitHubClient,
    build_body,
    create_pr_best_effort,
    is_permission_error,
    load_branch_pr_metadata,
    main,
    resolve_token,
    skip_existing_pr,
    sync_existing_pr,
)


def test_build_body_contains_increment_type():
    body = build_body("cursor/padrao-ouro-ciclos-88ba", "main")
    assert "increment-type: consolidate" in body
    assert "cursor/padrao-ouro-ciclos-88ba" in body
    assert "Padrão Ouro Delivery Automation" in body


def test_is_permission_error_detects_403():
    assert is_permission_error(RuntimeError('GitHub API PATCH /pulls/461 failed (403): {"message":"forbidden"}'))
    assert is_permission_error(RuntimeError('GitHub API POST /pulls failed (403): {"message":"forbidden"}'))


def test_resolve_token_prefers_gh_token_over_pat(monkeypatch):
    monkeypatch.setenv("GH_PAT_ACTIONS", "pat-limitado")
    monkeypatch.setenv("GH_TOKEN", "token-workflow")
    assert resolve_token() == "token-workflow"


def test_find_existing_pr_url_encodes_branch_com_barra():
    client = GitHubClient("token", "owner/repo")
    captured: dict[str, str] = {}

    def fake_request(method: str, path: str, payload=None):
        captured["method"] = method
        captured["path"] = path
        return []

    client._request = fake_request  # type: ignore[method-assign]
    assert client.find_existing_pr("cursor/coverage-targeted-tests-ddbb", "main") is None
    assert captured["method"] == "GET"
    assert "head=owner%3Acursor%2Fcoverage-targeted-tests-ddbb" in captured["path"]
    assert "base=main" in captured["path"]


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


def test_skip_existing_pr_quando_pr_ja_mergeado(tmp_path, monkeypatch):
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    existing = {
        "number": 461,
        "html_url": "https://github.com/example/repo/pull/461",
        "state": "closed",
        "merged_at": "2026-06-28T00:00:00Z",
    }

    exit_code = skip_existing_pr(
        branch="cursor/consume-governance-cards-monitoramento-36e0",
        base="main",
        title="feat: teste",
        body="body",
        existing=existing,
    )

    assert exit_code == 0
    artifact = (tmp_path / "auto-pr-request.json").read_text(encoding="utf-8")
    assert "skipped_merged" in artifact


def test_create_pr_best_effort_ignora_403(tmp_path, monkeypatch):
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    client = MagicMock()
    client.create_pr.side_effect = RuntimeError(
        'GitHub API POST /pulls failed (403): {"message":"Resource not accessible by personal access token"}'
    )

    exit_code = create_pr_best_effort(
        client,
        branch="cursor/teste-36e0",
        base="main",
        title="feat: teste",
        body="body",
    )

    assert exit_code == 0
    artifact = (tmp_path / "auto-pr-request.json").read_text(encoding="utf-8")
    assert "skipped_permission" in artifact


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
        def find_existing_pr(self, head: str, base: str):
            return {"number": 469, "html_url": "https://github.com/example/repo/pull/469", "state": "open"}

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


def test_load_branch_pr_metadata_reads_json(tmp_path, monkeypatch):
    metadata_dir = tmp_path / ".github" / "pr-metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "cursor-gap-fix-consolidator-71ed.json").write_text(
        json.dumps({"title": "fix(ci): titulo", "body": "corpo customizado"}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    payload = load_branch_pr_metadata("cursor/gap-fix-consolidator-71ed")
    assert payload == {"title": "fix(ci): titulo", "body": "corpo customizado"}


def test_main_uses_branch_metadata_when_present(tmp_path, monkeypatch):
    metadata_dir = tmp_path / ".github" / "pr-metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "cursor-gap-fix-consolidator-71ed.json").write_text(
        json.dumps(
            {
                "title": "fix(ci): corrigir PR Conflict Guard com checkout do head SHA",
                "body": "descricao canonica do PR",
            }
        ),
        encoding="utf-8",
    )

    class FakeClient:
        def find_existing_pr(self, head: str, base: str):
            return {"number": 471, "state": "open", "html_url": "https://example/pr/471"}

        def update_pr(self, number: int, *, title: str, body: str):
            self.updated = {"number": number, "title": title, "body": body}

        def add_labels(self, number: int, labels: list[str]):
            return None

    fake = FakeClient()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "ericson-j-santos/reqsys-v2-enterprise-real")
    monkeypatch.setenv("GITHUB_REF_NAME", "cursor/gap-fix-consolidator-71ed")
    monkeypatch.setenv("GH_TOKEN", "token-teste")
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr("scripts.auto_open_agent_pr.GitHubClient", lambda token, repo: fake)
    monkeypatch.setattr("sys.argv", ["auto_open_agent_pr.py", "--base", "main"])

    assert main() == 0
    assert fake.updated["title"] == "fix(ci): corrigir PR Conflict Guard com checkout do head SHA"
    assert fake.updated["body"] == "descricao canonica do PR"
