"""Testes de caminhos críticos — cliente GitHub para integrações."""

from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from app.services import github_client
from app.services.github_client import GitHubError


def test_parse_repo_valido_e_invalido():
    assert github_client._parse_repo("owner/repo") == ("owner", "repo")
    assert github_client._parse_repo("/owner/repo/") == ("owner", "repo")

    with pytest.raises(GitHubError, match="Repo invalido"):
        github_client._parse_repo("repo-sem-owner")


def test_request_json_sem_token():
    with patch("app.services.github_client.get_secret", return_value=""):
        with pytest.raises(GitHubError, match="GITHUB_TOKEN"):
            github_client._request_json("GET", "/repos/o/r/issues")


def test_request_json_http_error():
    with patch("app.services.github_client.get_secret", return_value="token-teste"):
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.side_effect = HTTPError(
                url="https://api.github.com/test",
                code=403,
                msg="Forbidden",
                hdrs=None,
                fp=MagicMock(read=lambda: b"rate limit"),
            )
            with pytest.raises(GitHubError, match="HTTP 403"):
                github_client._request_json("GET", "/repos/o/r/issues")


def test_request_json_url_error():
    with patch("app.services.github_client.get_secret", return_value="token-teste"):
        with patch("urllib.request.urlopen", side_effect=URLError("timeout")):
            with pytest.raises(GitHubError, match="Falha de rede"):
                github_client._request_json("GET", "/repos/o/r/issues")


def test_list_issues_filtra_pull_requests():
    payload = [
        {"number": 1, "title": "issue pura"},
        {"number": 2, "title": "pull", "pull_request": {"url": "https://example.com/pr/2"}},
    ]
    with patch("app.services.github_client._request_json", return_value=payload):
        issues = github_client.list_issues("acme/repo", limit=50)

    assert len(issues) == 1
    assert issues[0]["number"] == 1


def test_create_e_update_issue():
    with patch("app.services.github_client._request_json", return_value={"number": 9}) as request_json:
        created = github_client.create_issue("acme/repo", "Titulo", "Corpo", labels=["bug"])
        updated = github_client.update_issue("acme/repo", 9, state="closed")

    assert created["number"] == 9
    assert updated["number"] == 9
    assert request_json.call_args_list[0][0][2]["labels"] == ["bug"]


def test_request_json_post_com_payload_vazio():
    mock_resp = MagicMock()
    mock_resp.read.return_value = ""
    mock_resp.__enter__.return_value = mock_resp

    with patch("app.services.github_client.get_secret", return_value="token-teste"):
        with patch("urllib.request.urlopen", return_value=mock_resp) as urlopen:
            resultado = github_client._request_json("POST", "/repos/o/r/issues", payload={"titulo": "x"})

    assert resultado == {}
    sent_request = urlopen.call_args[0][0]
    assert sent_request.get_header("Content-type") == "application/json"


def test_find_issue_by_marker():
    issues = [{"body": "sem marcador"}, {"body": "contem REQ-FIGMA-001 aqui"}]
    with patch("app.services.github_client.list_issues", return_value=issues):
        encontrada = github_client.find_issue_by_marker("acme/repo", "REQ-FIGMA-001")

    assert encontrada["body"].startswith("contem")


def test_find_issue_by_marker_retorna_none_quando_ausente():
    with patch("app.services.github_client.list_issues", return_value=[{"body": "sem marcador"}]):
        assert github_client.find_issue_by_marker("acme/repo", "REQ-404") is None


def test_get_branch_sha_retorna_none_em_404():
    with patch(
        "app.services.github_client._request_json",
        side_effect=GitHubError("HTTP 404 no GitHub: not found"),
    ):
        assert github_client.get_branch_sha("acme/repo", "feature-x") is None


def test_create_branch_envia_ref():
    with patch("app.services.github_client._request_json", return_value={"ref": "refs/heads/nova"}) as request_json:
        resposta = github_client.create_branch("acme/repo", "nova", "sha123")

    assert resposta["ref"] == "refs/heads/nova"
    assert request_json.call_args[0][2]["sha"] == "sha123"


def test_create_issue_comment_e_get_branch_sha_propaga_erro():
    with patch("app.services.github_client._request_json", return_value={"id": 1}) as request_json:
        comentario = github_client.create_issue_comment("acme/repo", 9, "comentario")

    assert comentario["id"] == 1
    assert request_json.call_args[0][1] == "/repos/acme/repo/issues/9/comments"

    with patch(
        "app.services.github_client._request_json",
        side_effect=github_client.GitHubError("HTTP 500 no GitHub"),
    ):
        with pytest.raises(github_client.GitHubError):
            github_client.get_branch_sha("acme/repo", "main")


def test_github_token_configurado():
    with patch("app.services.github_client.get_secret", return_value="  token  "):
        assert github_client.github_token_configurado() is True
    with patch("app.services.github_client.get_secret", return_value=""):
        assert github_client.github_token_configurado() is False
