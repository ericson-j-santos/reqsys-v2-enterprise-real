def _criar_sprint(client):
    response = client.post('/v1/agile-runtime/sprints', json={
        'nome': 'Sprint Scrum operacional',
        'objetivo': 'Validar as cerimônias e ações de melhoria',
        'data_inicio': '2026-09-07',
        'data_fim': '2026-09-18',
        'capacidade_pontos': 21,
        'pontos_comprometidos': 13,
    })
    assert response.status_code == 200
    return response.json()['data']['id']


def test_ciclo_de_cerimonia_com_impedimento_e_acao(client):
    sprint_id = _criar_sprint(client)
    created = client.post('/v1/agile-runtime/cerimonias', headers={'X-Correlation-Id': 'scrum-001'}, json={
        'sprint_id': sprint_id,
        'tipo': 'retrospectiva',
        'titulo': 'Retrospectiva da sprint',
        'inicio_em': '2026-09-18T15:00:00Z',
        'duracao_minutos': 60,
        'facilitador': 'Scrum Master',
        'participantes': ['Product Owner', 'Time de desenvolvimento'],
        'pauta': 'Inspecionar resultados e definir melhorias.',
    })
    assert created.status_code == 200
    ceremony = created.json()['data']
    assert ceremony['participantes'] == ['Product Owner', 'Time de desenvolvimento']

    action = client.post(f"/v1/agile-runtime/cerimonias/{ceremony['id']}/acoes", json={
        'tipo': 'impedimento',
        'descricao': 'Ambiente de homologação indisponível',
        'responsavel': 'Plataforma',
        'prazo': '2026-09-21',
        'bloqueante': True,
    })
    assert action.status_code == 200
    action_id = action.json()['data']['id']
    updated = client.patch(f"/v1/agile-runtime/cerimonias/{ceremony['id']}/acoes/{action_id}", json={'status': 'resolvida'})
    assert updated.status_code == 200
    assert updated.json()['data']['status'] == 'resolvida'

    finished = client.post(f"/v1/agile-runtime/cerimonias/{ceremony['id']}/concluir", json={
        'resumo': 'A sprint foi inspecionada pelo time.',
        'decisoes': 'Automatizar a verificação do ambiente.',
    })
    assert finished.status_code == 200
    assert finished.json()['data']['status'] == 'concluida'


def test_gate_dor_informa_campos_faltantes(client):
    item = client.post('/v1/agile-runtime/work-items', json={
        'tipo': 'story',
        'titulo': 'Story ainda não refinada',
        'descricao': 'Item criado para validar o gate de prontidão.',
    }).json()['data']
    assert client.patch(f"/v1/agile-runtime/work-items/{item['id']}/workflow", json={'status': 'refinando'}).status_code == 200
    response = client.patch(f"/v1/agile-runtime/work-items/{item['id']}/workflow", json={'status': 'pronto_para_sprint'})
    assert response.status_code == 422
    assert set(response.json()['detail']['campos_faltantes']) == {'criterios_aceite', 'sprint_id', 'owner', 'pontos'}


def test_ciclo_de_vida_da_sprint(client):
    sprint_id = _criar_sprint(client)
    active = client.patch(f'/v1/agile-runtime/sprints/{sprint_id}/status', json={'status': 'ativa'})
    assert active.status_code == 200
    assert active.json()['data']['status'] == 'ativa'
    finished = client.patch(f'/v1/agile-runtime/sprints/{sprint_id}/status', json={'status': 'concluida'})
    assert finished.status_code == 200
    assert finished.json()['data']['status'] == 'concluida'
