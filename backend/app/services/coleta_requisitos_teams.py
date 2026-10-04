"""Acompanhamento Teams da coleta governada de requisitos.

O módulo apenas produz eventos sanitizados para a fila central já existente.
Nenhum texto funcional da necessidade é duplicado em metadata/logs e falhas de
mensageria nunca bloqueiam a geração do requisito.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.teams_notification_queue import TeamsNotificationQueueItem
from app.schemas.teams_notifications import TeamsNotificationEnqueueRequest
from app.services.teams_gateway import status_gateway
from app.services.teams_notifications import criar_item_fila, executar_item_fila

logger = logging.getLogger('reqsys.requisitos.coleta_teams')

TIPO_EVENTO_REFINAMENTO = 'coleta_requisito_refinamento'
TIPO_EVENTO_GERADO = 'coleta_requisito_gerado'

_AMBIENTES_SEM_ENVIO_EXTERNO = {'test', 'testing', 'ci'}


def _hash_deduplicacao(hash_idempotencia: str, tipo_evento: str) -> str:
    material = f'coleta-requisitos:{hash_idempotencia}:{tipo_evento}'
    return hashlib.sha256(material.encode('utf-8')).hexdigest()


def _buscar_existente(
    db: Session,
    *,
    tipo_evento: str,
    hash_deduplicacao: str,
) -> TeamsNotificationQueueItem | None:
    return (
        db.query(TeamsNotificationQueueItem)
        .filter(
            TeamsNotificationQueueItem.origem == 'requisitos',
            TeamsNotificationQueueItem.tipo_evento == tipo_evento,
            TeamsNotificationQueueItem.metadata_json.contains(hash_deduplicacao),
        )
        .order_by(TeamsNotificationQueueItem.id_evento.asc())
        .first()
    )


def _webhook_operacional(db: Session) -> bool:
    ambiente = (settings.app_environment or '').strip().lower()
    if ambiente in _AMBIENTES_SEM_ENVIO_EXTERNO:
        return False

    try:
        status = status_gateway(db)
    except Exception:
        logger.exception('coleta_teams_status_gateway_indisponivel')
        return False

    for rota in status.get('rotas') or []:
        if rota.get('canal') == 'webhook' and rota.get('disponivel') is True:
            return True
    return False


def _url_reqsys(path: str) -> str:
    base = (settings.app_public_url or '').strip().rstrip('/')
    return f'{base}{path}' if base else path


def _resumo_item(item: TeamsNotificationQueueItem, *, deduplicado: bool) -> dict[str, Any]:
    return {
        'id_evento': item.id_evento,
        'tipo_evento': item.tipo_evento,
        'status_evento': item.status_evento,
        'canal_usado': item.canal_usado,
        'status_http': item.status_http,
        'tentativas': item.tentativas,
        'correlation_id': item.correlation_id,
        'deduplicado': deduplicado,
    }


def _payload_notificacao(
    *,
    tipo_evento: str,
    payload,
    avaliacao,
    hash_idempotencia: str,
    payload_hash: str,
    correlation_id: str,
    requisito=None,
) -> TeamsNotificationEnqueueRequest:
    hash_deduplicacao = _hash_deduplicacao(hash_idempotencia, tipo_evento)

    if tipo_evento == TIPO_EVENTO_REFINAMENTO:
        titulo = 'Coleta de requisito requer refinamento'
        texto = (
            'Uma coleta governada ainda não atingiu o nível mínimo para gerar o requisito.\n\n'
            f'Pontuação: {avaliacao.pontuacao}/100\n'
            f'Classificação: {avaliacao.classificacao}\n'
            f'Pendências: {len(avaliacao.pendencias)}\n'
            f'Origem: {payload.origem}\n'
            f'Correlação: {correlation_id}'
        )
        view_url = _url_reqsys('/requisitos/coleta')
    else:
        codigo = getattr(requisito, 'codigo', None) or 'não informado'
        titulo = 'Requisito gerado pela coleta governada'
        texto = (
            'Uma coleta governada atingiu o gate de qualidade e gerou um requisito.\n\n'
            f'Requisito: {codigo}\n'
            f'Pontuação: {avaliacao.pontuacao}/100\n'
            f'Classificação: {avaliacao.classificacao}\n'
            f'Origem: {payload.origem}\n'
            f'Correlação: {correlation_id}'
        )
        view_url = _url_reqsys('/requisitos')

    return TeamsNotificationEnqueueRequest(
        origem='requisitos',
        tipo_evento=tipo_evento,
        ambiente=(settings.app_environment or 'unknown')[:40],
        correlation_id=correlation_id,
        titulo=titulo,
        texto=texto,
        content_type='text',
        autor='reqsys-coleta-requisitos',
        metadata={
            'schema_version': '1.0.0',
            'origem_funcional': 'coleta_requisitos',
            'notification_type': tipo_evento,
            'dedupe_key_hash': hash_deduplicacao,
            'chave_idempotencia_hash': hash_idempotencia,
            'payload_hash': payload_hash,
            'pontuacao': avaliacao.pontuacao,
            'classificacao': avaliacao.classificacao,
            'pendencias_total': len(avaliacao.pendencias),
            'origem_coleta': payload.origem,
            'requisito_codigo': getattr(requisito, 'codigo', None),
            'view_url': view_url,
        },
        destino_tipo='canal',
        modo='webhook',
        permitir_fallback=False,
        dry_run=False,
        enviar_agora=True,
        max_tentativas=3,
    )


async def notificar_acompanhamento_coleta(
    db: Session,
    *,
    tipo_evento: str,
    payload,
    avaliacao,
    hash_idempotencia: str,
    payload_hash: str,
    correlation_id: str,
    requisito=None,
) -> dict[str, Any]:
    """Enfileira e, quando há webhook governado, tenta entregar imediatamente.

    Deduplicação é por coleta + tipo de evento. Assim, pré-visualizar e depois
    tentar gerar a mesma coleta em refinamento não cria duas mensagens.
    """

    if tipo_evento not in {TIPO_EVENTO_REFINAMENTO, TIPO_EVENTO_GERADO}:
        raise ValueError(f'Tipo de acompanhamento Teams inválido: {tipo_evento}')

    hash_deduplicacao = _hash_deduplicacao(hash_idempotencia, tipo_evento)
    existente = _buscar_existente(
        db,
        tipo_evento=tipo_evento,
        hash_deduplicacao=hash_deduplicacao,
    )
    if existente is not None:
        return _resumo_item(existente, deduplicado=True)

    try:
        item = criar_item_fila(
            db,
            _payload_notificacao(
                tipo_evento=tipo_evento,
                payload=payload,
                avaliacao=avaliacao,
                hash_idempotencia=hash_idempotencia,
                payload_hash=payload_hash,
                correlation_id=correlation_id,
                requisito=requisito,
            ),
        )

        if _webhook_operacional(db):
            item = await executar_item_fila(db, item)

        return _resumo_item(item, deduplicado=False)
    except Exception as exc:
        db.rollback()
        logger.exception(
            'coleta_teams_acompanhamento_falhou tipo=%s correlation_id=%s',
            tipo_evento,
            correlation_id,
        )
        return {
            'id_evento': None,
            'tipo_evento': tipo_evento,
            'status_evento': 'FALHA_INTERNA',
            'canal_usado': None,
            'status_http': None,
            'tentativas': 0,
            'correlation_id': correlation_id,
            'deduplicado': False,
            'erro': type(exc).__name__,
        }
