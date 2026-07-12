from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    call_with_retry_async,
)
from app.models.bot_conversa_referencia import BotConversaReferencia
from app.models.teams_flow_bot_owner import TeamsFlowBotOwner
from app.schemas.teams_gateway import (
    TeamsFlowBotOwnerCreate,
    TeamsFlowBotOwnerUpdate,
    TeamsGatewayMessageRequest,
)
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

_bot_circuit = CircuitBreaker(name='teams_gateway_bot', failure_threshold=3, cooldown_seconds=60)
_BOT_MAX_RETRIES = 3
_BOT_BACKOFF_SECONDS = 0.5
_BOT_FRAMEWORK_TOKEN_URL = 'https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token'
_BOT_FRAMEWORK_JWKS_URL = 'https://login.botframework.com/v1/.well-known/keys'
_BOT_FRAMEWORK_ISSUER = 'https://api.botframework.com'

_bot_jwks_client: PyJWKClient | None = None

_FLOW_BOT_MAX_RETRIES = 3
_FLOW_BOT_BACKOFF_SECONDS = 0.5
_flow_bot_circuits: dict[str, CircuitBreaker] = {}


def _flow_bot_circuit_do_dono(owner_email: str) -> CircuitBreaker:
    circuit = _flow_bot_circuits.get(owner_email)
    if circuit is None:
        circuit = CircuitBreaker(name=f'teams_gateway_flow_bot:{owner_email}', failure_threshold=3, cooldown_seconds=60)
        _flow_bot_circuits[owner_email] = circuit
    return circuit


def reset_teams_gateway_circuit_breakers() -> None:
    _webhook_circuit.reset()
    _bot_circuit.reset()
    for circuit in _flow_bot_circuits.values():
        circuit.reset()


def _correlation_id(correlation_id: str | None = None) -> str:
    return correlation_id or str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Donos/backups do canal flow_bot (Power Automate "Chat with Flow bot")
# ---------------------------------------------------------------------------

def listar_flow_bot_owners(db: Session, apenas_ativos: bool = False) -> list[TeamsFlowBotOwner]:
    stmt = select(TeamsFlowBotOwner).order_by(TeamsFlowBotOwner.prioridade.asc(), TeamsFlowBotOwner.id.asc())
    if apenas_ativos:
        stmt = stmt.where(TeamsFlowBotOwner.ativo.is_(True))
    return list(db.execute(stmt).scalars().all())


def criar_flow_bot_owner(db: Session, payload: TeamsFlowBotOwnerCreate) -> TeamsFlowBotOwner:
    item = TeamsFlowBotOwner(
        owner_email=payload.owner_email,
        webhook_url=payload.webhook_url,
        prioridade=payload.prioridade,
        ativo=payload.ativo,
        observacao=payload.observacao,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def atualizar_flow_bot_owner(db: Session, owner_id: int, payload: TeamsFlowBotOwnerUpdate) -> TeamsFlowBotOwner:
    item = db.get(TeamsFlowBotOwner, owner_id)
    if item is None:
        raise ValueError(f'flow_bot owner nao encontrado: {owner_id}')
    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(item, campo, valor)
    db.commit()
    db.refresh(item)
    return item


def remover_flow_bot_owner(db: Session, owner_id: int) -> None:
    item = db.get(TeamsFlowBotOwner, owner_id)
    if item is None:
        raise ValueError(f'flow_bot owner nao encontrado: {owner_id}')
    db.delete(item)
    db.commit()


def _flow_bot_alvos(db: Session | None) -> list[tuple[str, str]]:
    """Retorna [(owner_email, webhook_url), ...] ordenados por prioridade.

    Prefere os donos cadastrados no banco (editaveis em runtime); cai para
    TEAMS_FLOW_BOT_WEBHOOK_URL do .env apenas quando nenhum dono ativo existe
    (setup de um unico dono, sem redundancia).
    """
    if db is not None:
        owners = listar_flow_bot_owners(db, apenas_ativos=True)
        if owners:
            return [(o.owner_email, o.webhook_url) for o in owners]
    if settings.teams_flow_bot_webhook_url.strip():
        return [('env:TEAMS_FLOW_BOT_WEBHOOK_URL', settings.teams_flow_bot_webhook_url.strip())]
    return []


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
            'disponivel': settings.teams_bot_configurado,
            'recomendado_para': ['servico completo sem usuario logado', 'chat humano 1:1 apos instalacao do bot'],
            'requer_usuario_logado': False,
            'campos_faltantes': list(settings.teams_bot_missing_fields),
            'observacao': (
                'Exige Azure Bot registrado (Bot Framework) e conversationReference '
                'salva (bot instalado/mencionado ao menos uma vez pelo usuario-alvo) '
                'antes do primeiro envio proativo.'
            ),
        },
        {
            'canal': 'flow_bot',
            'disponivel': bool(_flow_bot_alvos(db)),
            'recomendado_para': ['chat humano 1:1 sem usuario logado, sem Azure Bot Service'],
            'requer_usuario_logado': False,
            'campos_faltantes': [] if _flow_bot_alvos(db) else ['TEAMS_FLOW_BOT_WEBHOOK_URL ou ao menos 1 flow_bot_owner ativo'],
            'donos_ativos': len(_flow_bot_alvos(db)),
            'observacao': (
                'Usa o webhook de um flow do Power Automate ("Post a message in a '
                'chat or channel", Post as: Flow bot, Post in: Chat with Flow bot). '
                'Nao exige Azure Bot Service/assinatura Azure; mensagem chega com o '
                'remetente "Workflows", nao com identidade propria do ReqSys.'
            ),
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
            'provider_response': resultado.get('provider_response') or {},
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


def _deve_usar_bot(request: TeamsGatewayMessageRequest) -> bool:
    if request.modo == 'bot':
        return True
    return (
        request.modo == 'auto'
        and request.destino_tipo in ('auto', 'chat', 'chat_1a1')
        and not request.usuario_access_token
        and settings.teams_bot_configurado
    )


def _deve_usar_flow_bot(request: TeamsGatewayMessageRequest, db: Session | None = None) -> bool:
    if request.modo == 'flow_bot':
        return True
    return (
        request.modo == 'auto'
        and request.destino_tipo in ('auto', 'chat', 'chat_1a1')
        and not request.usuario_access_token
        and not settings.teams_bot_configurado
        and bool(_flow_bot_alvos(db))
    )


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

    if _deve_usar_bot(request):
        result = await _enviar_bot(request, db, corr)
        if result['entregue'] or not request.permitir_fallback:
            _log_gateway(db, request, result)
            return result
        if request.webhook_url or _webhook_url_configurada(db):
            fallback = await _enviar_via_webhook(request, db, corr, fallback_usado=True)
            _log_gateway(db, request, fallback)
            return fallback
        _log_gateway(db, request, result)
        return result

    if _deve_usar_flow_bot(request, db):
        result = await _enviar_flow_bot(request, db, corr)
        if result['entregue'] or not request.permitir_fallback:
            _log_gateway(db, request, result)
            return result
        if request.webhook_url or _webhook_url_configurada(db):
            fallback = await _enviar_via_webhook(request, db, corr, fallback_usado=True)
            _log_gateway(db, request, fallback)
            return fallback
        _log_gateway(db, request, result)
        return result

    result = _resultado(
        request,
        corr,
        entregue=False,
        canal_usado=None,
        erro=(
            'Chat humano no Teams exige usuario_access_token delegado, bot instalado '
            'ou flow_bot configurado. Para automacao sem usuario logado, configure '
            'webhook, bot ou flow_bot.'
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
    if _deve_usar_bot(request):
        motivo = 'modo explicito' if request.modo == 'bot' else 'sem token delegado; bot configurado para chat humano'
        return {'canal': 'bot', 'motivo': motivo}
    if _deve_usar_flow_bot(request, db):
        motivo = 'modo explicito' if request.modo == 'flow_bot' else 'sem token delegado e sem bot; flow_bot configurado para chat humano'
        return {'canal': 'flow_bot', 'motivo': motivo}
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


# ---------------------------------------------------------------------------
# Canal "bot" (Azure Bot Service / Bot Framework Connector API)
# ---------------------------------------------------------------------------

def obter_conversa_referencia_bot(db: Session, usuario_aad_object_id: str) -> BotConversaReferencia | None:
    return db.execute(
        select(BotConversaReferencia).where(
            BotConversaReferencia.usuario_aad_object_id == usuario_aad_object_id,
            BotConversaReferencia.channel_id == 'msteams',
        )
    ).scalar_one_or_none()


def salvar_conversa_referencia_bot(
    db: Session,
    usuario_aad_object_id: str,
    service_url: str,
    conversation_id: str,
    bot_id: str = '',
    tenant_id: str = '',
    channel_id: str = 'msteams',
) -> BotConversaReferencia:
    existing = db.execute(
        select(BotConversaReferencia).where(
            BotConversaReferencia.usuario_aad_object_id == usuario_aad_object_id,
            BotConversaReferencia.channel_id == channel_id,
        )
    ).scalar_one_or_none()
    item = existing or BotConversaReferencia(usuario_aad_object_id=usuario_aad_object_id, channel_id=channel_id)
    item.service_url = service_url
    item.conversation_id = conversation_id
    item.bot_id = bot_id
    item.tenant_id = tenant_id
    if not existing:
        db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _obter_jwks_client() -> PyJWKClient:
    global _bot_jwks_client
    if _bot_jwks_client is None:
        _bot_jwks_client = PyJWKClient(_BOT_FRAMEWORK_JWKS_URL)
    return _bot_jwks_client


def validar_jwt_bot_framework(token: str) -> dict[str, Any]:
    """Valida o JWT assinado enviado pelo Bot Framework no header Authorization.

    Levanta jwt.PyJWTError (ou subclasse) quando o token e invalido/expirado/
    de outro emissor. Depende de rede (busca a JWKS publica do Bot Framework)
    — em testes, esta funcao e mockada no ponto de chamada.
    """
    jwks_client = _obter_jwks_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=['RS256'],
        audience=settings.teams_bot_app_id,
        issuer=_BOT_FRAMEWORK_ISSUER,
    )


async def _token_bot_framework() -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            _BOT_FRAMEWORK_TOKEN_URL,
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.teams_bot_app_id,
                'client_secret': settings.teams_bot_secret,
                'scope': 'https://api.botframework.com/.default',
            },
        )
        resp.raise_for_status()
        return resp.json()['access_token']


async def _enviar_atividade_bot_framework(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    async def _postar() -> dict[str, Any]:
        token = await _token_bot_framework()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload, headers={'Authorization': f'Bearer {token}'})
            resp.raise_for_status()
            return resp.json()

    return await call_with_retry_async(
        _postar,
        max_retries=_BOT_MAX_RETRIES,
        backoff_seconds=_BOT_BACKOFF_SECONDS,
        retry_on=(httpx.TimeoutException, httpx.ConnectError),
        circuit=_bot_circuit,
    )


async def _enviar_bot(
    request: TeamsGatewayMessageRequest,
    db: Session | None,
    correlation_id: str,
) -> dict[str, Any]:
    if not settings.teams_bot_configurado:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='bot',
            erro='Bot do Teams nao configurado: ' + ', '.join(settings.teams_bot_missing_fields),
        )
    if not request.destino_id:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='bot',
            erro='destino_id (AAD object id do usuario-alvo) e obrigatorio para o canal bot',
        )
    if db is None:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='bot',
            erro='Sessao de banco de dados e obrigatoria para o canal bot',
        )

    referencia = obter_conversa_referencia_bot(db, request.destino_id)
    if referencia is None:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='bot',
            erro=(
                'Bot ainda nao foi instalado/nao recebeu nenhuma mensagem deste usuario; '
                'nao ha conversationReference salva para enviar proativamente.'
            ),
            motivo='conversa_bot_nao_instalada',
        )

    text_format = 'xml' if request.content_type == 'html' else 'plain'
    url = f"{referencia.service_url.rstrip('/')}/v3/conversations/{referencia.conversation_id}/activities"
    payload = {
        'type': 'message',
        'from': {'id': settings.teams_bot_app_id},
        'conversation': {'id': referencia.conversation_id},
        'text': request.texto,
        'textFormat': text_format,
    }

    try:
        provider = await _enviar_atividade_bot_framework(url, payload)
        return _resultado(
            request,
            correlation_id,
            entregue=True,
            canal_usado='bot',
            provider_response={'message_id': provider.get('id'), 'chat_id': referencia.conversation_id},
        )
    except CircuitBreakerOpenError as exc:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='bot',
            erro=str(exc),
        )
    except httpx.HTTPStatusError as exc:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='bot',
            erro=f'HTTP {exc.response.status_code}: {exc.response.text[:300]}',
        )
    except Exception as exc:
        logger.warning('teams_gateway_bot_error correlation_id=%s error=%s', correlation_id, exc)
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='bot',
            erro=str(exc),
        )


# ---------------------------------------------------------------------------
# Canal "flow_bot" (Power Automate — Post as: Flow bot, Post in: Chat with Flow bot)
# ---------------------------------------------------------------------------

def _payload_flow_bot(destinatario: str, texto: str, metadata: dict[str, Any], correlation_id: str) -> dict[str, Any]:
    """Payload no schema real validado ao vivo contra um flow de producao existente
    no tenant (`robo_envia_teams`, 2026-07-09) — nao e um schema inventado. Campos
    obrigatorios no flow original: to, title, content, signature.
    """
    return {
        'to': destinatario,
        'title': metadata.get('titulo') or metadata.get('title') or 'ReqSys',
        'content': texto,
        'signature': metadata.get('assinatura') or metadata.get('signature') or 'ReqSys',
        'correlationId': correlation_id,
    }


async def _enviar_flow_bot_webhook(
    url: str, destinatario: str, texto: str, metadata: dict[str, Any], correlation_id: str, circuit: CircuitBreaker
) -> dict[str, Any]:
    payload = _payload_flow_bot(destinatario, texto, metadata, correlation_id)

    async def _postar() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return {'status_code': resp.status_code}

    return await call_with_retry_async(
        _postar,
        max_retries=_FLOW_BOT_MAX_RETRIES,
        backoff_seconds=_FLOW_BOT_BACKOFF_SECONDS,
        retry_on=(httpx.TimeoutException, httpx.ConnectError),
        circuit=circuit,
    )


async def _enviar_flow_bot(
    request: TeamsGatewayMessageRequest,
    db: Session | None,
    correlation_id: str,
) -> dict[str, Any]:
    alvos = _flow_bot_alvos(db)
    if not alvos:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='flow_bot',
            erro='Flow bot do Teams nao configurado: nenhum flow_bot_owner ativo nem TEAMS_FLOW_BOT_WEBHOOK_URL',
        )
    if not request.destino_id:
        return _resultado(
            request,
            correlation_id,
            entregue=False,
            canal_usado='flow_bot',
            erro='destino_id (e-mail/UPN do usuario-alvo) e obrigatorio para o canal flow_bot',
        )

    tentativas: list[dict[str, Any]] = []
    for owner_email, webhook_url in alvos:
        try:
            provider = await _enviar_flow_bot_webhook(
                webhook_url,
                request.destino_id,
                request.texto,
                request.metadata,
                correlation_id,
                circuit=_flow_bot_circuit_do_dono(owner_email),
            )
            return _resultado(
                request,
                correlation_id,
                entregue=True,
                canal_usado='flow_bot',
                provider_response={**provider, 'owner': owner_email, 'tentativas_anteriores': len(tentativas)},
            )
        except CircuitBreakerOpenError as exc:
            tentativas.append({'owner': owner_email, 'erro': str(exc)})
        except httpx.HTTPStatusError as exc:
            tentativas.append({'owner': owner_email, 'erro': f'HTTP {exc.response.status_code}: {exc.response.text[:300]}'})
        except Exception as exc:
            logger.warning('teams_gateway_flow_bot_error correlation_id=%s owner=%s error=%s', correlation_id, owner_email, exc)
            tentativas.append({'owner': owner_email, 'erro': str(exc)})

    return _resultado(
        request,
        correlation_id,
        entregue=False,
        canal_usado='flow_bot',
        erro=f'Todos os {len(tentativas)} donos de flow_bot falharam.',
        motivo='flow_bot_todos_indisponiveis',
        provider_response={'tentativas': tentativas},
    )
