from app.services.planner_teams_notify_provisioning import gerar_definicao


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


def test_trigger_planner_persiste_group_e_plan_com_ids_literais():
    payload = _payload()

    for evento in ('criada', 'concluida'):
        definicao = gerar_definicao(payload, evento)
        trigger = next(iter(definicao['triggers'].values()))
        parametros = trigger['inputs']['parameters']

        assert parametros['groupId'] == payload['group_id']
        assert parametros['id'] == payload['plan_id']
        assert not parametros['groupId'].startswith('@parameters(')
        assert not parametros['id'].startswith('@parameters(')
