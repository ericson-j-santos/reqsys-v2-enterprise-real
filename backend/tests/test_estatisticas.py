from fastapi.testclient import TestClient

from app.main import app


def test_estatisticas_status_200():
    res = TestClient(app).get('/v1/estatisticas')
    assert res.status_code == 200


def test_estatisticas_envelope_e_schema_v2():
    res = TestClient(app).get('/v1/estatisticas')
    body = res.json()

    assert body['success'] is True
    assert body['data']['schema_version'] == '2.0.0'
    assert isinstance(body['data']['indicadores'], list)
    assert body['data']['resumo']['total'] == len(body['data']['indicadores'])


def test_estatisticas_propaga_correlation_id():
    correlation_id = 'corr-estatisticas-v2-test'
    res = TestClient(app).get('/v1/estatisticas', headers={'X-Correlation-Id': correlation_id})
    body = res.json()

    assert body['meta']['correlation_id'] == correlation_id
    assert body['data']['correlation_id'] == correlation_id


def test_estatisticas_indicadores_possuem_fonte_formula_e_estado():
    res = TestClient(app).get('/v1/estatisticas')
    indicadores = res.json()['data']['indicadores']

    assert indicadores
    for indicador in indicadores:
        assert indicador['id']
        assert indicador['nome']
        assert indicador['formula']
        assert indicador['estadoAtual'] in {'nao_medido', 'critico', 'atencao', 'adequado', 'avancado'}
        assert indicador['estadoAlvo'] in {'adequado', 'avancado', 'excelencia'}
        assert indicador['tendencia'] in {'subindo', 'estavel', 'caindo', 'indefinida'}
        assert indicador['fonte']['id']
        assert indicador['fonte']['tipo'] in {'interna', 'externa'}
        assert indicador['fonte']['coletadoEm']
        assert indicador['fonte']['confiabilidade'] in {'alta', 'media', 'baixa'}


def test_estatisticas_fonte_externa_permanece_nao_medida_sem_registry_real():
    res = TestClient(app).get('/v1/estatisticas')
    indicadores = res.json()['data']['indicadores']
    externo = next(item for item in indicadores if item['id'] == 'fontes-externas-validas')

    assert externo['fonte']['tipo'] == 'externa'
    assert externo['estadoAtual'] == 'nao_medido'
    assert externo['fonte']['ttlMinutos'] > 0
