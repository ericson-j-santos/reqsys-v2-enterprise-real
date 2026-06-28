import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_power_automate_requisitos.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_power_automate_post_get_e_contrato_requisitos():
    client = TestClient(app)
    correlation_id = 'test-power-automate-requisitos-001'

    create_response = client.post(
        '/api/requisitos',
        headers={'X-Correlation-Id': correlation_id},
        json={
            'schema_version': '1.0.0',
            'titulo': 'Validar payload Power Automate',
            'descricao': 'O ReqSys deve receber requisitos enviados por fluxo HTTP POST do Power Automate.',
            'tipo': 'funcional',
            'prioridade': 'alta',
            'area': 'Arquitetura',
            'sistema': 'ReqSys',
            'solicitante': 'Power Automate',
            'impacto_regulatorio': False,
        },
    )

    assert create_response.status_code == 201
    create_body = create_response.json()
    assert create_body['success'] is True
    assert create_body['meta']['correlation_id'] == correlation_id
    assert create_body['meta']['contract'] == 'reqsys-power-automate-requisitos'
    assert create_body['data']['codigo'].startswith('REQ-')
    assert create_body['data']['prioridade'] == 'alta'

    codigo = create_body['data']['codigo']

    get_response = client.get(f'/api/requisitos/{codigo}', headers={'X-Correlation-Id': correlation_id})
    assert get_response.status_code == 200
    get_body = get_response.json()
    assert get_body['success'] is True
    assert get_body['data']['codigo'] == codigo
    assert get_body['data']['schema_version'] == '1.0.0'

    list_response = client.get('/api/requisitos', headers={'X-Correlation-Id': correlation_id})
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body['data']['schema_version'] == '1.0.0'
    assert list_body['data']['total'] >= 1

    contract_response = client.get('/api/runtime/contracts')
    assert contract_response.status_code == 200
    optional_paths = {item['path'] for item in contract_response.json()['data']['optional_public_evidence']}
    assert '/api/requisitos' in optional_paths
    assert '/api/requisitos/{codigo}' in optional_paths


def test_power_automate_payload_invalido_retorna_422():
    client = TestClient(app)

    response = client.post(
        '/api/requisitos',
        json={
            'schema_version': '1.0.0',
            'titulo': 'Curto',
            'descricao': 'Descricao invalida curta.',
            'tipo': 'invalido',
            'prioridade': 'urgente',
        },
    )

    assert response.status_code == 422
