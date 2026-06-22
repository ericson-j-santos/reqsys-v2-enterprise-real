"""Testes do contrato de monitoramento operacional do ReqSys."""

from fastapi.testclient import TestClient

from app.api.monitoramento_operacional import (
    ItemMonitorado,
    classificar_estado_geral,
    criar_tempo_operacional,
)
from app.main import app


def test_monitoramento_operacional_status_200():
    res = TestClient(app).get('/monitoramento-operacional')
    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    assert body['data']['schema_version'] == '1.2.0'
    assert body['data']['resumo']['total_itens'] == len(body['data']['itens'])
    assert 'frentes_criticas' in body['data']['resumo']
    assert 'itens_prontos_para_merge' in body['data']['resumo']
    assert 'tempo_operacional' in body['data']


def test_monitoramento_operacional_propaga_correlation_id():
    correlation_id = 'corr-oper-006-test'
    res = TestClient(app).get('/monitoramento-operacional', headers={'X-Correlation-Id': correlation_id})

    assert res.status_code == 200
    body = res.json()
    assert body['meta']['correlation_id'] == correlation_id
    assert body['data']['correlation_id'] == correlation_id


def test_monitoramento_operacional_expoe_frentes_operacionais_prioritarias():
    res = TestClient(app).get('/monitoramento-operacional')
    referencias = {item['referencia'] for item in res.json()['data']['itens']}

    assert {'REQSYS-OPER-001', 'REQSYS-OPER-002', 'REQSYS-OPER-003'} <= referencias
    assert {'REQSYS-OPER-004', 'REQSYS-OPER-005'} <= referencias


def test_monitoramento_operacional_expoe_proximos_passos_e_criterios():
    res = TestClient(app).get('/monitoramento-operacional')
    itens = res.json()['data']['itens']
    pendencias = [item for item in itens if item['estado'] in {'amarelo', 'vermelho'}]

    assert pendencias
    assert all(item['proximo_passo'] for item in pendencias)
    assert all(item['criterio_de_fechamento'] for item in pendencias)


def test_monitoramento_operacional_expoe_tempo_operacional():
    res = TestClient(app).get('/monitoramento-operacional')
    tempo = res.json()['data']['tempo_operacional']

    assert tempo['previsao_proxima_acao']
    assert tempo['eta_proxima_verificacao_minutos'] > 0
    assert tempo['tempo_medio_proxima_acao_minutos'] > 0
    assert tempo['tempo_medio_resolucao_horas'] > 0
    assert tempo['tempo_medio_review_minutos'] > 0
    assert tempo['sla_operacional_minutos'] > 0


def test_monitoramento_operacional_estado_geral_reflete_bloqueio_govbi():
    res = TestClient(app).get('/monitoramento-operacional')
    data = res.json()['data']

    assert data['resumo']['estado_geral'] == 'bloqueado'
    assert data['resumo']['bloqueios'] >= 1
    assert data['resumo']['pendencias'] > 0
    assert data['tempo_operacional']['eta_proxima_verificacao_minutos'] == 10


def test_classificar_estado_geral_prioriza_bloqueio():
    itens = [
        ItemMonitorado(
            tipo='gate',
            referencia='ok',
            titulo='OK',
            estado='verde',
            severidade='baixa',
            origem='teste',
        ),
        ItemMonitorado(
            tipo='pr',
            referencia='bloq',
            titulo='Bloqueado',
            estado='verde',
            severidade='critica',
            origem='teste',
            bloqueante=True,
        ),
    ]

    assert classificar_estado_geral(itens) == 'bloqueado'


def test_classificar_estado_geral_sem_itens_desconhecido():
    assert classificar_estado_geral([]) == 'desconhecido'


def test_classificar_estado_geral_cobre_vermelho_amarelo_desconhecido_e_verde():
    vermelho = ItemMonitorado(tipo='x', referencia='r1', titulo='T1', estado='vermelho', severidade='alta', origem='teste')
    amarelo = ItemMonitorado(tipo='x', referencia='r2', titulo='T2', estado='amarelo', severidade='media', origem='teste')
    desconhecido = ItemMonitorado(tipo='x', referencia='r3', titulo='T3', estado='desconhecido', severidade='media', origem='teste')
    verde = ItemMonitorado(tipo='x', referencia='r4', titulo='T4', estado='verde', severidade='baixa', origem='teste')

    assert classificar_estado_geral([vermelho]) == 'vermelho'
    assert classificar_estado_geral([amarelo]) == 'amarelo'
    assert classificar_estado_geral([desconhecido]) == 'amarelo'
    assert classificar_estado_geral([verde]) == 'verde'


def test_criar_tempo_operacional_cobre_estados_operacionais():
    tempo_bloqueado = criar_tempo_operacional('bloqueado')
    tempo_amarelo = criar_tempo_operacional('amarelo')
    tempo_vermelho = criar_tempo_operacional('vermelho')
    tempo_verde = criar_tempo_operacional('verde')

    assert tempo_bloqueado.eta_proxima_verificacao_minutos == 10
    assert tempo_bloqueado.sla_operacional_minutos == 60
    assert tempo_amarelo.eta_proxima_verificacao_minutos == 15
    assert tempo_vermelho.tempo_medio_review_minutos == 45
    assert tempo_verde.eta_proxima_verificacao_minutos == 30
    assert tempo_verde.sla_operacional_minutos == 240
