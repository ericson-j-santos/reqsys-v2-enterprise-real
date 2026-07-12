"""
Testes do modulo Auditoria.

Cobertura minima:
- listagem paginada de eventos;
- filtros basicos;
- historico de configuracao de infraestrutura;
- validacao de parametros invalidos.
"""


def test_auditoria_eventos_retorna_200(client):
    resp = client.get('/v1/auditoria/eventos?limit=5&offset=0')

    assert resp.status_code == 200


def test_auditoria_eventos_retorna_envelope_e_paginacao(client):
    resp = client.get('/v1/auditoria/eventos?limit=5&offset=0')
    body = resp.json()

    assert body['success'] is True
    assert 'data' in body
    assert 'dados' in body['data']
    assert 'paginacao' in body['data']
    assert body['data']['paginacao']['limit'] == 5
    assert body['data']['paginacao']['offset'] == 0


def test_auditoria_eventos_aceita_filtros(client):
    resp = client.get('/v1/auditoria/eventos?entidade=infra&acao=CONFIG_DOMINIO_ATUALIZADA&limit=10')

    assert resp.status_code == 200
    data = resp.json()['data']
    assert isinstance(data['dados'], list)
    assert 'total' in data['paginacao']


def test_auditoria_config_infra_retorna_historico(client):
    resp = client.get('/v1/auditoria/eventos/config-infra?limit=10')

    assert resp.status_code == 200
    data = resp.json()['data']
    assert 'config_historico' in data
    assert 'total' in data
    assert isinstance(data['config_historico'], list)


def test_auditoria_limit_invalido_retorna_422(client):
    resp = client.get('/v1/auditoria/eventos?limit=0')

    assert resp.status_code == 422
    detail = resp.json().get('detail', [])
    assert any(err.get('loc') == ['query', 'limit'] for err in detail)


def test_auditoria_purgar_exige_admin(client):
    resp = client.post('/v1/auditoria/purgar')

    assert resp.status_code in (401, 403)


def test_auditoria_purgar_com_admin_retorna_retencao_aplicada(client, auth_headers):
    # retention_days bem alto para nao apagar nada de real neste ambiente de teste
    resp = client.post('/v1/auditoria/purgar?retention_days=36500', headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['retention_days'] == 36500
    assert data['registros_removidos'] == 0
