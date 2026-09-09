from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.pii_masking import mascarar_pii
from app.models.ai_conversation import AIConversation, AIConversationMessage
from app.schemas.ai_conversation import AIConversationCreateRequest
from app.schemas.teams_notifications import TeamsNotificationEnqueueRequest
from app.services.ai_corporate_policy import (
    CorporateAIPolicyError,
    evaluate_provider_policy,
    policy_mode,
)
from app.services.ai_history_protection import (
    AIUsageBudgetExceededError,
    AIScopeViolationError,
    assert_budget,
    assert_scope,
    estimate_tokens,
    record_usage,
)
from app.services.ai_provider_config import AIProviderRuntimeConfigError, resolve_provider_config
from app.services.llm_provider import LLMGateway
from app.services.teams_notifications import criar_item_fila

DEFAULT_CONTEXT_CHARS = 24000
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_SYSTEM_PROMPT = (
    'Continue a conversa preservando o contexto anterior. '
    'Responda à última mensagem do usuário de forma objetiva e não invente fatos.'
)


class AIConversationError(RuntimeError):
    pass


class AIConversationNotFoundError(AIConversationError):
    pass


class AIConversationConflictError(AIConversationError):
    pass


class AIConversationScopeError(AIConversationError):
    pass


class AIConversationBudgetError(AIConversationError):
    pass


class AIProviderConfigurationError(AIConversationError):
    pass


class AIProviderExecutionError(AIConversationError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _env_value(env: Mapping[str, str] | None, *names: str) -> str:
    for name in names:
        value = env.get(name) if env is not None else os.getenv(name)
        if value and str(value).strip():
            return str(value).strip()
    return ''


def _env_int(env: Mapping[str, str] | None, name: str, default: int) -> int:
    raw = _env_value(env, name)
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _env_bool(env: Mapping[str, str] | None, name: str, default: bool) -> bool:
    raw = _env_value(env, name)
    if not raw:
        return default
    return raw.lower() not in {'0', 'false', 'no', 'off'}


def _classification_lock(conversation_id: str, data_classification: str) -> str:
    return hashlib.sha256(f'{conversation_id}|{data_classification}'.encode('utf-8')).hexdigest()


def status_provedores(env: Mapping[str, str] | None = None) -> dict[str, dict[str, bool]]:
    status: dict[str, dict[str, bool]] = {}
    for provider in ('openai', 'claude', 'gemini', 'groq'):
        try:
            resolve_provider_config(provider, env=env)
            status[provider] = {'configurado': True}
        except AIProviderRuntimeConfigError:
            status[provider] = {'configurado': False}
    status['ollama'] = {
        'configurado': bool(
            _env_value(env, 'AI_CONVERSATION_OLLAMA_BASE_URL', 'CODEX_OLLAMA_BASE_URL', 'OLLAMA_BASE_URL')
        )
    }
    return status


def criar_conversa(db: Session, payload: AIConversationCreateRequest, *, correlation_id: str) -> AIConversation:
    try:
        decision = evaluate_provider_policy(
            provider=payload.provider,
            data_classification=payload.data_classification,
        )
    except CorporateAIPolicyError as exc:
        raise AIProviderConfigurationError(str(exc)) from None

    conversation_id = str(uuid.uuid4())
    conversa = AIConversation(
        id=conversation_id,
        provider=payload.provider,
        model=payload.model,
        titulo=payload.titulo,
        origem=payload.origem,
        status='aguardando_usuario',
        correlation_id=correlation_id,
        tenant_id=payload.tenant_id,
        area_id=payload.area_id,
        requester_id=payload.requester_id,
        cost_center=payload.cost_center,
        data_classification=payload.data_classification,
        classification_lock_sha256=_classification_lock(conversation_id, payload.data_classification),
        requested_provider=decision.requested_provider,
        authorized_provider=decision.authorized_provider or payload.provider,
        policy_mode=decision.mode,
        policy_decision='allowed' if decision.allowed else 'blocked',
        policy_reason=decision.reason,
        policy_correlation_id=correlation_id,
        teams_destino_tipo=payload.teams_destino_tipo,
        teams_destino_id=payload.teams_destino_id,
        teams_modo=payload.teams_modo,
        teams_permitir_fallback=payload.teams_permitir_fallback,
        ultima_mensagem_em=_utcnow(),
    )
    db.add(conversa)
    db.commit()
    db.refresh(conversa)
    return conversa


def obter_conversa(
    db: Session,
    conversation_id: str,
    *,
    tenant_id: str | None = None,
    area_id: str | None = None,
    env: Mapping[str, str] | None = None,
) -> AIConversation:
    conversa = db.get(AIConversation, conversation_id)
    if conversa is None:
        raise AIConversationNotFoundError('Conversa de IA não encontrada.')
    try:
        assert_scope(
            conversa,
            tenant_id=tenant_id,
            area_id=area_id,
            enforce=policy_mode(env) == 'enforce',
        )
    except AIScopeViolationError as exc:
        raise AIConversationScopeError(str(exc)) from None
    return conversa


def listar_mensagens(db: Session, conversation_id: str) -> list[AIConversationMessage]:
    stmt = select(AIConversationMessage).where(
        AIConversationMessage.conversation_id == conversation_id
    ).order_by(AIConversationMessage.id.asc())
    return list(db.execute(stmt).scalars().all())


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _assistant_idempotency(user_key: str) -> str:
    return f'assistant:{hashlib.sha256(user_key.encode("utf-8")).hexdigest()}'


def _salvar_mensagem(
    db: Session,
    *,
    conversa: AIConversation,
    role: str,
    content: str,
    source: str,
    correlation_id: str,
    idempotency_key: str,
) -> AIConversationMessage:
    item = AIConversationMessage(
        conversation_id=conversa.id,
        role=role,
        content=content,
        source=source,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        content_sha256=_hash_content(content),
    )
    db.add(item)
    conversa.ultima_mensagem_em = _utcnow()
    db.commit()
    db.refresh(item)
    return item


def _buscar_mensagem_idempotente(
    db: Session,
    *,
    conversation_id: str,
    idempotency_key: str,
) -> AIConversationMessage | None:
    stmt = select(AIConversationMessage).where(
        AIConversationMessage.conversation_id == conversation_id,
        AIConversationMessage.idempotency_key == idempotency_key,
    )
    return db.execute(stmt).scalar_one_or_none()


def _montar_contexto(db: Session, *, conversation_id: str, max_chars: int) -> str:
    stmt = (
        select(AIConversationMessage)
        .where(AIConversationMessage.conversation_id == conversation_id)
        .order_by(desc(AIConversationMessage.id))
        .limit(80)
    )
    recentes = list(db.execute(stmt).scalars().all())
    selecionadas: list[AIConversationMessage] = []
    total = 0
    for item in recentes:
        bloco = f'{item.role.upper()}: {item.content}\n'
        if selecionadas and total + len(bloco) > max_chars:
            break
        selecionadas.append(item)
        total += len(bloco)
    selecionadas.reverse()
    return '\n'.join(f'{item.role.upper()}: {item.content}' for item in selecionadas)


def _validar_politica_persistida(
    conversa: AIConversation,
    *,
    correlation_id: str,
    env: Mapping[str, str] | None,
) -> None:
    expected_lock = _classification_lock(conversa.id, conversa.data_classification)
    if conversa.classification_lock_sha256 != expected_lock:
        raise AIProviderConfigurationError(
            'Classificação da conversa foi alterada sem atualização governada da trava de integridade.'
        )
    if conversa.requested_provider != conversa.provider:
        raise AIProviderConfigurationError('Provedor da conversa diverge do provedor originalmente solicitado.')
    try:
        decision = evaluate_provider_policy(
            provider=conversa.provider,
            data_classification=conversa.data_classification,
            env=env,
        )
    except CorporateAIPolicyError as exc:
        conversa.policy_decision = 'blocked'
        conversa.policy_reason = str(exc)[:500]
        conversa.policy_correlation_id = correlation_id
        raise AIProviderConfigurationError(str(exc)) from None
    if decision.authorized_provider != conversa.provider:
        raise AIProviderConfigurationError(
            'Provedor autorizado pela política diverge do provedor persistido na conversa.'
        )
    conversa.authorized_provider = decision.authorized_provider or conversa.provider
    conversa.policy_mode = decision.mode
    conversa.policy_decision = 'allowed'
    conversa.policy_reason = decision.reason
    conversa.policy_correlation_id = correlation_id


def _chamar_provider(
    *,
    conversa: AIConversation,
    prompt: str,
    gateway: LLMGateway,
    env: Mapping[str, str] | None,
    correlation_id: str,
) -> str:
    _validar_politica_persistida(conversa, correlation_id=correlation_id, env=env)
    provider = conversa.provider
    model = conversa.model
    timeout = _env_int(env, 'AI_CONVERSATION_TIMEOUT_SECONDS', DEFAULT_TIMEOUT_SECONDS)
    system_prompt = _env_value(env, 'AI_CONVERSATION_SYSTEM_PROMPT') or DEFAULT_SYSTEM_PROMPT
    try:
        if provider in {'openai', 'claude', 'gemini', 'groq'}:
            runtime = resolve_provider_config(provider, env=env)
            common = {
                'api_key': runtime.secret,
                'model': model,
                'prompt': prompt,
                'system_prompt': system_prompt,
                'timeout': timeout,
                'endpoint': runtime.endpoint,
                'auth_mode': runtime.auth_mode,
            }
            if provider == 'openai':
                resposta = gateway.gerar_openai(**common)
            elif provider == 'claude':
                resposta = gateway.gerar_claude(**common)
            elif provider == 'gemini':
                resposta = gateway.gerar_gemini(**common)
            else:
                resposta = gateway.gerar_groq(**common)
        elif provider == 'ollama':
            base_url = _env_value(env, 'AI_CONVERSATION_OLLAMA_BASE_URL', 'CODEX_OLLAMA_BASE_URL', 'OLLAMA_BASE_URL')
            if not base_url:
                raise AIProviderConfigurationError('Provedor Ollama não configurado.')
            resposta = gateway.gerar_ollama(
                base_url=base_url,
                model=model,
                prompt=f'{system_prompt}\n\n{prompt}',
                timeout=timeout,
            )
        else:
            raise AIProviderConfigurationError(f'Provedor não suportado: {provider}.')
    except AIProviderRuntimeConfigError as exc:
        raise AIProviderConfigurationError(str(exc)) from None
    except AIProviderConfigurationError:
        raise
    except Exception as exc:
        raise AIProviderExecutionError(
            f'Falha ao executar o provedor {provider}: {type(exc).__name__}.'
        ) from None
    resposta_normalizada = str(resposta or '').strip()
    if not resposta_normalizada:
        raise AIProviderExecutionError(f'O provedor {provider} retornou resposta vazia.')
    return resposta_normalizada


def construir_adaptive_card(
    conversa: AIConversation,
    resposta: str,
    *,
    correlation_id: str,
) -> dict[str, Any]:
    return {
        '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
        'type': 'AdaptiveCard',
        'version': '1.4',
        'msteams': {'width': 'Full'},
        'body': [
            {'type': 'TextBlock', 'text': conversa.titulo, 'weight': 'Bolder', 'size': 'Medium', 'wrap': True},
            {
                'type': 'FactSet',
                'facts': [
                    {'title': 'Provedor', 'value': conversa.provider},
                    {'title': 'Modelo', 'value': conversa.model},
                    {'title': 'Conversa', 'value': conversa.id},
                ],
            },
            {'type': 'TextBlock', 'text': resposta[:8000], 'wrap': True},
            {
                'type': 'Input.Text', 'id': 'mensagem', 'isMultiline': True,
                'maxLength': 20000, 'placeholder': 'Escreva aqui para continuar esta mesma conversa.',
            },
        ],
        'actions': [{
            'type': 'Action.Submit',
            'title': 'Continuar conversa',
            'data': {
                'reqsys_action': 'ai_conversation_reply',
                'conversation_id': conversa.id,
                'correlation_id': correlation_id,
            },
        }],
    }


def _enfileirar_teams(
    db: Session,
    *,
    conversa: AIConversation,
    resposta: str,
    correlation_id: str,
):
    card = construir_adaptive_card(conversa, resposta, correlation_id=correlation_id)
    payload = TeamsNotificationEnqueueRequest(
        origem='sistema',
        tipo_evento='ai_conversation_response_completed',
        ambiente=_env_value(None, 'ENVIRONMENT', 'APP_ENV') or 'unknown',
        correlation_id=correlation_id,
        titulo=f'{conversa.provider}/{conversa.model} — {conversa.titulo}',
        texto=resposta[:20000],
        content_type='text',
        autor='reqsys-ai-conversation-gateway',
        metadata={
            'source': 'ai-conversation-gateway',
            'conversation_id': conversa.id,
            'provider': conversa.provider,
            'model': conversa.model,
            'tenant_id': conversa.tenant_id,
            'area_id': conversa.area_id,
            'data_classification': conversa.data_classification,
            'policy_decision': conversa.policy_decision,
            'reply_endpoint': f'/v1/teams-gateway/ai-conversations/{conversa.id}/reply',
            'requires_wait_for_response': True,
            'adaptiveCard': card,
        },
        destino_tipo=conversa.teams_destino_tipo,
        destino_id=conversa.teams_destino_id,
        modo=conversa.teams_modo,
        permitir_fallback=conversa.teams_permitir_fallback,
        dry_run=False,
        enviar_agora=True,
        max_tentativas=3,
    )
    return criar_item_fila(db, payload)


def executar_turno(
    db: Session,
    *,
    conversa: AIConversation,
    mensagem: str,
    correlation_id: str,
    idempotency_key: str | None,
    origem: str,
    enviar_teams: bool,
    gateway: LLMGateway | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if conversa.status == 'encerrada':
        raise AIConversationConflictError('A conversa já está encerrada.')
    mensagem_normalizada = mensagem.strip()
    if not mensagem_normalizada:
        raise AIConversationConflictError('Mensagem vazia não é permitida.')

    user_key = (idempotency_key or f'turn:{uuid.uuid4()}').strip()
    existente = _buscar_mensagem_idempotente(db, conversation_id=conversa.id, idempotency_key=user_key)
    if existente is not None:
        if existente.content_sha256 != _hash_content(mensagem_normalizada):
            raise AIConversationConflictError('A mesma chave de idempotência foi reutilizada com conteúdo diferente.')
        resposta_existente = _buscar_mensagem_idempotente(
            db, conversation_id=conversa.id, idempotency_key=_assistant_idempotency(user_key)
        )
        if resposta_existente is None:
            raise AIConversationConflictError(
                'A mensagem já existe, mas o turno anterior ainda não possui resposta concluída.'
            )
        return {
            'conversa': conversa,
            'mensagem_usuario': existente,
            'mensagem_assistente': resposta_existente,
            'notificacao': None,
            'duplicado': True,
        }

    conversa.status = 'processando'
    db.commit()
    user_message = _salvar_mensagem(
        db,
        conversa=conversa,
        role='user',
        content=mensagem_normalizada,
        source=origem,
        correlation_id=correlation_id,
        idempotency_key=user_key,
    )
    historico = _montar_contexto(
        db,
        conversation_id=conversa.id,
        max_chars=_env_int(env, 'AI_CONVERSATION_MAX_CONTEXT_CHARS', DEFAULT_CONTEXT_CHARS),
    )
    prompt = (
        'Histórico governado da conversa:\n\n'
        f'{historico}\n\n'
        'Continue a partir da última mensagem USER sem repetir desnecessariamente o histórico.'
    )
    prompt_provider = mascarar_pii(prompt) if _env_bool(env, 'AI_CONVERSATION_PII_MASKING', True) else prompt

    try:
        assert_budget(
            db,
            conversation=conversa,
            estimated_next_tokens=estimate_tokens(prompt_provider),
            env=env,
        )
    except AIUsageBudgetExceededError as exc:
        conversa.status = 'falha'
        db.commit()
        raise AIConversationBudgetError(str(exc)) from None

    try:
        resposta = _chamar_provider(
            conversa=conversa,
            prompt=prompt_provider,
            gateway=gateway or LLMGateway(),
            env=env,
            correlation_id=correlation_id,
        )
    except AIConversationError:
        conversa.status = 'falha'
        db.commit()
        raise

    assistant_message = _salvar_mensagem(
        db,
        conversa=conversa,
        role='assistant',
        content=resposta,
        source=conversa.provider,
        correlation_id=correlation_id,
        idempotency_key=_assistant_idempotency(user_key),
    )
    record_usage(
        db,
        conversation=conversa,
        prompt=prompt_provider,
        response=resposta,
        correlation_id=correlation_id,
    )
    conversa.status = 'aguardando_usuario'
    conversa.ultima_mensagem_em = _utcnow()
    db.commit()
    db.refresh(conversa)

    notificacao = None
    if enviar_teams:
        notificacao = _enfileirar_teams(
            db, conversa=conversa, resposta=resposta, correlation_id=correlation_id
        )
    return {
        'conversa': conversa,
        'mensagem_usuario': user_message,
        'mensagem_assistente': assistant_message,
        'notificacao': notificacao,
        'duplicado': False,
    }


def serializar_conversa(
    db: Session,
    conversa: AIConversation,
    *,
    incluir_mensagens: bool = True,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        'id': conversa.id,
        'provider': conversa.provider,
        'model': conversa.model,
        'provider_conversation_id': conversa.provider_conversation_id,
        'titulo': conversa.titulo,
        'origem': conversa.origem,
        'status': conversa.status,
        'correlation_id': conversa.correlation_id,
        'tenant_id': conversa.tenant_id,
        'area_id': conversa.area_id,
        'requester_id': conversa.requester_id,
        'cost_center': conversa.cost_center,
        'data_classification': conversa.data_classification,
        'requested_provider': conversa.requested_provider,
        'authorized_provider': conversa.authorized_provider,
        'policy_mode': conversa.policy_mode,
        'policy_decision': conversa.policy_decision,
        'policy_reason': conversa.policy_reason,
        'policy_correlation_id': conversa.policy_correlation_id,
        'teams_destino_tipo': conversa.teams_destino_tipo,
        'teams_modo': conversa.teams_modo,
        'criado_em': conversa.criado_em.isoformat() if conversa.criado_em else None,
        'atualizado_em': conversa.atualizado_em.isoformat() if conversa.atualizado_em else None,
        'ultima_mensagem_em': conversa.ultima_mensagem_em.isoformat() if conversa.ultima_mensagem_em else None,
    }
    if incluir_mensagens:
        data['mensagens'] = [
            {
                'id': item.id,
                'role': item.role,
                'content': item.content,
                'source': item.source,
                'correlation_id': item.correlation_id,
                'content_sha256': item.content_sha256,
                'criado_em': item.criado_em.isoformat() if item.criado_em else None,
            }
            for item in listar_mensagens(db, conversa.id)
        ]
    return data
