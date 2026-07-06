"""Publicação governada de eventos do workflow de requisitos.

Este adaptador mantém a integração com o Runtime Core desacoplada da API.
A API pode publicar eventos de domínio sem conhecer detalhes de handlers,
retry ou dead letter queue.
"""

from __future__ import annotations

from typing import Any

from app.services.runtime_core import (
    RuntimeDeliveryResult,
    RuntimeEventBus,
    RuntimeEventEnvelope,
)

EVENTO_REQUISITO_TRANSICIONADO = 'REQUISITO_TRANSICIONADO'
SOURCE_WORKFLOW_REQUISITOS = 'api.requisitos.workflow'

_runtime_bus = RuntimeEventBus()


def obter_runtime_bus_requisitos() -> RuntimeEventBus:
    """Retorna o barramento singleton do workflow de requisitos.

    A implementação atual é in-memory para baixo risco. A função isola o ponto de
    evolução futura para outbox SQL, fila corporativa ou broker externo.
    """

    return _runtime_bus


def publicar_requisito_transicionado(
    *,
    requisito_id: int | str,
    requisito_codigo: str,
    origem: str,
    destino: str,
    usuario: str,
    motivo: str | None,
    evidencia_informada: bool,
    score_prontidao: int,
    correlation_id: str | None,
) -> list[RuntimeDeliveryResult]:
    """Publica evento técnico de transição sem quebrar o fluxo principal.

    A ausência de handlers retorna status `pending` pelo Runtime Core e não impede
    a transição do requisito. Falhas definitivas de handlers são enviadas para DLQ.
    """

    envelope = RuntimeEventEnvelope(
        event_type=EVENTO_REQUISITO_TRANSICIONADO,
        source=SOURCE_WORKFLOW_REQUISITOS,
        aggregate_type='requisito',
        aggregate_id=str(requisito_id),
        correlation_id=correlation_id or 'sem-correlation-id',
        payload={
            'schema_version': '1.0.0',
            'requisito_codigo': requisito_codigo,
            'origem': origem,
            'destino': destino,
            'usuario': usuario,
            'motivo_informado': bool((motivo or '').strip()),
            'evidencia_informada': evidencia_informada,
            'score_prontidao': score_prontidao,
        },
    )
    return obter_runtime_bus_requisitos().publish(envelope)


def resumir_runtime_requisitos() -> dict[str, Any]:
    """Snapshot operacional mínimo para inspeção e testes de integração futura."""

    bus = obter_runtime_bus_requisitos()
    eventos = bus.published_events()
    dead_letters = bus.dead_letters()
    return {
        'schema_version': '1.0.0',
        'source': SOURCE_WORKFLOW_REQUISITOS,
        'eventos_publicados': len(eventos),
        'dead_letters': len(dead_letters),
        'handlers_registrados': list(bus.pending_event_types()),
        'ultimo_evento': eventos[-1].to_audit_payload() if eventos else None,
        'ultima_dead_letter': {
            'event_id': dead_letters[-1].envelope.event_id,
            'handler_name': dead_letters[-1].handler_name,
            'attempts': dead_letters[-1].attempts,
            'error': dead_letters[-1].error,
            'failed_at': dead_letters[-1].failed_at,
        } if dead_letters else None,
    }
