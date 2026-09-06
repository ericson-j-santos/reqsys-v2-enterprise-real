from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_issue_governance import load_issue_json, render_comment, validate_issue


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
