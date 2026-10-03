import pytest

from app.services.email_operations_center import (
    EmailDeliveryRequest,
    EmailOperationStatus,
    EmailOperationsCenter,
    EmailOperationSeverity,
    FakeEmailDeliveryGateway,
    InMemoryEmailOperationsRepository,
)


def _request(max_attempts: int = 3) -> EmailDeliveryRequest:
    return EmailDeliveryRequest(
        subject="[REQSYS] Relatorio Executivo Operacional",
        recipients=("ericson.takay@gmail.com",),
        correlation_id="REQSYS-EMAIL-OPS-TEST-001",
        html_body="<strong>SUCCESS</strong>",
        text_body="SUCCESS",
        max_attempts=max_attempts,
        metadata={"source": "unit-test"},
    )


def test_enqueue_registra_operacao_e_evento_de_fila():
    repository = InMemoryEmailOperationsRepository()
    center = EmailOperationsCenter(repository=repository, gateway=FakeEmailDeliveryGateway())

    operation = center.enqueue(_request())

    assert operation.status == EmailOperationStatus.QUEUED
    assert center.metrics().queued == 1
    assert center.metrics().total == 1

    timeline = center.timeline(operation.operation_id)
    assert len(timeline) == 1
    assert timeline[0].status == EmailOperationStatus.QUEUED
    assert timeline[0].severity == EmailOperationSeverity.INFO
    assert timeline[0].correlation_id == "REQSYS-EMAIL-OPS-TEST-001"


def test_process_next_entrega_com_sucesso_e_registra_provider_message_id():
    center = EmailOperationsCenter(gateway=FakeEmailDeliveryGateway())
    operation = center.enqueue(_request())

    processed = center.process_next()

    assert processed is not None
    assert processed.operation_id == operation.operation_id
    assert processed.status == EmailOperationStatus.SENT
    assert processed.provider_message_id == "fake-REQSYS-EMAIL-OPS-TEST-001-1"
    assert center.metrics().sent == 1
    assert center.metrics().queued == 0

    statuses = [event.status for event in center.timeline(operation.operation_id)]
    assert statuses == [
        EmailOperationStatus.QUEUED,
        EmailOperationStatus.PROCESSING,
        EmailOperationStatus.SENT,
    ]


def test_process_next_agenda_retry_quando_falha_antes_do_limite():
    center = EmailOperationsCenter(gateway=FakeEmailDeliveryGateway(fail_times=1))
    operation = center.enqueue(_request(max_attempts=3))

    processed = center.process_next()

    assert processed is not None
    assert processed.status == EmailOperationStatus.RETRY_SCHEDULED
    assert processed.attempts == 1
    assert processed.last_error == "simulated delivery failure"
    assert center.metrics().retry_scheduled == 1

    last_event = center.timeline(operation.operation_id)[-1]
    assert last_event.status == EmailOperationStatus.RETRY_SCHEDULED
    assert last_event.severity == EmailOperationSeverity.WARNING


def test_process_next_move_para_dlq_apos_esgotar_tentativas():
    center = EmailOperationsCenter(gateway=FakeEmailDeliveryGateway(fail_times=5))
    operation = center.enqueue(_request(max_attempts=2))

    first = center.process_next()
    second = center.process_next()

    assert first is not None
    assert second is not None
    assert first.status == EmailOperationStatus.DEAD_LETTER
    assert second.status == EmailOperationStatus.DEAD_LETTER
    assert second.attempts == 2
    assert center.metrics().dead_letter == 1
    assert center.dead_letters()[0].operation_id == operation.operation_id

    last_event = center.timeline(operation.operation_id)[-1]
    assert last_event.status == EmailOperationStatus.DEAD_LETTER
    assert last_event.severity == EmailOperationSeverity.CRITICAL


def test_replay_dead_letter_recoloca_operacao_para_processamento():
    center = EmailOperationsCenter(gateway=FakeEmailDeliveryGateway(fail_times=1))
    operation = center.enqueue(_request(max_attempts=1))
    processed = center.process_next()

    assert processed is not None
    assert processed.status == EmailOperationStatus.DEAD_LETTER

    replayed = center.replay_dead_letter(operation.operation_id)

    assert replayed.status == EmailOperationStatus.REPLAYED
    assert replayed.last_error is None
    assert center.metrics().replayed == 1

    last_event = center.timeline(operation.operation_id)[-1]
    assert last_event.status == EmailOperationStatus.REPLAYED
    assert last_event.severity == EmailOperationSeverity.WARNING


def test_replay_rejeita_operacao_que_nao_esta_na_dlq():
    center = EmailOperationsCenter(gateway=FakeEmailDeliveryGateway())
    operation = center.enqueue(_request())

    with pytest.raises(ValueError, match="only dead-letter operations can be replayed"):
        center.replay_dead_letter(operation.operation_id)


def test_request_validation_exige_campos_minimos():
    request = EmailDeliveryRequest(
        subject=" ",
        recipients=(),
        correlation_id=" ",
        html_body="",
        text_body="",
        max_attempts=0,
    )
    center = EmailOperationsCenter(gateway=FakeEmailDeliveryGateway())

    with pytest.raises(ValueError, match="subject is required"):
        center.enqueue(request)
