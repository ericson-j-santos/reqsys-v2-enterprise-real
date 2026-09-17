"""Regressão do corpo do painel persistente de certificação Teams.

O corpo é montado por Python embutido no workflow. Uma interpolação multilinha
dentro do literal anula o prefixo comum e faz ``textwrap.dedent`` devolver o
texto indentado, que o GitHub publica como bloco de código. Estes testes leem o
workflow real para impedir a reintrodução do defeito.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/teams-certification-progress-status.yml"
ALIGN_BLOCK_RE = re.compile(
    r"\n( +)def align_block\(text: str, spaces: int = 4\) -> str:\n"
    r".*?\n\1    return textwrap\.indent\(text, \" \" \* spaces\)\.strip\(\)\n",
    re.DOTALL,
)


@pytest.fixture(scope="module")
def workflow_source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def align_block(workflow_source: str):
    match = ALIGN_BLOCK_RE.search(workflow_source)
    assert match, "helper align_block ausente no workflow do painel"
    namespace: dict[str, object] = {"textwrap": textwrap}
    exec(textwrap.dedent(match.group(0)), namespace)  # noqa: S102 - fonte versionada no próprio repo
    return namespace["align_block"]


def test_bloqueios_sao_alinhados_antes_da_interpolacao(workflow_source: str) -> None:
    assert "blockers_text = align_block(" in workflow_source


def test_corpo_declara_marcador_de_painel_operacional(workflow_source: str) -> None:
    assert "<!-- reqsys-operational-panel -->" in workflow_source


def test_indentacao_do_template_casa_com_o_alinhamento_padrao(workflow_source: str) -> None:
    """O alinhamento só funciona se casar com a indentação do literal do corpo."""
    match = re.search(
        r"\n( +)body = textwrap\.dedent\(f\"\"\"\\\n( +)<!-- reqsys-operational-panel -->",
        workflow_source,
    )
    assert match, "literal do corpo do painel não encontrado"
    assert len(match.group(2)) - len(match.group(1)) == 4


def test_dedent_preserva_markdown_com_bloco_multilinha(align_block) -> None:
    # O literal deste teste está indentado em 8 colunas; o alinhamento acompanha.
    blockers = align_block("- SLO de entrega: 98.53%\n- SLO do monitor: 41.38%", 8)

    body = textwrap.dedent(
        f"""\
        <!-- reqsys-operational-panel -->
        ## Progresso

        ### Bloqueios atuais

        {blockers}
        """
    )

    assert body.startswith("<!-- reqsys-operational-panel -->")
    assert not any(line.startswith(" ") for line in body.splitlines())
    assert "- SLO do monitor: 41.38%" in body


def test_bloco_multilinha_sem_alinhamento_quebraria_o_dedent() -> None:
    blockers = "- SLO de entrega: 98.53%\n- SLO do monitor: 41.38%"

    body = textwrap.dedent(
        f"""\
        ## Progresso

        {blockers}
        """
    )

    # Controle negativo: comprova que o defeito original é reproduzível.
    assert body.startswith("        ## Progresso")


def test_bloco_de_linha_unica_tambem_e_preservado(align_block) -> None:
    assert align_block("- nenhum bloqueio atual") == "- nenhum bloqueio atual"
