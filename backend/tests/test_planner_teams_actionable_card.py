import json

from app.services.planner_teams_notify_provisioning import (
    FILTRO_TAREFA_TESTE_ID,
    PLANNER_TASK_URL,
    gerar_definicao,
    validar_definicao,
)


def _payload():
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
    }


def _card(evento='criada'):
    definition = gerar_definicao(_payload(), evento)
    notify = definition['actions'][FILTRO_TAREFA_TESTE_ID]['actions']['Notificar_Teams']
    return definition, json.loads(notify['inputs']['parameters']['body/messageBody'])


def test_card_prioriza_dados_operacionais_e_link_da_tarefa():
    definition, card = _card()

    assert validar_definicao(definition) == []
    assert card['version'] == '1.2'
    assert card['body'][0]['text'] == 'Nova tarefa no Planner'
    assert card['body'][1]['weight'] == 'Bolder'

    facts = {fact['title']: fact['value'] for fact in card['body'][2]['facts']}
    assert set(facts) == {'Progresso', 'Vencimento'}
    assert "percentComplete" in facts['Progresso']
    assert 'Sem prazo' in facts['Vencimento']
    assert 'Plano' not in facts

    assert card['actions'] == [
        {
            'type': 'Action.OpenUrl',
            'title': 'Abrir no Planner',
            'url': PLANNER_TASK_URL,
        }
    ]
    assert "triggerBody()?['id']" in PLANNER_TASK_URL
    assert "parameters('PLANNER_PLAN_ID')" in PLANNER_TASK_URL


def test_card_mantem_id_tecnico_como_metadado_secundario():
    _, card = _card()

    technical = card['body'][3]
    assert technical['isSubtle'] is True
    assert technical['size'] == 'Small'
    assert technical['text'] == "ID da tarefa: @{triggerBody()?['id']}"


def test_validador_falha_fechado_sem_acao_abrir_planner():
    definition, card = _card()
    card['actions'] = []
    notify = definition['actions'][FILTRO_TAREFA_TESTE_ID]['actions']['Notificar_Teams']
    notify['inputs']['parameters']['body/messageBody'] = json.dumps(card, ensure_ascii=False)

    assert 'acao_abrir_planner_ausente' in validar_definicao(definition)
