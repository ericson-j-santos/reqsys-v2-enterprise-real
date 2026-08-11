from time import perf_counter

import pytest

from app.core.fila_observability import (
    EstadoFila,
    RegistroObservabilidadeFila,
    TransicaoFila,
    anonimizar_demanda_id,
    registrar_transicao_fila,
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
