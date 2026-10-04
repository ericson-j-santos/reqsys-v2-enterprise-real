"""Testes de caminhos críticos — API de incidentes (paridade recomendações IA)."""

import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_incidentes_api.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')


def test_listar_incidentes_retorna_envelope(client):
    response = client.get('/v1/incidentes?limit=5')
    assert response.status_code == 200
    body = response.json()
    assert 'data' in body
    assert isinstance(body['data'], list)


def test_obter_incidente_inexistente_retorna_404(client):
    response = client.get('/v1/incidentes/999999')
    assert response.status_code == 404
    assert response.json()['detail'] == 'Incidente/requisito não encontrado.'


def test_obter_incidente_por_id_apos_criar_requisito(client):
    criado = client.post(
        '/v1/requisitos',
        json={
            'titulo': 'Incidente API',
            'descricao': 'Validação de leitura por id na rota de incidentes.',
            'urgencia': 'media',
            'area': 'Operações',
            'sistema': 'Monitoramento',
            'solicitante': 'qa@reqsys.local',
            'impacto_regulatorio': False,
        },
    )
    assert criado.status_code == 200
    incidente_id = criado.json()['data']['id']

    response = client.get(f'/v1/incidentes/{incidente_id}')
    assert response.status_code == 200
    incidente = response.json()['data']
    assert incidente['id'] == incidente_id
    assert incidente['titulo'] == 'Incidente API'
