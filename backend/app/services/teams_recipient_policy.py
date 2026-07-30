from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.teams_notification_recipient import TeamsNotificationRecipient
from app.schemas.teams_recipient_policy import (
    TeamsNotificationRecipientCreate,
    TeamsNotificationRecipientUpdate,
    TeamsRecipientPolicyMessageRequest,
)
from app.services.teams_gateway import enviar_mensagem_gateway


def listar_destinatarios(
    db: Session,
    politica: str | None = None,
    *,
    apenas_ativos: bool = False,
) -> list[TeamsNotificationRecipient]:
    stmt = select(TeamsNotificationRecipient)
    if politica:
        stmt = stmt.where(TeamsNotificationRecipient.politica == politica.lower())
    if apenas_ativos:
        stmt = stmt.where(TeamsNotificationRecipient.ativo.is_(True))
    stmt = stmt.order_by(
        TeamsNotificationRecipient.politica.asc(),
        TeamsNotificationRecipient.prioridade.asc(),
        TeamsNotificationRecipient.id.asc(),
    )
    return list(db.execute(stmt).scalars().all())


def criar_destinatario(
    db: Session,
    payload: TeamsNotificationRecipientCreate,
) -> TeamsNotificationRecipient:
    item = TeamsNotificationRecipient(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def atualizar_destinatario(
    db: Session,
    recipient_id: int,
    payload: TeamsNotificationRecipientUpdate,
) -> TeamsNotificationRecipient:
    item = db.get(TeamsNotificationRecipient, recipient_id)
    if item is None:
        raise ValueError(f'destinatario Teams nao encontrado: {recipient_id}')
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(item, campo, valor)
    db.commit()
    db.refresh(item)
    return item


def remover_destinatario(db: Session, recipient_id: int) -> None:
    item = db.get(TeamsNotificationRecipient, recipient_id)
    if item is None:
        raise ValueError(f'destinatario Teams nao encontrado: {recipient_id}')
    db.delete(item)
    db.commit()


def _resultado_resumido(
    item: TeamsNotificationRecipient,
    resultado: dict[str, Any],
) -> dict[str, Any]:
    return {
        'recipient_id': item.id,
        'nome': item.nome,
        'destino_tipo': item.destino_tipo,
        'entregue': bool(resultado.get('entregue')),
        'canal_usado': resultado.get('canal_usado'),
        'correlation_id': resultado.get('correlation_id'),
        'erro': resultado.get('erro'),
        'motivo': resultado.get('motivo'),
    }


async def enviar_mensagem_por_politica(
    politica: str,
    request: TeamsRecipientPolicyMessageRequest,
    *,
    db: Session,
    correlation_id: str,
) -> dict[str, Any]:
    politica_normalizada = politica.strip().lower()
    destinatarios = listar_destinatarios(db, politica_normalizada, apenas_ativos=True)

    # Compatibilidade de transicao: o secret existente pode continuar sendo
    # fornecido como destino explicito, mas deixa de ser a fonte primaria.
    if not destinatarios and request.destino_id:
        resultado = await enviar_mensagem_gateway(request, db=db, correlation_id=correlation_id)
        provider = dict(resultado.get('provider_response') or {})
        provider.update(
            {
                'recipient_policy': politica_normalizada,
                'delivery_mode': request.delivery_mode,
                'resolution': 'explicit_destination_fallback',
            }
        )
        resultado['provider_response'] = provider
        resultado['fallback_usado'] = True
        return resultado

    if not destinatarios:
        return {
            'entregue': False,
            'canal_usado': 'recipient_policy',
            'destino_tipo': 'policy',
            'correlation_id': correlation_id,
            'dry_run': request.dry_run,
            'fallback_usado': False,
            'message_id': None,
            'chat_id': None,
            'status_code': None,
            'erro': f'Nenhum destinatario ativo configurado para a politica {politica_normalizada}.',
            'motivo': 'recipient_policy_without_recipients',
            'provider_response': {
                'recipient_policy': politica_normalizada,
                'delivery_mode': request.delivery_mode,
                'configured': 0,
                'attempted': 0,
                'delivered': 0,
                'failed': 0,
                'results': [],
            },
        }

    selecionados = destinatarios
    if request.delivery_mode == 'channel':
        canais = [item for item in destinatarios if item.destino_tipo in ('canal', 'webhook')]
        selecionados = (canais or destinatarios)[:1]

    resultados: list[dict[str, Any]] = []
    entregues = 0

    for item in selecionados:
        request_individual = request.model_copy(
            update={
                'destino_id': item.destino_id,
                'destino_tipo': item.destino_tipo,
            }
        )
        resultado = await enviar_mensagem_gateway(
            request_individual,
            db=db,
            correlation_id=f'{correlation_id}:{item.id}',
        )
        resultados.append(_resultado_resumido(item, resultado))
        if resultado.get('entregue'):
            entregues += 1
            if request.delivery_mode == 'first_success':
                break

    tentados = len(resultados)
    falhas = tentados - entregues
    parcial = entregues > 0 and falhas > 0

    return {
        'entregue': entregues > 0,
        'canal_usado': 'recipient_policy',
        'destino_tipo': 'policy',
        'correlation_id': correlation_id,
        'dry_run': request.dry_run,
        'fallback_usado': False,
        'message_id': None,
        'chat_id': None,
        'status_code': 207 if parcial else (200 if entregues else None),
        'erro': None if entregues else 'Nenhuma notificacao foi entregue.',
        'motivo': 'recipient_policy_partial' if parcial else ('recipient_policy_delivered' if entregues else 'recipient_policy_failed'),
        'provider_response': {
            'recipient_policy': politica_normalizada,
            'delivery_mode': request.delivery_mode,
            'configured': len(destinatarios),
            'attempted': tentados,
            'delivered': entregues,
            'failed': falhas,
            'results': resultados,
        },
    }
