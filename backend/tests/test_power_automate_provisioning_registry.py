import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_power_automate_provisioning_registry.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_power_automate_provisioning_registry_fluxo_plano_resumo_status():
    client = TestClient(app)
    correlation_id = 'test-pa-provisioning-registry-001'

    plan_response = client.post(
        '/v1/hub-lowcode/power-automate/flows/provisioning-plan',
        headers={'X-Correlation-Id': correlation_id},
        json={
            'display_name': 'ReqSys - Receber Requisito via HTTP',
            'trigger_type': 'HttpRequest',
            'description': 'Flow de pratica para ReqSys',
            'target_environment': 'dev',
            'solution_name': 'ReqSysAutomacao',
            'dry_run': True,
            'registrar': True,
        },
    )

    assert plan_response.status_code == 200
    plan_body = plan_response.json()
    assert plan_body['success'] is True
    assert plan_body['meta']['correlation_id'] == correlation_id
    assert plan_body['data']['registry']['status'] == 'planned'
    assert plan_body['data']['registry']['ambiente'] == 'dev'
    assert plan_body['data']['registry']['flow_display_name'] == 'ReqSys - Receber Requisito via HTTP'

    list_response = client.get('/v1/hub-lowcode/power-automate/flows/provisioning-registry')
    assert list_response.status_code == 200
    items = list_response.json()['data']['items']
    assert any(item['correlation_id'] == correlation_id for item in items)

    summary_response = client.get('/v1/hub-lowcode/power-automate/flows/provisioning-registry/summary')
    assert summary_response.status_code == 200
    summary = summary_response.json()['data']
    assert summary['schema_version'] == '1.0.0'
    assert summary['total'] >= 1
    assert 'dev' in summary['por_ambiente']

    status_response = client.patch(
        f'/v1/hub-lowcode/power-automate/flows/provisioning-registry/{correlation_id}/status',
        json={
            'status': 'succeeded',
            'workflow_run_url': 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions',
            'artifact_url': 'artifact://power-automate-flow-provisioning-p0/1',
        },
    )
    assert status_response.status_code == 200
    updated = status_response.json()['data']
    assert updated['status'] == 'succeeded'
    assert updated['workflow_run_url'].startswith('https://github.com/')
    assert updated['artifact_url'].startswith('artifact://')


def test_power_automate_provisioning_registry_rejeita_status_invalido():
    client = TestClient(app)
    correlation_id = 'test-pa-provisioning-registry-002'

    create_response = client.post(
        '/v1/hub-lowcode/power-automate/flows/provisioning-plan',
        headers={'X-Correlation-Id': correlation_id},
        json={
            'display_name': 'ReqSys - Flow Status Invalido',
            'trigger_type': 'Manual',
            'target_environment': 'test',
            'solution_name': 'ReqSysAutomacao',
            'registrar': True,
        },
    )
    assert create_response.status_code == 200

    response = client.patch(
        f'/v1/hub-lowcode/power-automate/flows/provisioning-registry/{correlation_id}/status',
        json={'status': 'verde_sem_evidencia'},
    )

    assert response.status_code >= 400
