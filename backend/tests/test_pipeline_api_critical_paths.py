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
