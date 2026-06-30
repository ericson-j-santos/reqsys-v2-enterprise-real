"""Testes de caminhos críticos — API Pipeline."""

from unittest.mock import patch

from app.api import pipeline as pipeline_api


def test_inferir_rfs_detecta_termos_de_cadastro():
    rfs = pipeline_api.inferir_rfs('Permitir cadastro por CPF e consulta de registros.')

    assert any('CPF' in item for item in rfs)
    assert any('Consultar' in item for item in rfs)


def test_criar_solicitacao_persiste_requisito(client):
    response = client.post(
        '/v1/solicitacoes',
        headers={'X-Correlation-Id': 'corr-pipeline-sol'},
        json={
            'origem': 'portal',
            'titulo': 'Solicitacao pipeline teste',
            'descricao': 'Descricao com mais de vinte caracteres para validacao.',
            'solicitante': 'qa@reqsys.local',
            'area': 'Operacoes',
            'sistema': 'Pipeline',
            'urgencia': 'alta',
        },
    )

    assert response.status_code == 201
    data = response.json()['data']
    assert data['codigo'].startswith('SOL-')
    assert data['status'] == 'recebido'


def test_validar_requisito_com_alertas(client):
    response = client.post(
        '/v1/requisitos/validar',
        json={
            'titulo': 'Titulo rapido e simples',
            'descricao': 'Descricao sem criterios formais.',
            'requisitos_funcionais': [],
            'criterios_aceite': [],
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['aprovado_para_triagem'] is False
    assert len(data['alertas']) >= 2


def test_estruturar_requisito_inexistente_gera_codigo(client):
    response = client.post(
        '/v1/requisitos/estruturar/999999',
        json={
            'origem': 'api',
            'titulo': 'Estruturar inexistente',
            'descricao': 'Fluxo quando requisito nao existe no banco local.',
            'solicitante': 'qa@reqsys.local',
            'area': 'QA',
            'sistema': 'Pipeline',
            'urgencia': 'media',
        },
    )

    assert response.status_code == 200
    assert response.json()['data']['codigo_requisito'].startswith('REQ-')


def test_listar_issues_github_integracao_desabilitada(client, monkeypatch):
    monkeypatch.setattr(pipeline_api, 'github_redmine_import_enabled', lambda: False)

    response = client.post(
        '/v1/integracoes/github/issues',
        json={'repo': 'owner/repo', 'state': 'open', 'limit': 5},
    )

    assert response.status_code == 409


def test_publicar_redmine_requisito_inexistente(client):
    response = client.post('/v1/backlog/publicar-redmine/999999', json={})

    assert response.status_code == 404


def test_listar_issues_github_com_integracao_habilitada(client, monkeypatch):
    monkeypatch.setattr(pipeline_api, 'github_redmine_import_enabled', lambda: True)

    with patch('app.api.pipeline.fetch_github_issues', return_value=[]):
        response = client.post(
            '/v1/integracoes/github/issues',
            json={'repo': 'owner/repo', 'state': 'open', 'limit': 5},
        )

    assert response.status_code == 200
    assert response.json()['data']['total'] == 0


def test_inferir_rfs_retorna_lista_vazia_sem_termos():
    assert pipeline_api.inferir_rfs('texto neutro sem palavras chave') == []


def test_publicar_redmine_com_github_import_sem_repo(client, monkeypatch):
    monkeypatch.setattr(pipeline_api, 'github_redmine_import_enabled', lambda: True)
    criado = client.post(
        '/v1/solicitacoes',
        json={
            'origem': 'portal',
            'titulo': 'Publicar redmine github',
            'descricao': 'Descricao longa para publicacao com import github.',
            'solicitante': 'qa@reqsys.local',
            'area': 'Integracoes',
            'sistema': 'Redmine',
            'urgencia': 'media',
        },
    )
    requisito_id = criado.json()['data']['id']

    response = client.post(
        f'/v1/backlog/publicar-redmine/{requisito_id}',
        json={'use_github_import': True},
    )

    assert response.status_code == 422


@patch('app.api.pipeline.publish_issues_to_redmine')
@patch('app.api.pipeline.publish_requisito_to_redmine')
@patch('app.api.pipeline.fetch_github_issues')
def test_publicar_redmine_com_github_import_filtra_issues(
    mock_fetch,
    mock_publish_req,
    mock_publish_issues,
    client,
    monkeypatch,
):
    monkeypatch.setattr(pipeline_api, 'github_redmine_import_enabled', lambda: True)
    mock_fetch.return_value = [
        {'number': 1, 'title': 'Issue 1'},
        {'number': 2, 'title': 'Issue 2'},
    ]
    mock_publish_req.return_value = {'issue_principal_id': 10, 'subtarefas': [], 'warnings': []}
    mock_publish_issues.return_value = {'published_count': 1, 'published_issues': [{'number': 1}], 'warnings': []}

    criado = client.post(
        '/v1/solicitacoes',
        json={
            'origem': 'portal',
            'titulo': 'Publicar redmine com filtro',
            'descricao': 'Descricao longa para publicacao redmine com import github.',
            'solicitante': 'qa@reqsys.local',
            'area': 'Integracoes',
            'sistema': 'Redmine',
            'urgencia': 'media',
        },
    )
    requisito_id = criado.json()['data']['id']

    response = client.post(
        f'/v1/backlog/publicar-redmine/{requisito_id}',
        json={
            'use_github_import': True,
            'github_repo': 'owner/repo',
            'issue_numbers': [1],
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['github_imported_count'] == 1
    assert data['redmine_published_count'] == 1


@patch('app.api.pipeline.fetch_github_issues', side_effect=pipeline_api.IntegracaoError('repo invalido'))
def test_publicar_redmine_github_import_integracao_error(mock_fetch, client, monkeypatch):
    monkeypatch.setattr(pipeline_api, 'github_redmine_import_enabled', lambda: True)
    criado = client.post(
        '/v1/solicitacoes',
        json={
            'origem': 'portal',
            'titulo': 'Publicar redmine erro github',
            'descricao': 'Descricao longa para validar erro de integracao github.',
            'solicitante': 'qa@reqsys.local',
            'area': 'Integracoes',
            'sistema': 'Redmine',
            'urgencia': 'media',
        },
    )
    requisito_id = criado.json()['data']['id']

    response = client.post(
        f'/v1/backlog/publicar-redmine/{requisito_id}',
        json={'use_github_import': True, 'github_repo': 'owner/repo'},
    )

    assert response.status_code == 400


def test_validar_requisito_atualiza_status_quando_requisito_id_informado(client):
    criado = client.post(
        '/v1/solicitacoes',
        json={
            'origem': 'portal',
            'titulo': 'Validar com requisito id',
            'descricao': 'Descricao longa para validar requisito existente no banco.',
            'solicitante': 'qa@reqsys.local',
            'area': 'QA',
            'sistema': 'Pipeline',
            'urgencia': 'media',
        },
    )
    requisito_id = criado.json()['data']['id']

    response = client.post(
        f'/v1/requisitos/validar?requisito_id={requisito_id}',
        json={
            'titulo': 'Titulo valido',
            'descricao': 'Descricao valida sem termos ambiguos.',
            'requisitos_funcionais': ['RF-001'],
            'criterios_aceite': [{'ordem': 1, 'descricao': 'Criterio atendido.'}],
        },
    )

    assert response.status_code == 200
    assert response.json()['data']['aprovado_para_triagem'] is True

    detalhe = client.get(f'/v1/requisitos/{requisito_id}')
    if detalhe.status_code == 200:
        assert detalhe.json()['data']['status'] == 'validado'


def test_estruturar_requisito_existente_atualiza_status(client):
    criado = client.post(
        '/v1/solicitacoes',
        json={
            'origem': 'portal',
            'titulo': 'Estruturar requisito existente',
            'descricao': 'Descricao longa para estruturar requisito recebido no banco.',
            'solicitante': 'qa@reqsys.local',
            'area': 'QA',
            'sistema': 'Pipeline',
            'urgencia': 'alta',
        },
    )
    requisito_id = criado.json()['data']['id']

    response = client.post(
        f'/v1/requisitos/estruturar/{requisito_id}',
        json={
            'origem': 'portal',
            'titulo': 'Estruturar requisito existente',
            'descricao': 'Buscar cadastro por CPF antes de criar novo registro.',
            'solicitante': 'qa@reqsys.local',
            'area': 'QA',
            'sistema': 'Pipeline',
            'urgencia': 'alta',
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['status'] == 'estruturado'
    assert data['codigo_requisito'].startswith('REQ-')


def test_listar_issues_github_propaga_integracao_error(client, monkeypatch):
    monkeypatch.setattr(pipeline_api, 'github_redmine_import_enabled', lambda: True)

    def _raise(*_args, **_kwargs):
        raise pipeline_api.IntegracaoError('falha simulada na API GitHub')

    monkeypatch.setattr(pipeline_api, 'fetch_github_issues', _raise)

    response = client.post(
        '/v1/integracoes/github/issues',
        json={'repo': 'owner/repo', 'state': 'open', 'limit': 5},
    )

    assert response.status_code == 400
    assert 'falha simulada' in response.json()['detail']
