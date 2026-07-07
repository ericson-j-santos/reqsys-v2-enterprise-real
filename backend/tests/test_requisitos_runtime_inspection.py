from fastapi.testclient import TestClient

from app.main import app
from app.services.requisitos_runtime_events import publicar_requisito_transicionado

client = TestClient(app)


def test_runtime_requisitos_inspection_endpoint_expoe_snapshot_governado():
    publicar_requisito_transicionado(
        requisito_id='REQ-INSPECT-1',
        requisito_codigo='REQ-INSPECT-1',
        origem='recebido',
        destino='refinamento',
        usuario='qa.reqsys',
        motivo='Validacao de inspecao runtime.',
        evidencia_informada=False,
        score_prontidao=81,
        correlation_id='corr-runtime-inspection-001',
    )

    response = client.get(
        '/api/requisitos/runtime/inspection',
        headers={'x-correlation-id': 'corr-runtime-inspection-001'},
    )

    assert response.status_code == 200
    body = response.json()
    assert body['success'] is True
    assert body['errors'] == []
    assert body['meta']['correlation_id'] == 'corr-runtime-inspection-001'
    assert body['meta']['contract'] == 'reqsys-requisitos-runtime-inspection-v1'
    assert body['data']['schema_version'] == '1.0.0'
    assert body['data']['health']['status'] == 'healthy'
    assert body['data']['health']['eventos_publicados'] >= 1
    assert body['data']['health']['dead_letters'] == 0
    assert body['data']['runtime']['ultimo_evento']['correlation_id'] == 'corr-runtime-inspection-001'
