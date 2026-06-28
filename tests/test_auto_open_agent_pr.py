import json
from pathlib import Path

import pytest

from scripts.auto_open_agent_pr import (
    GitHubClient,
    build_body,
    is_github_permission_error,
    main,
    update_pr_best_effort,
)


def test_build_body_contains_increment_type():
    body = build_body("cursor/padrao-ouro-ciclos-88ba", "main")
    assert "increment-type: consolidate" in body
    assert "cursor/padrao-ouro-ciclos-88ba" in body
    assert "Padrão Ouro Delivery Automation" in body


def test_is_github_permission_error_detecta_403():
    exc = RuntimeError(
        'GitHub API PATCH /pulls/469 failed (403): {"message":"Resource not accessible by personal access token"}'
    )
    assert is_github_permission_error(exc) is True


def test_update_pr_best_effort_ignora_403():
    class FakeClient:
        def update_pr(self, number: int, *, title: str, body: str) -> dict:
            raise RuntimeError("GitHub API PATCH /pulls/469 failed (403): forbidden")

    assert update_pr_best_effort(FakeClient(), 469, title="t", body="b") is False


def test_update_pr_best_effort_propaga_outros_erros():
    class FakeClient:
        def update_pr(self, number: int, *, title: str, body: str) -> dict:
            raise RuntimeError("GitHub API PATCH /pulls/469 failed (422): invalid")

    with pytest.raises(RuntimeError, match="422"):
        update_pr_best_effort(FakeClient(), 469, title="t", body="b")


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
    assert artifact["error"] is None


def test_main_atualiza_pr_existente_quando_token_tem_permissao(monkeypatch, tmp_path):
    class FakeClient:
        updated = False

        def find_open_pr(self, head: str, base: str):
            return {"number": 12, "html_url": "https://github.com/example/repo/pull/12"}

        def update_pr(self, number: int, *, title: str, body: str):
            self.updated = True
            return {"number": number}

        def add_labels(self, number: int, labels: list[str]):
            return None

    monkeypatch.setenv("GITHUB_REPOSITORY", "ericson-j-santos/reqsys-v2-enterprise-real")
    monkeypatch.setenv("GITHUB_REF_NAME", "cursor/test-branch")
    monkeypatch.setenv("GH_TOKEN", "token-teste")
    monkeypatch.setenv("PR_REQUEST_ARTIFACT_DIR", str(tmp_path))
    fake = FakeClient()
    monkeypatch.setattr("scripts.auto_open_agent_pr.GitHubClient", lambda token, repo: fake)
    monkeypatch.setattr("sys.argv", ["auto_open_agent_pr.py", "--base", "main", "--title", "feat: teste"])

    assert main() == 0
    assert fake.updated is True
    artifact_path = Path(tmp_path / "auto-pr-request.json")
    assert artifact_path.is_file()
