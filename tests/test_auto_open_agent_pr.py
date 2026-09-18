from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from scripts.auto_open_agent_pr import (
    GitHubClient,
    ReadyForPrBlocked,
    build_body,
    create_pr_best_effort,
    is_permission_error,
    load_branch_pr_metadata,
    main,
    resolve_token,
    skip_existing_pr,
    sync_existing_pr,
    wait_for_ready_for_pr,
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


def test_wait_for_ready_for_pr_accepts_same_sha_and_current_base():
    class FakeClient:
        def list_pre_pr_readiness_runs(self, head_sha: str):
            return [
                {
                    "id": 77,
                    "html_url": "https://github.com/example/repo/actions/runs/77",
                    "head_sha": head_sha,
                    "status": "completed",
                    "conclusion": "success",
                }
            ]

        def get_branch_sha(self, branch: str):
            assert branch == "main"
            return "base-sha"

        def compare(self, base_sha: str, head_sha: str):
            assert base_sha == "base-sha"
            assert head_sha == "head-sha"
            return {"behind_by": 0, "ahead_by": 2, "status": "ahead"}

    evidence = wait_for_ready_for_pr(
        FakeClient(),  # type: ignore[arg-type]
        head_sha="head-sha",
        base="main",
        wait_seconds=0,
        poll_seconds=0.01,
    )
    assert evidence["status"] == "passed"
    assert evidence["run_id"] == 77
    assert evidence["base_sha"] == "base-sha"


def test_wait_for_ready_for_pr_blocks_failed_run():
    class FakeClient:
        def list_pre_pr_readiness_runs(self, head_sha: str):
            return [
                {
                    "id": 88,
                    "html_url": "https://github.com/example/repo/actions/runs/88",
                    "head_sha": head_sha,
                    "status": "completed",
                    "conclusion": "failure",
                }
            ]

    with pytest.raises(ReadyForPrBlocked, match="não passou") as exc:
        wait_for_ready_for_pr(
            FakeClient(),  # type: ignore[arg-type]
            head_sha="head-sha",
            base="main",
            wait_seconds=0,
            poll_seconds=0.01,
        )
    assert exc.value.evidence["reason"] == "ready_for_pr_run_not_successful"


def test_wait_for_ready_for_pr_blocks_missing_run():
    class FakeClient:
        def list_pre_pr_readiness_runs(self, head_sha: str):
            return []

    with pytest.raises(ReadyForPrBlocked, match="não foi encontrado") as exc:
        wait_for_ready_for_pr(
            FakeClient(),  # type: ignore[arg-type]
            head_sha="head-sha",
            base="main",
            wait_seconds=0,
            poll_seconds=0.01,
        )
    assert exc.value.evidence["reason"] == "ready_for_pr_run_missing_or_pending"


def test_wait_for_ready_for_pr_blocks_when_main_advanced():
    class FakeClient:
        def list_pre_pr_readiness_runs(self, head_sha: str):
            return [
                {
                    "id": 99,
                    "html_url": "https://github.com/example/repo/actions/runs/99",
                    "head_sha": head_sha,
                    "status": "completed",
                    "conclusion": "success",
                }
            ]

        def get_branch_sha(self, branch: str):
            return "new-main"

        def compare(self, base_sha: str, head_sha: str):
            return {"behind_by": 1, "ahead_by": 2, "status": "diverged"}

    with pytest.raises(ReadyForPrBlocked, match="reconciliar") as exc:
        wait_for_ready_for_pr(
            FakeClient(),  # type: ignore[arg-type]
            head_sha="head-sha",
            base="main",
            wait_seconds=0,
            poll_seconds=0.01,
        )
    assert exc.value.evidence["reason"] == "base_not_ancestor_of_head"


def test_main_blocks_new_pr_without_ready_for_pr(monkeypatch, tmp_path):
    class FakeClient:
        created = False

        def find_existing_pr(self, head: str, base: str):
            return None

        def list_pre_pr_readiness_runs(self, head_sha: str):
            return []

        def create_pr(self, **kwargs):
            self.created = True
            raise AssertionError("create_pr não deveria ser chamado")

    fake = FakeClient()
    monkeypatch.setenv("GITHUB_REPOSITORY", "ericson-j-santos/reqsys-v2-enterprise-real")
    monkeypatch.setenv("GITHUB_REF_NAME", "cursor/novo-incremento")
    monkeypatch.setenv("GITHUB_SHA", "sha-sem-gate")
    monkeypatch.setenv("GH_TOKEN", "token-teste")
    monkeypatch.setenv("READY_FOR_PR_WAIT_SECONDS", "0")
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr("scripts.auto_open_agent_pr.GitHubClient", lambda token, repo: fake)
    monkeypatch.setattr("sys.argv", ["auto_open_agent_pr.py", "--base", "main"])

    assert main() == 3
    assert fake.created is False
    request = json.loads((tmp_path / "auto-pr-request.json").read_text(encoding="utf-8"))
    readiness = json.loads((tmp_path / "ready-for-pr-verification.json").read_text(encoding="utf-8"))
    assert request["status"] == "blocked_readiness"
    assert readiness["status"] == "blocked"
    assert readiness["head_sha"] == "sha-sem-gate"


def test_main_creates_new_pr_only_after_ready_for_pr(monkeypatch, tmp_path):
    class FakeClient:
        created_payload = None

        def find_existing_pr(self, head: str, base: str):
            return None

        def list_pre_pr_readiness_runs(self, head_sha: str):
            return [
                {
                    "id": 123,
                    "html_url": "https://github.com/example/repo/actions/runs/123",
                    "head_sha": head_sha,
                    "status": "completed",
                    "conclusion": "success",
                }
            ]

        def get_branch_sha(self, branch: str):
            return "main-sha"

        def compare(self, base_sha: str, head_sha: str):
            return {"behind_by": 0, "ahead_by": 1, "status": "ahead"}

        def create_pr(self, **kwargs):
            self.created_payload = kwargs
            return {"number": 500, "html_url": "https://github.com/example/repo/pull/500"}

        def add_labels(self, number: int, labels: list[str]):
            return None

    fake = FakeClient()
    monkeypatch.setenv("GITHUB_REPOSITORY", "ericson-j-santos/reqsys-v2-enterprise-real")
    monkeypatch.setenv("GITHUB_REF_NAME", "cursor/novo-incremento")
    monkeypatch.setenv("GITHUB_SHA", "head-sha")
    monkeypatch.setenv("GH_TOKEN", "token-teste")
    monkeypatch.setenv("READY_FOR_PR_WAIT_SECONDS", "0")
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr("scripts.auto_open_agent_pr.GitHubClient", lambda token, repo: fake)
    monkeypatch.setattr("sys.argv", ["auto_open_agent_pr.py", "--base", "main"])

    assert main() == 0
    assert fake.created_payload is not None
    assert "## READY_FOR_PR" in fake.created_payload["body"]
    assert "head-sha" in fake.created_payload["body"]
    request = json.loads((tmp_path / "auto-pr-request.json").read_text(encoding="utf-8"))
    readiness = json.loads((tmp_path / "ready-for-pr-verification.json").read_text(encoding="utf-8"))
    assert request["status"] == "created"
    assert readiness["status"] == "passed"
    assert readiness["run_id"] == 123
