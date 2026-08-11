from time import perf_counter

import pytest

from app.core.fila_observability import (
    EstadoFila,
    PoliticaSLOFila,
    RegistroObservabilidadeFila,
    RepositorioSnapshotsFila,
    TransicaoFila,
    anonimizar_demanda_id,
    avaliar_slos_fila,
    criar_cards_dashboard_fila,
    registrar_transicao_fila,
    renderizar_metricas_prometheus,
)


def _evento(origem, destino, *, sucesso=True, erro_codigo=None):
    return TransicaoFila(
        demanda_hash=anonimizar_demanda_id('DEM-123'),
        estado_origem=origem,
        estado_destino=destino,
        correlation_id='corr-teste',
        duracao_ms=25,
        sucesso=sucesso,
        erro_codigo=erro_codigo,
    )


def test_fluxo_completo_publica_quatro_sinais():
    registro = RegistroObservabilidadeFila()
    registro.registrar(_evento(EstadoFila.DISPONIVEL, EstadoFila.RESERVADA))
    registro.registrar(_evento(EstadoFila.RESERVADA, EstadoFila.EM_ATENDIMENTO))
    registro.registrar(_evento(EstadoFila.EM_ATENDIMENTO, EstadoFila.CONCLUIDA))

    sinais = registro.snapshot()['quatro_sinais']

    assert sinais['volume']['transicoes_total'] == 3
    assert sinais['latencia']['p95_ms'] == 25
    assert sinais['erros']['total'] == 0
    assert sinais['saturacao']['por_estado']['CONCLUIDA'] == 1


def test_transicao_invalida_e_bloqueada():
    registro = RegistroObservabilidadeFila()

    with pytest.raises(ValueError, match='transicao_invalida'):
        registro.registrar(_evento(EstadoFila.DISPONIVEL, EstadoFila.CONCLUIDA))


def test_erro_e_classificado_sem_expor_demanda():
    registro = RegistroObservabilidadeFila()
    evento = _evento(
        EstadoFila.RESERVADA,
        EstadoFila.DISPONIVEL,
        sucesso=False,
        erro_codigo='TIMEOUT_DEPENDENCIA',
    )
    registro.registrar(evento)
    snapshot = registro.snapshot()

    assert snapshot['quatro_sinais']['erros']['por_codigo']['TIMEOUT_DEPENDENCIA'] == 1
    assert evento.demanda_hash != 'DEM-123'
    assert len(evento.demanda_hash) == 16


def test_api_exige_correlation_id():
    with pytest.raises(ValueError, match='correlation_id_obrigatorio'):
        registrar_transicao_fila(
            demanda_id='DEM-123',
            estado_origem=EstadoFila.DISPONIVEL,
            estado_destino=EstadoFila.RESERVADA,
            correlation_id=' ',
            inicio=perf_counter(),
        )



def test_persistencia_armazena_somente_agregados(tmp_path):
    registro = RegistroObservabilidadeFila()
    registro.registrar(_evento(EstadoFila.DISPONIVEL, EstadoFila.RESERVADA))
    repositorio = RepositorioSnapshotsFila(
        database_url=f"sqlite:///{tmp_path / 'fila.db'}",
        limite=2,
    )

    repositorio.registrar(registro.snapshot())
    historico = repositorio.listar()

    assert len(historico) == 1
    assert historico[0]['guardrails']['sem_pii'] is True
    assert 'demanda_hash' not in str(historico[0])
    assert 'correlation_id' not in str(historico[0])


def test_metricas_prometheus_tem_cardinalidade_governada():
    registro = RegistroObservabilidadeFila()
    registro.registrar(_evento(EstadoFila.DISPONIVEL, EstadoFila.RESERVADA))

    metricas = renderizar_metricas_prometheus(registro.snapshot())

    assert 'reqsys_fila_transicoes_total{origem="DISPONIVEL",destino="RESERVADA"} 1' in metricas
    assert 'reqsys_fila_latencia_p95_ms 25' in metricas
    assert 'DEM-123' not in metricas
    assert 'corr-teste' not in metricas


def test_dashboard_publica_os_quatro_sinais():
    cards = criar_cards_dashboard_fila(RegistroObservabilidadeFila().snapshot())

    assert [card['id'] for card in cards] == [
        'fila-volume',
        'fila-latencia-p95',
        'fila-erros',
        'fila-saturacao',
    ]
    assert all(card['drilldown'].startswith('/api/runtime/fila/') for card in cards)



def test_slo_identifica_erros_latencia_e_saturacao():
    snapshot = RegistroObservabilidadeFila().snapshot()
    snapshot['quatro_sinais']['erros'] = {'total': 2, 'taxa_percentual': 10.0, 'por_codigo': {}}
    snapshot['quatro_sinais']['latencia']['p95_ms'] = 2500
    snapshot['quatro_sinais']['saturacao']['demandas_ativas'] = 60

    resultado = avaliar_slos_fila(snapshot, [], PoliticaSLOFila())

    assert resultado['status'] == 'alerta'
    assert {alerta['codigo'] for alerta in resultado['alertas']} == {
        'FILA_TAXA_ERROS_ACIMA_SLO',
        'FILA_LATENCIA_P95_ACIMA_SLO',
        'FILA_SATURACAO_ACIMA_SLO',
    }
    assert resultado['guardrails']['sem_disparo_externo'] is True


def test_slo_identifica_crescimento_continuo():
    registro = RegistroObservabilidadeFila()
    snapshot = registro.snapshot()
    snapshot['quatro_sinais']['saturacao']['demandas_ativas'] = 3
    historico = []
    for valor in (2, 1):
        item = registro.snapshot()
        item['quatro_sinais']['saturacao']['demandas_ativas'] = valor
        historico.append(item)

    resultado = avaliar_slos_fila(
        snapshot,
        historico,
        PoliticaSLOFila(demandas_ativas_maximas=100),
    )

    assert resultado['alertas'][0]['codigo'] == 'FILA_CRESCIMENTO_CONTINUO'


def test_slo_sem_violacao_permanece_verde():
    resultado = avaliar_slos_fila(
        RegistroObservabilidadeFila().snapshot(),
        [],
        PoliticaSLOFila(),
    )

    assert resultado['status'] == 'dentro_do_slo'
    assert resultado['alertas'] == []
