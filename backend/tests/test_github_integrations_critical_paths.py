"""Testes de caminhos críticos — integrações GitHub (versão e Redmine)."""

import hashlib
import json
from base64 import b64encode
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from app.services import github_redmine, github_version_checker
from app.services.github_redmine import IntegracaoError


@pytest.fixture(autouse=True)
def _circuit_breaker_isolado():
    github_version_checker.reset_circuit_breaker()
    yield
    github_version_checker.reset_circuit_breaker()


def test_github_redmine_import_enabled_respeita_env(monkeypatch):
    monkeypatch.setenv("ENABLE_GITHUB_REDMINE_IMPORT", "false")
    assert github_redmine.github_redmine_import_enabled() is False
    monkeypatch.setenv("ENABLE_GITHUB_REDMINE_IMPORT", "yes")
    assert github_redmine.github_redmine_import_enabled() is True


def test_github_redmine_parse_repo_invalido():
    with pytest.raises(IntegracaoError, match="Repo inválido"):
        github_redmine._parse_repo("invalido")


def test_fetch_github_issues_filtra_pull_requests_e_aplica_labels():
    payload = [
        {
            "id": 1,
            "number": 1,
            "title": "Issue",
            "state": "open",
            "html_url": "https://example.com/1",
            "labels": [{"name": "bug"}],
        },
        {"id": 2, "number": 2, "pull_request": {"url": "https://example.com/pr/2"}},
    ]
    with patch("app.services.github_redmine.get_secret", return_value="gh-token"):
        with patch("app.services.github_redmine._request_json", return_value=payload) as request_json:
            issues = github_redmine.fetch_github_issues("acme/repo", labels=[" bug ", ""])

    assert len(issues) == 1
    assert issues[0]["labels"] == ["bug"]
    assert "labels=bug" in request_json.call_args[0][1]


def test_publish_requisito_to_redmine_sem_configuracao():
    requisito = SimpleNamespace(
        codigo="REQ-INT-1",
        titulo="Integração",
        descricao="desc",
        sistema="ReqSys",
        area="TI",
        solicitante="pytest",
        urgencia="alta",
        impacto_regulatorio=True,
    )
    with patch("app.services.github_redmine.get_secret", return_value=""):
        resultado = github_redmine.publish_requisito_to_redmine(requisito)

    assert resultado["issue_principal_id"] is None
    assert "Redmine nao configurado" in resultado["warnings"][0]


def test_publish_requisito_to_redmine_reporta_falha_na_criacao():
    requisito = SimpleNamespace(
        codigo="REQ-INT-3",
        titulo="Falha Redmine",
        descricao="desc",
        sistema="ReqSys",
        area="TI",
        solicitante="pytest",
        urgencia="baixa",
        impacto_regulatorio=False,
    )

    with patch("app.services.github_redmine.get_secret", side_effect=lambda key, default="": {
        "REDMINE_BASE_URL": "https://redmine.example",
        "REDMINE_API_KEY": "key",
        "REDMINE_PROJECT_ID": "7",
    }.get(key, default)):
        with patch(
            "app.services.github_redmine._request_json",
            side_effect=IntegracaoError("HTTP 500"),
        ):
            resultado = github_redmine.publish_requisito_to_redmine(requisito)

    assert resultado["issue_principal_id"] is None
    assert resultado["warnings"]


def test_publish_requisito_to_redmine_cria_issue_e_subtarefas():
    requisito = SimpleNamespace(
        codigo="REQ-INT-2",
        titulo="Integração completa",
        descricao="descricao longa",
        sistema="ReqSys",
        area="TI",
        solicitante="pytest",
        urgencia="media",
        impacto_regulatorio=False,
    )

    def fake_request(method, url, headers=None, payload=None):
        if payload and payload["issue"]["subject"].endswith("Frontend"):
            return {"issue": {"id": 102}}
        return {"issue": {"id": 101}}

    with patch("app.services.github_redmine.get_secret", side_effect=lambda key, default="": {
        "REDMINE_BASE_URL": "https://redmine.example",
        "REDMINE_API_KEY": "key",
        "REDMINE_PROJECT_ID": "7",
    }.get(key, default)):
        with patch("app.services.github_redmine._request_json", side_effect=fake_request):
            resultado = github_redmine.publish_requisito_to_redmine(requisito, tracker_id=3)

    assert resultado["issue_principal_id"] == 101
    assert len(resultado["subtarefas"]) == 4
    assert resultado["subtarefas"][0]["subject"] == "Frontend"


def test_publish_issues_to_redmine_publica_lista():
    issues = [{"number": 10, "title": "Bug", "html_url": "https://gh/10", "labels": ["bug"]}]

    with patch("app.services.github_redmine.get_secret", side_effect=lambda key, default="": {
        "REDMINE_BASE_URL": "https://redmine.example",
        "REDMINE_API_KEY": "key",
        "REDMINE_PROJECT_ID": "7",
    }.get(key, default)):
        with patch(
            "app.services.github_redmine._request_json",
            return_value={"issue": {"id": 500}},
        ):
            resultado = github_redmine.publish_issues_to_redmine("acme/repo", issues)

    assert resultado["published_count"] == 1
    assert resultado["published_issues"][0]["redmine_issue_id"] == 500


def test_verificar_versao_github_arquivo_nao_encontrado():
    with patch("urllib.request.urlopen", side_effect=HTTPError("url", 404, "not found", None, None)):
        resultado = github_version_checker.verificar_versao_github("acme/repo", "docs/a.md", "hash-local")

    assert resultado["status"] == "nao_encontrado"
    assert resultado["hash_reqsys"] == "hash-local"


def test_verificar_versao_github_erro_http():
    with patch("urllib.request.urlopen", side_effect=HTTPError("url", 500, "erro", None, None)):
        resultado = github_version_checker.verificar_versao_github("acme/repo", "docs/a.md", "hash-local")

    assert resultado["status"] == "erro"
    assert "HTTP 500" in resultado["mensagem"]


def test_verificar_versao_github_falha_rede():
    with patch("urllib.request.urlopen", side_effect=URLError("timeout")):
        resultado = github_version_checker.verificar_versao_github("acme/repo", "docs/a.md", "hash-local")

    assert resultado["status"] == "erro"
    assert "Falha ao conectar" in resultado["mensagem"]


def test_verificar_versao_github_sincronizado_e_divergente():
    import json

    conteudo = "conteudo wiki"
    hash_reqsys = hashlib.sha256(conteudo.encode("utf-8")).hexdigest()
    body = json.dumps({"content": b64encode(conteudo.encode("utf-8")).decode("utf-8")})

    mock_resp = MagicMock()
    mock_resp.read.return_value = body.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        sincronizado = github_version_checker.verificar_versao_github("acme/repo", "docs/a.md", hash_reqsys)

    assert sincronizado["status"] == "sincronizado"

    with patch("urllib.request.urlopen", return_value=mock_resp):
        divergente = github_version_checker.verificar_versao_github(
            "acme/repo",
            "docs/a.md",
            "outro-hash",
        )

    assert divergente["status"] == "divergente"
    assert divergente["conteudo_github"] == conteudo


def test_github_redmine_request_json_propaga_erros():
    with patch("urllib.request.urlopen", side_effect=HTTPError("url", 500, "erro", None, MagicMock(read=lambda: b"falha"))):
        with pytest.raises(IntegracaoError, match="HTTP 500"):
            github_redmine._request_json("GET", "https://example.com")

    with patch("urllib.request.urlopen", side_effect=URLError("timeout")):
        with pytest.raises(IntegracaoError, match="Falha de rede"):
            github_redmine._request_json("GET", "https://example.com")


def test_verificar_versao_github_tenta_novamente_apos_falha_transitoria():
    chamadas = {"n": 0}
    sonos = []
    conteudo = "conteudo ok"
    payload = {"content": b64encode(conteudo.encode("utf-8")).decode("ascii")}

    def fake_urlopen(req, timeout):
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise URLError("timeout de rede")
        resp = MagicMock()
        resp.read.return_value = json.dumps(payload).encode("utf-8")
        resp.__enter__.return_value = resp
        return resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        resultado = github_version_checker.verificar_versao_github(
            "acme/repo", "docs/a.md", hashlib.sha256(conteudo.encode("utf-8")).hexdigest(), sleep=sonos.append,
        )

    assert resultado["status"] == "sincronizado"
    assert chamadas["n"] == 3
    assert len(sonos) == 2


def test_verificar_versao_github_nao_retenta_404():
    """HTTPError e subclasse de URLError, mas 404 e um resultado definitivo — nao deve ser retentado."""
    chamadas = {"n": 0}

    def fake_urlopen(req, timeout):
        chamadas["n"] += 1
        raise HTTPError("url", 404, "not found", None, None)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        resultado = github_version_checker.verificar_versao_github(
            "acme/repo", "docs/a.md", "hash-local", sleep=lambda _s: None,
        )

    assert resultado["status"] == "nao_encontrado"
    assert chamadas["n"] == 1


def test_verificar_versao_github_circuito_abre_apos_falhas_consecutivas():
    def fake_urlopen(req, timeout):
        raise URLError("github fora do ar")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        for _ in range(3):
            resultado = github_version_checker.verificar_versao_github(
                "acme/repo", "docs/a.md", "hash-local", sleep=lambda _s: None, max_retries=1,
            )
            assert resultado["status"] == "erro"

        resultado_circuito_aberto = github_version_checker.verificar_versao_github(
            "acme/repo", "docs/a.md", "hash-local", sleep=lambda _s: None,
        )

    assert resultado_circuito_aberto["status"] == "erro"
    assert "Circuito 'github_version_checker' aberto" in resultado_circuito_aberto["mensagem"]
