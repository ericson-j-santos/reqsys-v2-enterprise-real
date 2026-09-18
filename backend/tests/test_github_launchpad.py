import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_github_launchpad.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.services.github_launchpad import montar_github_launchpad, normalizar_ambiente_launchpad
from app.models.agile_runtime import AgileWorkItem


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_normalizar_ambiente_launchpad_aliases():
    assert normalizar_ambiente_launchpad('dev') == 'dev'
    assert normalizar_ambiente_launchpad('desenvolvimento') == 'dev'
    assert normalizar_ambiente_launchpad('hml') == 'homolog'
    assert normalizar_ambiente_launchpad('producao') == 'prod'


def test_montar_github_launchpad_dev_com_branch_sugerida():
    item = AgileWorkItem(
        id=1,
        codigo='AGI-101',
        tipo='story',
        titulo='Corrigir login demo',
        descricao='Como operador, quero abrir a tarefa no GitHub com branch correta.',
        repositorio='org/reqsys',
        branch=None,
        pontos=0,
        valor_negocio=0,
        score_risco=0,
        ambiente_deploy='none',
        ci_status='unknown',
        deploy_status='not_started',
    )
    payload = montar_github_launchpad(item, 'dev')
    assert payload['ambiente'] == 'dev'
    assert payload['branch_base'] == 'dev'
    assert payload['branch_trabalho'].startswith('feature/')
    assert 'org/reqsys' in payload['repositorio']
    assert payload['links']['branch'].startswith('https://github.com/org/reqsys/tree/')
    assert 'compare/dev...' in payload['links']['criar_branch']
    assert 'quick_pull=1' in payload['links']['novo_pr']
    assert 'criar_branch_github' in payload['acoes_disponiveis']
    assert payload['somente_leitura'] is False
    assert 'AGI-101' in payload['mensagem_commit_sugerida']


def test_montar_github_launchpad_prod_somente_leitura():
    item = AgileWorkItem(
        id=2,
        codigo='AGI-202',
        tipo='story',
        titulo='Promover release',
        descricao='Story de promocao para producao com links read-only.',
        repositorio='org/reqsys',
        branch='feature/backend/agi-202-promover-release',
        pontos=0,
        valor_negocio=0,
        score_risco=0,
        ambiente_deploy='prod',
        ci_status='unknown',
        deploy_status='not_started',
    )
    payload = montar_github_launchpad(item, 'prod')
    assert payload['ambiente'] == 'prod'
    assert payload['branch_base'] == 'main'
    assert payload['branch_trabalho'] == 'main'
    assert payload['somente_leitura'] is True
    assert payload['acoes_disponiveis'] == ['abrir_branch', 'abrir_app']
    assert 'criar_branch_github' not in payload['acoes_disponiveis']


def test_github_launchpad_endpoint():
    client = TestClient(app)
    correlation_id = 'test-github-launchpad-001'

    create_response = client.post(
        '/v1/agile-runtime/work-items',
        headers={'X-Correlation-Id': correlation_id},
        json={
            'tipo': 'story',
            'titulo': 'Launchpad GitHub por ambiente',
            'descricao': 'Como desenvolvedor, quero abrir a tarefa no GitHub com branch e ambiente corretos.',
            'prioridade': 'P1',
            'repositorio': 'org/reqsys',
            'branch': 'feature/frontend/agi-launchpad-github',
        },
    )
    assert create_response.status_code == 200
    work_item_id = create_response.json()['data']['id']

    launchpad_response = client.get(
        f'/v1/agile-runtime/work-items/{work_item_id}/github-launchpad',
        params={'ambiente': 'dev'},
    )
    assert launchpad_response.status_code == 200
    body = launchpad_response.json()
    assert body['success'] is True
    data = body['data']
    assert data['branch_trabalho'] == 'feature/frontend/agi-launchpad-github'
    assert data['links']['branch'].endswith('/tree/feature/frontend/agi-launchpad-github')
    assert data['links']['app_ambiente']

    invalid_response = client.get(
        f'/v1/agile-runtime/work-items/{work_item_id}/github-launchpad',
        params={'ambiente': 'invalido'},
    )
    assert invalid_response.status_code == 422
