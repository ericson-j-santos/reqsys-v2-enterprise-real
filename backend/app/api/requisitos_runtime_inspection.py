"""Inspeção operacional do Runtime Core para requisitos.

Expõe snapshot controlado do barramento de eventos de requisitos sem alterar o
contrato de criação, consulta ou transição de requisitos.
"""

from __future__ import annotations

import logging

from fastapi import Header

from app.core.envelope import ok
from app.services.requisitos_runtime_events import resumir_runtime_requisitos

from . import requisitos

logger = logging.getLogger('reqsys.requisitos.runtime.inspection')
_ROUTE_PATH = '/runtime/inspection'
_ROUTE_NAME = 'inspecionar_runtime_requisitos'


def inspecionar_runtime_requisitos(x_correlation_id: str | None = Header(default=None)):
    """Retorna snapshot operacional do Runtime Core de requisitos."""

    resumo = resumir_runtime_requisitos()
    payload = {
        'schema_version': '1.0.0',
        'runtime': resumo,
        'health': {
            'status': 'healthy' if resumo.get('dead_letters', 0) == 0 else 'degraded',
            'eventos_publicados': resumo.get('eventos_publicados', 0),
            'dead_letters': resumo.get('dead_letters', 0),
            'handlers_registrados': len(resumo.get('handlers_registrados', [])),
        },
    }
    logger.info(
        'runtime_requisitos_inspecionado status=%s eventos=%s dead_letters=%s correlation_id=%s',
        payload['health']['status'],
        payload['health']['eventos_publicados'],
        payload['health']['dead_letters'],
        x_correlation_id or 'sem-correlation-id',
    )
    return ok(
        payload,
        x_correlation_id,
        meta={'contract': 'reqsys-requisitos-runtime-inspection-v1'},
    )


def instalar_runtime_inspection_route() -> None:
    """Instala rota GET de inspeção operacional sem duplicidade."""

    if any(route.name == _ROUTE_NAME for route in requisitos.api_router.routes):
        return

    requisitos.api_router.add_api_route(
        _ROUTE_PATH,
        inspecionar_runtime_requisitos,
        methods=['GET'],
        name=_ROUTE_NAME,
    )


instalar_runtime_inspection_route()
