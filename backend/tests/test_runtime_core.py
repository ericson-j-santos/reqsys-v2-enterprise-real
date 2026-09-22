import pytest

from app.services.runtime_core import (
    RetryPolicy,
    RuntimeEventBus,
    RuntimeEventEnvelope,
    RuntimeEventStatus,
)


def evento(**overrides):
    payload = {
        'event_type': 'REQUISITO_TRANSICIONADO',
        'source': 'tests.runtime_core',
        'aggregate_type': 'requisito',
        'aggregate_id': 'REQ-000000001',
        'correlation_id': 'corr-001',
        'payload': {'origem': 'recebido', 'destino': 'refinamento'},
    }
    payload.update(overrides)
    return RuntimeEventEnvelope(**payload)


def test_envelope_expoe_payload_minimo_para_auditoria():
    envelope = evento()

    auditoria = envelope.to_audit_payload()

    assert auditoria['schema_version'] == '1.0.0'
    assert auditoria['event_id'].startswith('evt-')
    assert auditoria['event_type'] == 'REQUISITO_TRANSICIONADO'
    assert auditoria['correlation_id'] == 'corr-001'
    assert auditoria['payload_minimo']['destino'] == 'refinamento'


def test_envelope_bloqueia_campos_obrigatorios_ausentes():
    with pytest.raises(ValueError) as exc:
        evento(event_type='')

    assert 'event_type' in str(exc.value)


def test_event_bus_entrega_evento_para_handler_assinado():
    bus = RuntimeEventBus()
    entregues = []

    def handler(envelope):
        entregues.append(envelope.event_id)

    bus.subscribe('REQUISITO_TRANSICIONADO', handler)
    resultados = bus.publish(evento())

    assert entregues == [resultados[0].event_id]
    assert resultados[0].status == RuntimeEventStatus.DELIVERED
    assert resultados[0].attempts == 1
    assert len(bus.dead_letters()) == 0


def test_event_bus_registra_evento_sem_handler_como_pending_sem_falhar():
    bus = RuntimeEventBus()

    resultados = bus.publish(evento(event_type='EVENTO_SEM_HANDLER'))

    assert resultados[0].handler_name == 'sem-handler'
    assert resultados[0].status == RuntimeEventStatus.PENDING
    assert resultados[0].attempts == 0
    assert len(bus.published_events()) == 1


def test_event_bus_envia_para_dead_letter_apos_retries():
    bus = RuntimeEventBus(retry_policy=RetryPolicy(max_attempts=2))

    def handler_falho(_envelope):
        raise RuntimeError('falha controlada')

    bus.subscribe('REQUISITO_TRANSICIONADO', handler_falho)
    resultados = bus.publish(evento())

    assert resultados[0].status == RuntimeEventStatus.DEAD_LETTER
    assert resultados[0].attempts == 2
    assert resultados[0].error == 'falha controlada'
    assert len(bus.dead_letters()) == 1
    assert bus.dead_letters()[0].handler_name == 'handler_falho'


def test_retry_policy_exige_pelo_menos_uma_tentativa():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
