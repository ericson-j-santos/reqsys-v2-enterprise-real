import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_agile_runtime.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_agile_runtime_fluxo_story_sprint_workflow_rastreabilidade_evidencia_resumo():
    client = TestClient(app)
    correlation_id = 'test-agile-runtime-flow-001'

    sprint_response = client.post(
        '/v1/agile-runtime/sprints',
        headers={'X-Correlation-Id': correlation_id},
        json={
            'nome': 'Sprint Agile Runtime Teste',
            'objetivo': 'Validar fluxo backend minimo do Agile Runtime Core',
            'data_inicio': '2026-06-25',
            'data_fim': '2026-07-09',
            'capacidade_pontos': 13,
            'pontos_comprometidos': 8,
        },
    )
    assert sprint_response.status_code == 200
    sprint_body = sprint_response.json()
    assert sprint_body['success'] is True
    sprint_id = sprint_body['data']['id']
    assert sprint_body['data']['codigo'].startswith('SPR-')

    story_response = client.post(
        '/v1/agile-runtime/work-items',
        headers={'X-Correlation-Id': correlation_id},
        json={
            'tipo': 'story',
            'titulo': 'Validar fluxo Agile Runtime',
            'descricao': 'Como operador do ReqSys, quero rastrear story, CI e evidencia no Agile Runtime.',
            'prioridade': 'P1',
            'pontos': 5,
            'valor_negocio': 80,
            'score_risco': 20,
            'owner_ai': 'qa-ia',
            'sprint_id': sprint_id,
            'criterios_aceite': 'Dado uma story, quando houver CI verde, entao a evidencia deve ser registrada.',
            'repositorio': 'ericson-j-santos/reqsys-v2-enterprise-real',
            'branch': 'feature/agile-runtime-backend-tests',
        },
    )
    assert story_response.status_code == 200
    story_body = story_response.json()
    assert story_body['success'] is True
    work_item_id = story_body['data']['id']
    assert story_body['data']['codigo'].startswith('AGI-')
    assert story_body['data']['status'] == 'novo'

    for status in ['refinando', 'pronto_para_sprint', 'planejado', 'em_execucao', 'em_revisao', 'em_ci']:
        transition_response = client.patch(
            f'/v1/agile-runtime/work-items/{work_item_id}/workflow',
            headers={'X-Correlation-Id': correlation_id},
            json={'status': status, 'motivo': 'Fluxo automatizado de teste'},
        )
        assert transition_response.status_code == 200
        assert transition_response.json()['data']['status'] == status

    invalid_transition_response = client.patch(
        f'/v1/agile-runtime/work-items/{work_item_id}/workflow',
        headers={'X-Correlation-Id': correlation_id},
        json={'status': 'concluido', 'motivo': 'Nao pode pular gates'},
    )
    assert invalid_transition_response.status_code == 409

    traceability_response = client.patch(
        f'/v1/agile-runtime/work-items/{work_item_id}/traceability',
        headers={'X-Correlation-Id': correlation_id},
        json={
            'repositorio': 'ericson-j-santos/reqsys-v2-enterprise-real',
            'branch': 'feature/agile-runtime-backend-tests',
            'change_provider': 'github',
            'change_id': '283',
            'change_url': 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/283',
            'ci_provider': 'github_actions',
            'ci_run_id': 'reqsys-ci-test-run',
            'ci_status': 'success',
            'ci_url': 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions',
            'ambiente_deploy': 'test',
            'deploy_status': 'deployed',
            'deploy_url': 'http://localhost:8084',
        },
    )
    assert traceability_response.status_code == 200
    traceability_body = traceability_response.json()['data']
    assert traceability_body['change_provider'] == 'github'
    assert traceability_body['ci_status'] == 'success'
    assert traceability_body['deploy_status'] == 'deployed'

    evidence_response = client.post(
        f'/v1/agile-runtime/work-items/{work_item_id}/evidences',
        headers={'X-Correlation-Id': correlation_id},
        json={
            'tipo': 'ci',
            'titulo': 'CI verde do fluxo Agile Runtime',
            'url': 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions',
            'status': 'success',
            'observacao': 'Evidencia sintetica usada em teste automatizado.',
            'criado_por': 'pytest',
        },
    )
    assert evidence_response.status_code == 200
    evidence_body = evidence_response.json()['data']
    assert evidence_body['work_item_id'] == work_item_id
    assert evidence_body['correlation_id'] == correlation_id

    evidences_response = client.get(f'/v1/agile-runtime/work-items/{work_item_id}/evidences')
    assert evidences_response.status_code == 200
    assert len(evidences_response.json()['data']) >= 1

    resumo_response = client.get('/v1/agile-runtime/resumo')
    assert resumo_response.status_code == 200
    resumo = resumo_response.json()['data']
    assert resumo['total_sprints'] >= 1
    assert resumo['total_itens'] >= 1
    assert resumo['total_evidencias'] >= 1
    assert resumo['itens_em_ci'] >= 1
    assert resumo['ci_success_percentual'] >= 0.0
