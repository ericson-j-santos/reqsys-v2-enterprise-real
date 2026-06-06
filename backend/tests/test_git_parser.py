import pytest
from app.services.git_parser import (
    extrair_codigos_requisito,
    processar_mr_gitlab,
    processar_pr_github,
    processar_push_github,
    processar_push_gitlab,
)


# ── extrair_codigos_requisito ──────────────────────────────────────────────

def test_extrai_codigo_simples():
    assert extrair_codigos_requisito("fix: corrige bug REQ-123456789") == ["REQ-123456789"]


def test_extrai_multiplos_codigos():
    result = extrair_codigos_requisito("REQ-123456789 e REQ-987654321 implementados")
    assert set(result) == {"REQ-123456789", "REQ-987654321"}


def test_sem_codigo_retorna_lista_vazia():
    assert extrair_codigos_requisito("fix: corrige typo no README") == []


def test_case_insensitive_normaliza_para_maiusculo():
    result = extrair_codigos_requisito("implementa req-123456789")
    assert "REQ-123456789" in result


def test_deduplica_codigo_repetido():
    result = extrair_codigos_requisito("REQ-123456789 REQ-123456789")
    assert result.count("REQ-123456789") == 1


def test_codigo_muito_curto_ignorado():
    # REQ-12345 tem 5 dígitos — menos que o mínimo de 6
    assert extrair_codigos_requisito("REQ-12345 é inválido") == []


def test_texto_vazio():
    assert extrair_codigos_requisito("") == []
    assert extrair_codigos_requisito(None) == []  # type: ignore[arg-type]


# ── processar_push_github ──────────────────────────────────────────────────

_PUSH_PAYLOAD = {
    "ref": "refs/heads/develop",
    "repository": {"full_name": "owner/repo"},
    "commits": [
        {
            "id": "abc123def456abc123def456abc123def456abc1",
            "message": "feat: implementa autenticação REQ-123456789\n\nDetalhes da implementação.",
            "author": {"username": "dev1", "name": "Dev Um"},
            "url": "https://github.com/owner/repo/commit/abc123",
        }
    ],
}


def test_push_github_extrai_vínculo():
    result = processar_push_github(_PUSH_PAYLOAD)
    assert len(result) == 1
    v = result[0]
    assert v["requisito_codigo"] == "REQ-123456789"
    assert v["tipo"] == "commit"
    assert v["provedor"] == "github"
    assert v["repo"] == "owner/repo"
    assert v["referencia"] == "abc123def456abc123def456abc123def456abc1"
    assert v["autor"] == "dev1"
    assert v["ambiente"] == "dev"


def test_push_github_sem_req_retorna_vazio():
    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "owner/repo"},
        "commits": [{"id": "abc", "message": "fix typo", "author": {}, "url": None}],
    }
    assert processar_push_github(payload) == []


def test_push_github_branch_main_ambiente_prod():
    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "owner/repo"},
        "commits": [
            {
                "id": "a" * 40,
                "message": "chore: merge REQ-111111111",
                "author": {"username": "ci"},
                "url": None,
            }
        ],
    }
    result = processar_push_github(payload)
    assert result[0]["ambiente"] == "prod"


def test_push_github_branch_desconhecida_ambiente_none():
    payload = {
        "ref": "refs/heads/feature/REQ-123-auth",
        "repository": {"full_name": "owner/repo"},
        "commits": [
            {
                "id": "a" * 40,
                "message": "feat: REQ-123456789",
                "author": {"username": "dev1"},
                "url": None,
            }
        ],
    }
    result = processar_push_github(payload)
    assert result[0]["ambiente"] is None


# ── processar_pr_github ────────────────────────────────────────────────────

def test_pr_github_merged_atualiza_flag():
    payload = {
        "action": "closed",
        "pull_request": {
            "number": 42,
            "title": "Implementa REQ-123456789",
            "body": "Closes REQ-123456789 — testes passando.",
            "html_url": "https://github.com/owner/repo/pull/42",
            "user": {"login": "dev1"},
            "head": {"ref": "feature/auth"},
            "merged": True,
        },
        "repository": {"full_name": "owner/repo"},
    }
    result = processar_pr_github(payload)
    assert len(result) == 1
    assert result[0]["tipo"] == "pr"
    assert result[0]["pr_merged"] is True
    assert result[0]["referencia"] == "42"


def test_pr_github_nao_merged():
    payload = {
        "action": "closed",
        "pull_request": {
            "number": 5,
            "title": "WIP REQ-123456789",
            "body": "",
            "html_url": "https://github.com/owner/repo/pull/5",
            "user": {"login": "dev1"},
            "head": {"ref": "wip"},
            "merged": False,
        },
        "repository": {"full_name": "owner/repo"},
    }
    result = processar_pr_github(payload)
    assert result[0]["pr_merged"] is False


def test_pr_github_sem_req_retorna_vazio():
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 1, "title": "Fix readme", "body": "",
            "html_url": "", "user": {"login": "x"}, "head": {"ref": "fix/readme"}, "merged": False,
        },
        "repository": {"full_name": "owner/repo"},
    }
    assert processar_pr_github(payload) == []


# ── processar_push_gitlab ──────────────────────────────────────────────────

def test_push_gitlab_extrai_vínculo():
    payload = {
        "ref": "refs/heads/staging",
        "project": {"path_with_namespace": "grupo/projeto"},
        "commits": [
            {
                "id": "b" * 40,
                "message": "fix: corrige validação REQ-987654321",
                "author": {"name": "Dev Dois"},
                "url": "https://gitlab.com/grupo/projeto/-/commit/bbb",
            }
        ],
    }
    result = processar_push_gitlab(payload)
    assert len(result) == 1
    assert result[0]["provedor"] == "gitlab"
    assert result[0]["ambiente"] == "staging"
    assert result[0]["requisito_codigo"] == "REQ-987654321"


# ── processar_mr_gitlab ────────────────────────────────────────────────────

def test_mr_gitlab_merged():
    payload = {
        "user": {"username": "devgitlab"},
        "project": {"path_with_namespace": "grupo/projeto"},
        "object_attributes": {
            "iid": 7,
            "title": "Implementa fluxo REQ-111111111",
            "description": "Resolve REQ-111111111 conforme especificação.",
            "url": "https://gitlab.com/grupo/projeto/-/merge_requests/7",
            "source_branch": "develop",
            "state": "merged",
        },
    }
    result = processar_mr_gitlab(payload)
    assert len(result) == 1
    assert result[0]["tipo"] == "merge_request"
    assert result[0]["mr_merged"] is True
    assert result[0]["ambiente"] == "dev"
