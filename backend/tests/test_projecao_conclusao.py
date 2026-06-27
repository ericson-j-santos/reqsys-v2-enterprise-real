from fastapi.testclient import TestClient

from app.main import app


def test_projecao_conclusao_status_200():
    res = TestClient(app).get('/v1/estatisticas/projecao-conclusao')
    assert res.status_code == 200


def test_projecao_conclusao_envelope_e_schema():
    res = TestClient(app).get('/v1/estatisticas/projecao-conclusao')
    body = res.json()

    assert body['success'] is True
    data = body['data']
    assert data['schema_version'] == '1.0.0'
    assert data['modo'] == 'governado'
    assert data['referencia_temporal'] == '2026-06-27T21:00:00-03:00'
    assert isinstance(data['estado_atual_consolidado'], list)
    assert len(data['estado_atual_consolidado']) == 10
    assert isinstance(data['percentual_conclusao_real'], list)
    assert isinstance(data['projecao_tempo']['conservador'], list)
    assert isinstance(data['projecao_tempo']['acelerado'], list)


def test_projecao_conclusao_propaga_correlation_id():
    correlation_id = 'corr-projecao-conclusao-test'
    res = TestClient(app).get(
        '/v1/estatisticas/projecao-conclusao',
        headers={'X-Correlation-Id': correlation_id},
    )
    body = res.json()

    assert body['meta']['correlation_id'] == correlation_id
    assert body['data']['correlation_id'] == correlation_id


def test_projecao_conclusao_separa_evidenciado_de_projecao():
    res = TestClient(app).get('/v1/estatisticas/projecao-conclusao')
    percentuais = res.json()['data']['percentual_conclusao_real']

    assert percentuais
    for item in percentuais:
        assert item['tipo'] in {'evidenciado', 'projeção'}
        assert 0 <= item['percentual'] <= 100


def test_projecao_conclusao_resumo_e_leitura_executiva():
    res = TestClient(app).get('/v1/estatisticas/projecao-conclusao')
    data = res.json()['data']

    assert data['resumo']['padrao_ouro_consolidado_percentual'] == 52
    assert data['confianca_percentual'] == 87
    assert data['cenario_ativo'] == 'acelerado_recomendado'
    assert data['leitura_executiva']['nao_experimental'] is True
    assert len(data['gargalos_principais']) >= 5
    assert len(data['aceleradores_marginais']) >= 5


def test_projecao_conclusao_probabilidades_finais():
    res = TestClient(app).get('/v1/estatisticas/projecao-conclusao')
    probabilidades = res.json()['data']['probabilidades_finais']

    assert len(probabilidades) == 4
    mvp = next(p for p in probabilidades if 'MVP forte' in p['resultado'])
    assert mvp['probabilidade_percentual'] == 87
