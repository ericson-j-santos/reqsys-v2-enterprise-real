from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "route_issue_by_label.py"
SPEC = importlib.util.spec_from_file_location("gitlab_issue_router", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_resolver_dominio_encontra_label_conhecida() -> None:
    dominio = MODULE.resolver_dominio(["bug", "ia:runtime", "prioridade:alta"])
    assert dominio is not None
    assert dominio["dominio"] == "runtime"
    assert dominio["prefixo"] == "runtime"


def test_resolver_dominio_sem_label_retorna_none() -> None:
    assert MODULE.resolver_dominio(["bug", "prioridade:alta"]) is None


def test_slugify_normaliza_titulo() -> None:
    assert MODULE.slugify("Corrigir Bug Crítico #42!!") == "corrigir-bug-cr-tico-42"


def test_slugify_titulo_vazio_usa_fallback() -> None:
    assert MODULE.slugify("   ") == "sem-titulo"


def test_nome_branch_usa_prefixo_iid_e_slug() -> None:
    assert MODULE.nome_branch("runtime", 123, "Corrigir timeout") == "runtime/issue-123-corrigir-timeout"


def test_decidir_acao_ja_roteada_ignora() -> None:
    acao = MODULE.decidir_acao(ja_roteada=True, tem_dominio=True, branch_ja_existe=False)
    assert acao == "ignorado_ja_roteado"


def test_decidir_acao_sem_dominio_ignora() -> None:
    acao = MODULE.decidir_acao(ja_roteada=False, tem_dominio=False, branch_ja_existe=False)
    assert acao == "ignorado_sem_dominio"


def test_decidir_acao_branch_existente_vincula() -> None:
    acao = MODULE.decidir_acao(ja_roteada=False, tem_dominio=True, branch_ja_existe=True)
    assert acao == "vincular_branch_existente"


def test_decidir_acao_cria_branch_quando_novo() -> None:
    acao = MODULE.decidir_acao(ja_roteada=False, tem_dominio=True, branch_ja_existe=False)
    assert acao == "criar_branch"


class ClientFake:
    def __init__(self, branch_existe: bool = False) -> None:
        self.chamadas: list[tuple[str, str, dict | None]] = []
        self._branch_existe = branch_existe

    def request(self, method, path, payload=None, allow_status=None):
        self.chamadas.append((method, path, payload))
        if method == "GET" and "/repository/branches/" in path:
            return (200 if self._branch_existe else 404), {}
        return 200, {}

    def project_path(self, suffix: str = "") -> str:
        return f"projects/1{suffix}"


def _config(dry_run: bool) -> "MODULE.Config":
    return MODULE.Config(
        api_url="https://gitlab.example.com/api/v4",
        project_id="1",
        token="fake-token",
        default_branch="main",
        timeout_seconds=20,
        dry_run=dry_run,
    )


def test_rotear_issue_dry_run_nao_chama_api_de_escrita() -> None:
    client = ClientFake()
    issue = {"iid": 42, "title": "Timeout no runtime", "labels": ["ia:runtime"]}

    resultado = MODULE.rotear_issue(client, _config(dry_run=True), issue)

    assert resultado["acao"] == "criar_branch"
    assert resultado["branch"] == "runtime/issue-42-timeout-no-runtime"
    assert client.chamadas == []


def test_rotear_issue_ja_roteada_nao_faz_nada() -> None:
    client = ClientFake()
    issue = {"iid": 7, "title": "Doc antiga", "labels": ["ia:docs", "ia:roteado"]}

    resultado = MODULE.rotear_issue(client, _config(dry_run=True), issue)

    assert resultado == {"issue_iid": 7, "acao": "ignorado_ja_roteado"}
    assert client.chamadas == []


def test_rotear_issue_sem_label_de_dominio_ignora() -> None:
    client = ClientFake()
    issue = {"iid": 8, "title": "Duvida geral", "labels": ["bug"]}

    resultado = MODULE.rotear_issue(client, _config(dry_run=True), issue)

    assert resultado == {"issue_iid": 8, "acao": "ignorado_sem_dominio"}


def test_rotear_issue_apply_cria_branch_labela_e_comenta() -> None:
    client = ClientFake(branch_existe=False)
    issue = {"iid": 42, "title": "Timeout no runtime", "labels": ["ia:runtime"]}

    resultado = MODULE.rotear_issue(client, _config(dry_run=False), issue)

    assert resultado["acao"] == "criar_branch"
    metodos = [chamada[0] for chamada in client.chamadas]
    assert metodos == ["GET", "POST", "PUT", "POST"]
    assert client.chamadas[1][1] == "projects/1/repository/branches"
    assert client.chamadas[1][2] == {"branch": "runtime/issue-42-timeout-no-runtime", "ref": "main"}
    assert client.chamadas[2][2] == {"add_labels": "ia:roteado"}


def test_rotear_issue_apply_com_branch_existente_apenas_vincula() -> None:
    client = ClientFake(branch_existe=True)
    issue = {"iid": 9, "title": "Ja tem branch", "labels": ["ia:observability"]}

    resultado = MODULE.rotear_issue(client, _config(dry_run=False), issue)

    assert resultado["acao"] == "vincular_branch_existente"
    assert client.chamadas == [("GET", "projects/1/repository/branches/observability%2Fissue-9-ja-tem-branch", None)]


def test_listar_issues_roteaveis_filtra_por_label_conhecida() -> None:
    class ClientListagem:
        def project_path(self, suffix: str = "") -> str:
            return f"projects/1{suffix}"

        def request(self, method, path, payload=None, allow_status=None):
            return 200, [
                {"iid": 1, "title": "A", "labels": ["ia:runtime"]},
                {"iid": 2, "title": "B", "labels": ["bug"]},
                {"iid": 3, "title": "C", "labels": ["ia:docs", "ia:roteado"]},
            ]

    issues = MODULE.listar_issues_roteaveis(ClientListagem())

    assert {issue["iid"] for issue in issues} == {1, 3}


def test_build_report_conta_issues_avaliadas() -> None:
    resultados = [
        {"issue_iid": 1, "acao": "criar_branch", "dominio": "runtime", "branch": "runtime/issue-1-a"},
        {"issue_iid": 2, "acao": "ignorado_sem_dominio"},
    ]

    report = MODULE.build_report(_config(dry_run=True), resultados)

    assert report["issues_avaliadas"] == 2
    assert report["dry_run"] is True
