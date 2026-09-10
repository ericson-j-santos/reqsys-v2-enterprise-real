"""Contrato do filtro que evita notificacoes Teams para tarefas E2E.

A avaliacao real da expressao pertence ao runtime do Logic Apps/Power Automate.
Esta suite fixa a expressao gerada e a tabela de decisao esperada sem simular
uma implantacao DEV como evidência operacional.
"""

import pytest

from app.services.planner_teams_notify_provisioning import (
    FILTRO_TAREFA_TESTE_ID,
    PREFIXO_TAREFA_TESTE_IGNORADA,
    gerar_definicao,
    validar_definicao,
)


def _payload() -> dict:
    return {
        'environment_id': 'env-dev-001',
        'environment_url': 'https://org-dev.crm2.dynamics.com',
        'group_id': 'group-dev-001',
        'plan_id': 'plan-dev-001',
        'planner_connection_id': 'planner-connection-dev',
        'teams_team_id': 'team-dev-001',
        'teams_channel_id': '19:channel-dev-001@thread.tacv2',
        'teams_connection_id': 'teams-connection-dev',
        'target_environment': 'dev',
        'confirmar': False,
        'correlation_id': 'corr-planner-teams-filter-contract',
    }


def test_expressao_do_filtro_permanece_restrita_ao_prefixo_e2e():
    definicao = gerar_definicao(_payload(), 'criada')
    filtro = definicao['actions'][FILTRO_TAREFA_TESTE_ID]

    assert filtro['type'] == 'If'
    assert filtro['expression'] == (
        "@not(startsWith(triggerBody()?['title'], "
        f"'{PREFIXO_TAREFA_TESTE_IGNORADA}'))"
    )
    assert set(filtro['actions']) == {'Notificar_Teams'}
    assert 'else' in filtro
    assert filtro['else'] == {'actions': {}}
    assert validar_definicao(definicao) == []


def test_validador_rejeita_if_sem_else_explicito():
    definicao = gerar_definicao(_payload(), 'criada')
    filtro = definicao['actions'][FILTRO_TAREFA_TESTE_ID]
    filtro.pop('else')

    assert 'filtro_tarefa_teste_else_explicito_ausente' in validar_definicao(definicao)


@pytest.mark.parametrize(
    ('titulo', 'deve_notificar'),
    [
        ('REQSYS-E2E-001', False),
        ('REQSYS-E2E-PLANNER', False),
        ('reqsys-e2e-001', False),
        ('REQSYS-1234', True),
        ('Corrigir integracao Teams', True),
        ('E2E-REQSYS-001', True),
    ],
)
def test_tabela_decisao_do_filtro_e2e(titulo: str, deve_notificar: bool):
    # startsWith() da linguagem de expressoes do Logic Apps nao diferencia
    # maiusculas de minusculas. O casefold abaixo representa apenas o contrato
    # esperado; a prova do runtime real continua sendo o aceite em DEV.
    prefixo_encontrado = titulo.casefold().startswith(PREFIXO_TAREFA_TESTE_IGNORADA.casefold())

    assert (not prefixo_encontrado) is deve_notificar
