"""Router shim para publicar eventos Runtime Core na transição de requisitos.

Este módulo adiciona uma rota compatível com o endpoint legado de transição,
posicionada antes da rota original em `requisitos.api_router`.
"""

from __future__ import annotations

import json
import logging

from fastapi import Depends, Header, status
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.schemas.requisito import RequisitoTransicaoCriar
from app.services.auditoria import registrar_evento
from app.services.requisitos_runtime_events import publicar_requisito_transicionado

from . import requisitos

logger = logging.getLogger('reqsys.requisitos.runtime')
_ROUTE_PATH = '/{identificador}/transicao'
_ROUTE_NAME = 'transicionar_requisito_runtime_core'


def transicionar_requisito_runtime_core(
    identificador: str,
    payload: RequisitoTransicaoCriar,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Transiciona requisito e publica evento governado no Runtime Core."""

    requisito = requisitos._buscar_requisito_por_identificador(db, identificador)
    origem, destino = requisitos._validar_transicao(requisito, payload)
    requisito.status = destino
    db.add(requisito)
    db.commit()
    db.refresh(requisito)

    score_prontidao = requisitos._calcular_score_prontidao(requisito)
    evidencia_informada = bool(requisitos._normalizar_texto(payload.evidencia))
    payload_auditoria = {
        'schema_version': '1.0.0',
        'origem': origem,
        'destino': destino,
        'motivo': payload.motivo,
        'evidencia': evidencia_informada,
        'score_prontidao': score_prontidao,
    }
    registrar_evento(
        db,
        x_correlation_id or 'sem-correlation-id',
        payload.usuario,
        'REQUISITO_TRANSICIONADO',
        'requisito',
        requisito.id,
        json.dumps(payload_auditoria, ensure_ascii=False),
    )
    runtime_results = publicar_requisito_transicionado(
        requisito_id=requisito.id,
        requisito_codigo=requisito.codigo,
        origem=origem,
        destino=destino,
        usuario=payload.usuario,
        motivo=payload.motivo,
        evidencia_informada=evidencia_informada,
        score_prontidao=score_prontidao,
        correlation_id=x_correlation_id,
    )
    runtime_event = {
        'schema_version': '1.0.0',
        'event_type': 'REQUISITO_TRANSICIONADO',
        'event_id': runtime_results[0].event_id if runtime_results else None,
        'status': runtime_results[0].status.value if runtime_results else 'unknown',
        'handler_name': runtime_results[0].handler_name if runtime_results else None,
        'attempts': runtime_results[0].attempts if runtime_results else 0,
    }
    logger.info(
        'requisito_transicionado_runtime_core codigo=%s origem=%s destino=%s runtime_status=%s correlation_id=%s',
        requisito.codigo,
        origem,
        destino,
        runtime_event['status'],
        x_correlation_id or 'sem-correlation-id',
    )
    return ok(
        {
            'schema_version': '1.0.0',
            'requisito': requisitos._serializar_power_automate(requisito),
            'workflow': requisitos._montar_workflow_state(requisito),
            'transicao': payload_auditoria,
            'runtime_event': runtime_event,
        },
        x_correlation_id,
        meta={'contract': 'reqsys-requisito-transicao-v1'},
    )


def instalar_runtime_transition_route() -> None:
    """Instala a rota runtime antes da rota legada equivalente."""

    if any(route.name == _ROUTE_NAME for route in requisitos.api_router.routes):
        return

    requisitos.api_router.add_api_route(
        _ROUTE_PATH,
        transicionar_requisito_runtime_core,
        methods=['POST'],
        status_code=status.HTTP_200_OK,
        name=_ROUTE_NAME,
    )
    rota_runtime = requisitos.api_router.routes.pop()
    requisitos.api_router.routes.insert(0, rota_runtime)


instalar_runtime_transition_route()
