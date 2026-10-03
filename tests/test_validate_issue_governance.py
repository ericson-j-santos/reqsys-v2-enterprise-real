from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_issue_governance import (
    load_issue_author_type,
    load_issue_json,
    main,
    render_comment,
    validate_issue,
)


VALID_BODY = """### Descrição do problema
Falha reproduzível no fluxo X.

### Estado atual evidenciado
Run 123 falha com erro verificável.

### Estado esperado
Run deve concluir com sucesso.

### Causa raiz
Ainda desconhecida — investigação necessária.

### Critérios de aceite
- [ ] Teste reproduzível passa
- [ ] Evidência anexada

### Riscos
Nenhum identificado.

### Dependências
Nenhuma.

### Evidências
https://example.invalid/run/123

### PR(s) relacionadas
Nenhuma ainda.

### Responsável
@responsavel

### Prioridade
P1 - Alta / próximo incremento

### Declaração de rastreabilidade
- [x] Confirmei que o estado atual e as evidências acima não foram inventados e podem ser verificados.
"""


def test_issue_governada_valida() -> None:
    result = validate_issue(title="[ISSUE] Corrigir fluxo X", body=VALID_BODY, issue_number=10)

    assert result.valid is True
    assert result.issue_number == 10
    assert result.checked_fields == 13
    assert result.missing_fields == []
    assert result.invalid_fields == []


def test_titulo_apenas_com_prefixo_e_invalido() -> None:
    result = validate_issue(title="[ISSUE]   ", body=VALID_BODY)

    assert result.valid is False
    assert any(item.field == "Título" for item in result.invalid_fields)


def test_campo_ausente_e_detectado() -> None:
    body = VALID_BODY.replace("### Riscos\nNenhum identificado.\n\n", "")
    result = validate_issue(title="[ISSUE] Exemplo", body=body)

    assert result.valid is False
    assert "Riscos" in result.missing_fields


def test_comentario_html_nao_conta_como_conteudo() -> None:
    body = VALID_BODY.replace(
        "### Dependências\nNenhuma.",
        "### Dependências\n<!-- preencher depois -->",
    )
    result = validate_issue(title="[ISSUE] Exemplo", body=body)

    assert result.valid is False
    assert "Dependências" in result.missing_fields


@pytest.mark.parametrize("priority", ["P0", "P1", "P2", "P3"])
def test_prioridades_validas(priority: str) -> None:
    body = VALID_BODY.replace("P1 - Alta / próximo incremento", f"{priority} - prioridade")
    result = validate_issue(title="[ISSUE] Exemplo", body=body)

    assert result.valid is True


def test_prioridade_fora_do_contrato_e_invalida() -> None:
    body = VALID_BODY.replace("P1 - Alta / próximo incremento", "Urgente")
    result = validate_issue(title="[ISSUE] Exemplo", body=body)

    assert result.valid is False
    assert any(item.field == "Prioridade" for item in result.invalid_fields)


def test_declaracao_precisa_estar_marcada() -> None:
    body = VALID_BODY.replace("- [x] Confirmei", "- [ ] Confirmei")
    result = validate_issue(title="[ISSUE] Exemplo", body=body)

    assert result.valid is False
    assert any(item.field == "Declaração de rastreabilidade" for item in result.invalid_fields)


def test_carrega_payload_de_evento_github(tmp_path: Path) -> None:
    payload_path = tmp_path / "event.json"
    payload_path.write_text(
        json.dumps({"issue": {"number": 77, "title": "[ISSUE] Evento", "body": VALID_BODY}}),
        encoding="utf-8",
    )

    title, body, number = load_issue_json(payload_path)

    assert title == "[ISSUE] Evento"
    assert body == VALID_BODY
    assert number == 77


def test_comentario_invalido_e_acionavel() -> None:
    result = validate_issue(title="[ISSUE] Exemplo", body="")
    comment = render_comment(result)

    assert "<!-- reqsys-issue-governance-validator -->" in comment
    assert "correção necessária" in comment
    assert "Descrição do problema" in comment
    assert "não invente evidências" in comment


def test_comentario_valido_marca_conformidade() -> None:
    result = validate_issue(title="[ISSUE] Exemplo", body=VALID_BODY)
    comment = render_comment(result)

    assert "Governança da Issue — conforme" in comment
    assert "13/13 campos válidos" in comment


PANEL_BODY = """<!-- reqsys-operational-panel -->
## Progresso da certificação GitHub → Teams

**Estado atual:** `quality_blocked`
"""


def test_painel_operacional_de_bot_fica_fora_do_contrato() -> None:
    result = validate_issue(
        title="[STATUS][TEAMS] Progresso da certificação operacional",
        body=PANEL_BODY,
        issue_number=1358,
        author_type="Bot",
    )

    assert result.scope == "operational_panel"
    assert result.valid is True
    assert result.missing_fields == []
    assert result.checked_fields == 0


def test_marcador_de_painel_em_issue_humana_nao_dispensa_o_contrato() -> None:
    result = validate_issue(
        title="[ISSUE] Tentativa de escapar do contrato",
        body=PANEL_BODY,
        issue_number=1359,
        author_type="User",
    )

    assert result.scope == "governed_issue"
    assert result.valid is False
    assert "Descrição do problema" in result.missing_fields


def test_issue_de_bot_sem_marcador_permanece_sob_contrato() -> None:
    result = validate_issue(
        title="[ISSUE] Criada por automação",
        body="## Painel sem marcador\n",
        issue_number=1360,
        author_type="Bot",
    )

    assert result.scope == "governed_issue"
    assert result.valid is False


def test_issue_governada_conforme_mantem_escopo_padrao() -> None:
    result = validate_issue(title="[ISSUE] Corrigir fluxo X", body=VALID_BODY, author_type="User")

    assert result.scope == "governed_issue"
    assert result.valid is True


def test_comentario_de_painel_declara_fora_de_escopo() -> None:
    result = validate_issue(title="[STATUS] Painel", body=PANEL_BODY, author_type="Bot")
    comment = render_comment(result)

    assert "<!-- reqsys-issue-governance-validator -->" in comment
    assert "fora de escopo" in comment
    assert "Nenhuma ação humana é necessária" in comment


def test_author_type_do_payload_e_utilizado(tmp_path: Path) -> None:
    payload_path = tmp_path / "event.json"
    payload_path.write_text(
        json.dumps(
            {
                "issue": {
                    "number": 1358,
                    "title": "[STATUS][TEAMS] Painel",
                    "body": PANEL_BODY,
                    "user": {"type": "Bot"},
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_issue_author_type(payload_path) == "Bot"


def test_cli_retorna_zero_para_painel_operacional(tmp_path: Path) -> None:
    issue_path = tmp_path / "issue.json"
    issue_path.write_text(
        json.dumps({"number": 1358, "title": "[STATUS] Painel", "body": PANEL_BODY, "author_type": "Bot"}),
        encoding="utf-8",
    )
    comment_path = tmp_path / "comment.md"

    exit_code = main(["--issue-json", str(issue_path), "--comment-output", str(comment_path)])

    assert exit_code == 0
    assert "fora de escopo" in comment_path.read_text(encoding="utf-8")
