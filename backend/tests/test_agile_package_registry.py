def _payload() -> dict:
    return {
        'titulo': 'Planejar sprint Scrum para aprovação de requisitos',
        'descricao': (
            'O analista precisa reduzir o prazo de aprovação. '
            'A API deve persistir o histórico no SQL e registrar logs com correlation_id.'
        ),
        'origem': 'pytest-agile-registry',
        'prioridade_informada': 'alta',
        'objetivo': 'Reduzir o lead time e o retrabalho da aprovação.',
        'publico_alvo': 'analista de requisitos',
        'owner': 'Product Owner',
    }


def test_orchestrator_persiste_pacote_agile_idempotente(client):
    headers = {'X-Correlation-ID': 'corr-agile-registry-001'}

    first = client.post('/v1/agents/orchestrator/route', json=_payload(), headers=headers)
    second = client.post('/v1/agents/orchestrator/route', json=_payload(), headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    first_data = first.json()['data']
    second_data = second.json()['data']
    package_id = first_data['agile_project_package']['package_id']

    assert first_data['agile_package_registry']['created'] is True
    assert second_data['agile_package_registry']['created'] is False
    assert second_data['agile_project_package']['package_id'] == package_id

    fetched = client.get(f'/v1/agents/orchestrator/agile/packages/{package_id}')
    assert fetched.status_code == 200
    registry = fetched.json()['data']
    assert registry['package_id'] == package_id
    assert registry['status'] == 'generated'
    assert registry['correlation_id'] == 'corr-agile-registry-001'
    assert registry['integration_targets'] == [
        'jira',
        'azure_devops',
        'github_projects',
        'gitlab',
    ]


def test_lista_pacotes_agile_por_correlation_id(client):
    headers = {'X-Correlation-ID': 'corr-agile-registry-list'}
    response = client.post('/v1/agents/orchestrator/route', json=_payload(), headers=headers)
    assert response.status_code == 200

    listed = client.get(
        '/v1/agents/orchestrator/agile/packages',
        params={'correlation_id': 'corr-agile-registry-list'},
    )
    assert listed.status_code == 200
    data = listed.json()['data']
    assert data['total'] >= 1
    assert all(item['correlation_id'] == 'corr-agile-registry-list' for item in data['packages'])


def test_consulta_pacote_agile_inexistente_retorna_404(client):
    response = client.get('/v1/agents/orchestrator/agile/packages/agile-inexistente')
    assert response.status_code == 404
    assert response.json()['detail'] == 'agile_package_not_found'
