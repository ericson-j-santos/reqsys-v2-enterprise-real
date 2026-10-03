from app.services.requisitos_runtime_events import (
    EVENTO_REQUISITO_TRANSICIONADO,
    publicar_requisito_transicionado,
    resumir_runtime_requisitos,
)
from app.services.runtime_core import RuntimeEventStatus


def test_publica_evento_requisito_transicionado_com_correlation_id():
    resultados = publicar_requisito_transicionado(
        requisito_id=1,
        requisito_codigo='REQ-000000001',
        origem='recebido',
        destino='refinamento',
        usuario='qa.reqsys',
        motivo='Fluxo validado por teste.',
        evidencia_informada=False,
        score_prontidao=82,
        correlation_id='corr-workflow-001',
    )

    resumo = resumir_runtime_requisitos()

    assert resultados[0].status == RuntimeEventStatus.PENDING
    assert resumo['eventos_publicados'] >= 1
    assert resumo['ultimo_evento']['event_type'] == EVENTO_REQUISITO_TRANSICIONADO
    assert resumo['ultimo_evento']['correlation_id'] == 'corr-workflow-001'
    assert resumo['ultimo_evento']['aggregate_type'] == 'requisito'
    assert resumo['ultimo_evento']['payload_minimo']['destino'] == 'refinamento'
    assert resumo['dead_letters'] == 0


def test_publicacao_usa_correlation_id_padrao_quando_header_nao_informado():
    publicar_requisito_transicionado(
        requisito_id='2',
        requisito_codigo='REQ-000000002',
        origem='validado',
        destino='evidenciado',
        usuario='qa.reqsys',
        motivo=None,
        evidencia_informada=True,
        score_prontidao=90,
        correlation_id=None,
    )

    resumo = resumir_runtime_requisitos()

    assert resumo['ultimo_evento']['correlation_id'] == 'sem-correlation-id'
    assert resumo['ultimo_evento']['payload_minimo']['motivo_informado'] is False
    assert resumo['ultimo_evento']['payload_minimo']['evidencia_informada'] is True
