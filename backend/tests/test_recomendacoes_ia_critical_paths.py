"""Testes de caminhos críticos — recomendações IA (paridade frontend/backend)."""

import os

import pytest

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_recomendacoes_ia.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.models.requisito import Requisito
from app.services import recomendacoes_ia as svc


def test_serializar_incidente_mapeia_campos_do_requisito(db_session):
    requisito = Requisito(
        codigo='REQ-IA-002',
        titulo='Incidente crítico',
        descricao='Contexto operacional detalhado para recomendação.',
        urgencia='critica',
        area='Segurança',
        sistema='Auth',
        solicitante='ops@reqsys.local',
        status='aberto',
    )
    db_session.add(requisito)
    db_session.commit()

    incidente = svc.serializar_incidente(requisito)

    assert incidente['modulo'] == 'Segurança'
    assert incidente['funcionalidade'] == 'Auth'
    assert incidente['severidade'] == 'critica'
    assert incidente['score_atual'] == 0.95


def test_gerar_texto_recomendacao_fallback_local():
    payload = svc.gerar_texto_recomendacao(
        titulo='Erro de autenticação',
        contexto_incidente='Token expirado em produção',
        tipo_recomendacao='hotfix',
    )

    assert 'hotfix' in payload['recomendacao'].lower() or 'Erro de autenticação' in payload['recomendacao']
    assert payload['modelo'] == 'reqsys-heuristica-local'
    assert payload['confianca_ia'] > 0


def test_fluxo_recomendacoes_ia_via_api(client):
    requisito_payload = {
        'titulo': 'Falha no pipeline de deploy',
        'descricao': 'Erro intermitente no gate de cobertura durante merge automatizado.',
        'urgencia': 'alta',
        'area': 'Plataforma',
        'sistema': 'CI/CD',
        'solicitante': 'analista@reqsys.local',
        'impacto_regulatorio': False,
    }
    criado = client.post('/v1/requisitos', json=requisito_payload)
    assert criado.status_code == 200
    incidente_id = criado.json()['data']['id']

    incidentes = client.get('/v1/incidentes?limit=5')
    assert incidentes.status_code == 200
    incidentes_data = incidentes.json()['data']
    assert any(item['id'] == incidente_id for item in incidentes_data)
    incidente = next(item for item in incidentes_data if item['id'] == incidente_id)

    geracao = client.post(
        '/v1/ia/gerar-recomendacao',
        json={
            'titulo': incidente['titulo'],
            'contexto_incidente': incidente['resumo_contexto'],
            'tipo_recomendacao': 'hotfix',
        },
    )
    assert geracao.status_code == 200
    texto = geracao.json()['data']['recomendacao']

    criacao = client.post(
        '/v1/recomendacoes',
        json={
            'id_incidente': incidente_id,
            'titulo': incidente['titulo'],
            'contexto_incidente': incidente['resumo_contexto'],
            'tipo_recomendacao': 'hotfix',
            'confianca_ia': 0.81,
            'recomendacao': texto,
            'modelo': 'reqsys-heuristica-local',
            'score_inicial': 0.8,
        },
    )
    assert criacao.status_code == 201
    recomendacao_id = criacao.json()['data']['id']

    decisao = client.post(
        f'/v1/recomendacoes/{recomendacao_id}/decisao',
        json={'aceita': True, 'motivo_decisao': 'Ação imediata', 'decidido_por': 'analista@reqsys.local'},
    )
    assert decisao.status_code == 200
    assert decisao.json()['data']['decisao']['aceita'] is True

    outcome = client.post(
        f'/v1/recomendacoes/{recomendacao_id}/outcome',
        json={
            'foi_aplicada': True,
            'versao_aplicada': 'v3.1.1',
            'outcome_positivo': True,
            'score_pos_correcao': 0.9,
            'observacao': 'Correção validada em dev',
        },
    )
    assert outcome.status_code == 200
    assert outcome.json()['data']['outcome']['foi_aplicada'] is True

    dashboard = client.get('/v1/dashboard/ia?janela_dias=30')
    assert dashboard.status_code == 200
    metricas = dashboard.json()['data']
    assert metricas['amostras_total'] >= 1
    assert metricas['metricas']['taxa_aceitacao']['valor']['total'] >= 1


def test_calcular_dashboard_ia_sem_amostras(db_session):
    payload = svc.calcular_dashboard_ia(db_session, janela_dias=30)

    assert payload['amostras_total'] == 0
    assert payload['metricas']['taxa_aceitacao']['valor']['taxa'] == 0.0


def test_recomendacoes_api_retorna_404_quando_inexistente(client):
    response = client.get('/v1/recomendacoes/999999')
    assert response.status_code == 404


def test_recomendacoes_api_rejeita_decisao_sem_recomendacao(client):
    response = client.post(
        '/v1/recomendacoes/999999/decisao',
        json={'aceita': True, 'motivo_decisao': 'teste', 'decidido_por': 'qa@reqsys.local'},
    )
    assert response.status_code == 400


def test_recomendacoes_api_listar_e_obter(client):
    criado = client.post(
        '/v1/requisitos',
        json={
            'titulo': 'Listagem recomendacoes',
            'descricao': 'Cobertura de listagem e leitura por id.',
            'urgencia': 'media',
            'area': 'QA',
            'sistema': 'API',
            'solicitante': 'qa@reqsys.local',
            'impacto_regulatorio': False,
        },
    )
    incidente_id = criado.json()['data']['id']

    criacao = client.post(
        '/v1/recomendacoes',
        json={
            'id_incidente': incidente_id,
            'titulo': 'Recomendacao listagem',
            'contexto_incidente': 'contexto',
            'tipo_recomendacao': 'hotfix',
            'confianca_ia': 0.7,
            'recomendacao': 'Aplicar patch',
            'modelo': 'reqsys-heuristica-local',
        },
    )
    assert criacao.status_code == 201
    recomendacao_id = criacao.json()['data']['id']

    listagem = client.get('/v1/recomendacoes?limit=5')
    assert listagem.status_code == 200
    ids = [item['id'] for item in listagem.json()['data']]
    assert recomendacao_id in ids

    detalhe = client.get(f'/v1/recomendacoes/{recomendacao_id}')
    assert detalhe.status_code == 200
    assert detalhe.json()['data']['titulo'] == 'Recomendacao listagem'


def test_recomendacoes_api_rejeita_criacao_com_incidente_inexistente(client):
    response = client.post(
        '/v1/recomendacoes',
        json={
            'id_incidente': 999999,
            'titulo': 'Sem incidente',
            'tipo_recomendacao': 'hotfix',
            'recomendacao': 'Nao deve persistir',
        },
    )
    assert response.status_code == 404


def test_recomendacoes_api_rejeita_outcome_duplicado(client):
    criado = client.post(
        '/v1/requisitos',
        json={
            'titulo': 'Outcome duplicado',
            'descricao': 'Validacao de outcome ja registrado.',
            'urgencia': 'baixa',
            'area': 'QA',
            'sistema': 'API',
            'solicitante': 'qa@reqsys.local',
            'impacto_regulatorio': False,
        },
    )
    incidente_id = criado.json()['data']['id']
    criacao = client.post(
        '/v1/recomendacoes',
        json={
            'id_incidente': incidente_id,
            'titulo': 'Recomendacao outcome',
            'tipo_recomendacao': 'hotfix',
            'recomendacao': 'Corrigir fluxo',
        },
    )
    recomendacao_id = criacao.json()['data']['id']
    payload = {'foi_aplicada': True, 'versao_aplicada': 'v1.0.0'}

    primeiro = client.post(f'/v1/recomendacoes/{recomendacao_id}/outcome', json=payload)
    assert primeiro.status_code == 200

    duplicado = client.post(f'/v1/recomendacoes/{recomendacao_id}/outcome', json=payload)
    assert duplicado.status_code == 400
