from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    call_with_retry_async,
)
from app.schemas.teams_gateway import TeamsGatewayMessageRequest
from app.services.hub_lowcode import (
    criar_chat_e_enviar_como_usuario,
    enviar_mensagem_chat_teams,
    enviar_mensagem_chat_teams_como_usuario,
    obter_planner_webhook_config,
    salvar_log_integracao,
)

logger = logging.getLogger('reqsys.teams_gateway')

_webhook_circuit = CircuitBreaker(name='teams_gateway_webhook', failure_threshold=3, cooldown_seconds=60)
_WEBHOOK_MAX_RETRIES = 3
_WEBHOOK_BACKOFF_SECONDS = 0.5


def reset_teams_gateway_circuit_breakers() -> None:
    _webhook_circuit.reset()


def _correlation_id(correlation_id: str | None = None) -> str:
    return correlation_id or str(uuid.uuid4())


def _webhook_url_configurada(db: Session | None) -> str:
    if db is not None:
        cfg = obter_planner_webhook_config(db)
        url = (cfg.get('teams_webhook_url') or '').strip()
        if url:
            return url
    return settings.teams_notifications_webhook_url.strip()


def _missing_webhook(db: Session | None) -> list[str]:
    return [] if _webhook_url_configurada(db) else ['TEAMS_NOTIFICATIONS_WEBHOOK_URL ou planner.webhook_config.teams_webhook_url']


def status_gateway(db: Session | None = None) -> dict[str, Any]:
    webhook_configurado = bool(_webhook_url_configurada(db))
    graph_delegado_campos = list(settings.azure_missing_fields)
    graph_app_campos = list(settings.teams_graph_missing_fields)

    rotas = [
        {
            'canal': 'graph_delegado',
            'disponivel': settings.azure_configured,
            'recomendado_para': ['chat humano 1:1', 'chat em grupo'],
            'requer_usuario_logado': True,
            'campos_faltantes': graph_delegado_campos,
            'observacao': 'Usa access_token delegado adquirido pelo frontend/MSAL.',
        },
        {
            'canal': 'webhook',
            'disponivel': webhook_configurado,
            'recomendado_para': ['alertas automaticos', 'mensagens em canal', 'eventos operacionais'],
            'requer_usuario_logado': False,
            'campos_faltantes': _missing_webhook(db),
            'observacao': 'Caminho recomendado para automacao backend sem usuario logado.',
        },
        {
            'canal': 'graph_app_only',
            'disponivel': settings.teams_graph_configurado,
            'recomendado_para': ['cenarios onde o app/bot e participante'],
            'requer_usuario_logado': False,
            'campos_faltantes': graph_app_campos,
            'observacao': 'Nao envia para chats humano-humano; Graph bloqueia esse caso.',
        },
        {
            'canal': 'bot',
            'disponivel': False,
            'recomendado_para': ['servico completo sem usuario logado'],
            'requer_usuario_logado': False,
            'campos_faltantes': ['TEAMS_BOT_APP_ID', 'TEAMS_BOT_SECRET', 'Teams App instalado'],
            'observacao': 'Rota futura para Teams App/Bot com instalacao governada.',
        },
    ]

    return {
        'schema_version': '1.0.0',
        'status': 'operacional' if any(r['disponivel'] for r in rotas) else 'pendente_configuracao',
        'rotas': rotas,
        'modo_padrao': 'auto',
        'politica': {
            'chat_humano_sem_usuario_logado': 'bloquear_com_mensagem_explicita',
            'automacao_backend': 'preferir_webhook_ou_bot',
            'fallback': 'webhook quando permitido e configurado',
        },
    }


def _payload_webhook(texto: str, content_type: str, metadata: dict[str, Any]) -> dict[str, Any]:
    subtitle = metadata.get('titulo') or metadata.get('title') or 'ReqSys Teams Gateway'
    content = texto if content_type == 'text' else texto.replace('<br>', '\n')
    return {
        'type': 'message',
        'attachments': [
            {
                'contentType': 'application/vnd.microsoft.card.adaptive',
                'content': {
                    '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
                    'type': 'AdaptiveCard',
                    'version': '1.2',
                    'body': [
                        {'type': 'TextBlock', 'size': 'Medium', 'weight': 'Bolder', 'text': subtitle},
                        {'type': 'TextBlock', 'text': content, 'wrap': True},
                    ],
                },
            }
        ],
    }


async def _enviar_webhook(url: str, texto: str, content_type: str, metadata: dict[str, Any]) -> dict[str, Any]:
    payload = _payload_webhook(texto, content_type, metadata)

    async def _postar() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return {'status_code': resp.status_code}

    return await call_with_retry_async(
        _postar,
        max_retries=_WEBHOOK_MAX_RETRIES,
        backoff_seconds=_WEBHOOK_BACKOFF_SECONDS,
        retry_on=(httpx.TimeoutException, httpx.ConnectError),
        circuit=_webhook_circuit,
    )


def _resultado(
    request: TeamsGatewayMessageRequest,
    correlation_id: str,
    *,
    entregue: bool,
    canal_usado: str | None,
    fallback_usado: bool = False,
    erro: str | None = None,
    motivo: str | None = None,
    provider_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = provider_response or {}
    return {
        'entregue': entregue,
        'canal_usado': canal_usado,
        'destino_tipo': request.destino_tipo,
        'correlation_id': correlation_id,
        'dry_run': request.dry_run,
        'fallback_usado': fallback_usado,
        'message_id': response.get('message_id'),
        'chat_id': response.get('chat_id') or request.destino_id,
        'status_code': response.get('status_code'),
        'erro': erro or response.get('erro'),
        'motivo': motivo,
        'provider_response': {
            key: value
            for key, value in response.items()
            if key not in {'erro', 'correlation_id'} and 'token' not in key.lower()
        },
    }


def _log_gateway(
    db: Session | None,
    request: TeamsGatewayMessageRequest,
    resultado: dict[str, Any],
) -> None:
    if db is None:
        return
    status = 'sucesso' if resultado.get('entregue') else 'erro'
    salvar_log_integracao(
        db,
        tipo='teams_gateway',
        status=status,
        autor=request.autor,
        titulo=f"Teams Gateway via {resultado.get('canal_usado') or 'nenhum'}",
        mensagem=request.texto[:200],
        detalhes={
            'destino_tipo': request.destino_tipo,
            'modo': request.modo,
            'canal_usado': resultado.get('canal_usado'),
            'fallback_usado': resultado.get('fallback_usado'),
            'dry_run': request.dry_run,
            'erro': resultado.get('erro'),
            'metadata': request.metadata,
        },
        correlation_id=resultado['correlation_id'],
    )


def _deve_usar_delegado(request: TeamsGatewayMessageRequest) -> bool:
    if request.modo == 'graph_delegado':
        return True
    return request.modo == 'auto' and request.destino_tipo in ('auto', 'chat', 'chat_1a1') and bool(request.usuario_access_token)


def _deve_usar_webhook(request: TeamsGatewayMessageRequest, db: Session | None) -> bool:
    if request.modo == 'webhook':
        return True
    if request.modo != 'auto':
        return False
    if request.destino_tipo in ('webhook', 'canal'):
        return True
    return request.destino_tipo == 'auto' and bool(request.webhook_url or _webhook_url_configurada(db))


async def enviar_mensagem_gateway(
    request: TeamsGatewayMessageRequest,
    db: Session | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    corr = _correlation_id(correlation_id)

    if request.dry_run:
        canal = selecionar_rota(request, db)['canal']
        result = _resultado(
            request,
            corr,
            entregue=False,
            canal_usado=canal,
            motivo='dry_run: mensagem nao enviada',
            provider_response={'planejado': True},
        )
        _log_gateway(db, request, result)
        return result

    if _deve_usar_delegado(request):
        result = await _enviar_delegado(request, db, corr)
        if result['entregue'] or not request.permitir_fallback:
            _log_gateway(db, request, result)
            return result
        if request.webhook_url or _webhook_url_configurada(db):
            fallback = await _enviar_via_webhook(request, db, corr, fallback_usado=True)
            _log_gateway(db, request, fallback)
            return fallback
        _log_gateway(db, request, result)
        return result

    if _deve_usar_webhook(request, db):
        result = await _enviar_via_webhook(request, db, corr)
        _log_gateway(db, request, result)
        return result

    if request.modo == 'graph_app_only':
        result = await _enviar_graph_app_only(request, db, corr)
        _log_gateway(db, request, result)
        return result

    result = _resultado(
        request,
        corr,
        entregue=False,
        canal_usado=None,
        erro=(
            'Chat humano no Teams exige usuario_access_token delegado. '
            'Para automacao sem usuario logado, configure webhook ou bot.'
        ),
        motivo='sem_rota_segura',
    )
    _log_gateway(db, request, result)
    return result


def selecionar_rota(request: TeamsGatewayMessageRequest, db: Session | None = None) -> dict[str, Any]:
    if _deve_usar_delegado(request):
        return {'canal': 'graph_delegado', 'motivo': 'token delegado presente ou modo explicito'}
    if _deve_usar_webhook(request, db):
        return {'canal': 'webhook', 'motivo': 'destino operacional sem necessidade de usuario logado'}
    if request.modo == 'graph_app_only':
        return {'canal': 'graph_app_only', 'motivo': 'modo explicito; nao recomendado para chat humano'}
    if request.modo == 'bot':
        return {'canal': 'bot', 'motivo': 'rota futura ainda nao implementada'}
    return {'canal': None, 'motivo': 'nenhuma rota disponivel'}


async def _enviar_delegado(
    request: TeamsGatewayMessageRequest,
    db: Session | None,
    correlation_id: str,
) -> dict[str, Any]:
    if not request.usuario_access_token:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='graph_delegado',
            erro='usuario_access_token e obrigatorio para graph_delegado',
        )

    if request.destino_tipo == 'chat_1a1':
        if not request.usuario_a_aad_object_id or not request.usuario_b_aad_object_id:
            return _resultado(
                request,
                correlation_id,
                entregue=False,
                canal_usado='graph_delegado',
                erro='usuario_a_aad_object_id e usuario_b_aad_object_id sao obrigatorios para chat_1a1',
            )
        provider = await criar_chat_e_enviar_como_usuario(
            request.usuario_a_aad_object_id,
            request.usuario_b_aad_object_id,
            request.texto,
            request.usuario_access_token,
            content_type=request.content_type,
            db=db,
            autor=request.autor,
            correlation_id=correlation_id,
        )
    else:
        if not request.destino_id:
            return _resultado(
                request,
                correlation_id,
                entregue=False,
                canal_usado='graph_delegado',
                erro='destino_id/chat_id e obrigatorio para envio delegado',
            )
        provider = await enviar_mensagem_chat_teams_como_usuario(
            request.destino_id,
            request.texto,
            request.usuario_access_token,
            content_type=request.content_type,
            db=db,
            autor=request.autor,
            correlation_id=correlation_id,
        )

    return _resultado(
        request,
        correlation_id,
        entregue=bool(provider.get('enviado')),
        canal_usado='graph_delegado',
        erro=provider.get('erro'),
        provider_response=provider,
    )


async def _enviar_graph_app_only(
    request: TeamsGatewayMessageRequest,
    db: Session | None,
    correlation_id: str,
) -> dict[str, Any]:
    if not request.destino_id:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='graph_app_only',
            erro='destino_id/chat_id e obrigatorio para graph_app_only',
        )
    provider = await enviar_mensagem_chat_teams(
        request.destino_id,
        request.texto,
        content_type=request.content_type,
        db=db,
        autor=request.autor,
        correlation_id=correlation_id,
    )
    return _resultado(
        request,
        correlation_id,
        entregue=bool(provider.get('enviado')),
        canal_usado='graph_app_only',
        erro=provider.get('erro'),
        provider_response=provider,
    )


async def _enviar_via_webhook(
    request: TeamsGatewayMessageRequest,
    db: Session | None,
    correlation_id: str,
    fallback_usado: bool = False,
) -> dict[str, Any]:
    url = request.webhook_url or _webhook_url_configurada(db)
    if not url:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='webhook',
            fallback_usado=fallback_usado,
            erro='Webhook Teams nao configurado',
        )

    try:
        provider = await _enviar_webhook(url, request.texto, request.content_type, request.metadata)
        return _resultado(
            request,
            correlation_id,
            entregue=True,
            canal_usado='webhook',
            fallback_usado=fallback_usado,
            provider_response=provider,
        )
    except CircuitBreakerOpenError as exc:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='webhook',
            fallback_usado=fallback_usado,
            erro=str(exc),
        )
    except httpx.HTTPStatusError as exc:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='webhook',
            fallback_usado=fallback_usado,
            erro=f'HTTP {exc.response.status_code}: {exc.response.text[:300]}',
        )
    except Exception as exc:
        logger.warning('teams_gateway_webhook_error correlation_id=%s error=%s', correlation_id, exc)
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='webhook',
            fallback_usado=fallback_usado,
            erro=str(exc),
        )
