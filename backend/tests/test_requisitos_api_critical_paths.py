"""Caminhos críticos — API de requisitos."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_obter_requisito_inexistente_retorna_404():
    response = client.get('/v1/requisitos/REQ-INEXISTENTE-999999999')
    assert response.status_code == 404
    body = response.json()
    assert body['detail']['code'] == 'REQUISITO_NAO_ENCONTRADO'


def test_obter_requisito_por_id_inexistente_retorna_404():
    response = client.get('/v1/requisitos/999999999')
    assert response.status_code == 404


def test_obter_requisito_com_correlation_id():
    criar = client.post(
        '/v1/requisitos',
        json={
            'titulo': 'Requisito critical path',
            'descricao': 'Descricao minima valida para teste',
            'solicitante': 'reqsys-ci@example.com',
            'area': 'TI',
            'sistema': 'ReqSys',
            'urgencia': 'media',
            'impacto_regulatorio': False,
        },
        headers={'X-Correlation-ID': 'corr-req-critical-1'},
    )
    assert criar.status_code == 200
    codigo = criar.json()['data']['codigo']
    obter = client.get(f'/v1/requisitos/{codigo}', headers={'X-Correlation-ID': 'corr-req-critical-1'})
    assert obter.status_code == 200
    assert obter.json()['meta']['correlation_id'] == 'corr-req-critical-1'
