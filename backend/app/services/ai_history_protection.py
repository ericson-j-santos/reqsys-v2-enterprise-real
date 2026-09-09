from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ai_conversation import AIConversation, AIUsageLedger

DEFAULT_AI_CONVERSATION_RETENTION_DAYS = 30


class AIHistoryProtectionError(RuntimeError):
    pass


class AIScopeViolationError(AIHistoryProtectionError):
    pass


class AIUsageBudgetExceededError(AIHistoryProtectionError):
    pass


def _value(env: Mapping[str, str] | None, name: str) -> str:
    value = env.get(name) if env is not None else os.getenv(name)
    return str(value or '').strip()


def retention_days(env: Mapping[str, str] | None = None) -> int:
    raw = _value(env, 'AI_CONVERSATION_RETENTION_DAYS') or str(DEFAULT_AI_CONVERSATION_RETENTION_DAYS)
    try:
        days = int(raw)
    except ValueError as exc:
        raise AIHistoryProtectionError('AI_CONVERSATION_RETENTION_DAYS inválido.') from exc
    if days < 1:
        raise AIHistoryProtectionError('Retenção de conversas deve ser de pelo menos 1 dia.')
    return days


def assert_scope(
    conversation: AIConversation,
    *,
    tenant_id: str | None,
    area_id: str | None,
    enforce: bool,
) -> None:
    if enforce and not tenant_id:
        raise AIScopeViolationError('X-Tenant-ID é obrigatório no modo corporativo.')
    if tenant_id and conversation.tenant_id != tenant_id:
        raise AIScopeViolationError('Conversa fora do tenant autorizado.')
    if area_id and conversation.area_id != area_id:
        raise AIScopeViolationError('Conversa fora da área autorizada.')


def estimate_tokens(text: str) -> int:
    return max(1, (len(text or '') + 3) // 4)


def _json_budgets(env: Mapping[str, str] | None, name: str) -> dict[str, int]:
    raw = _value(env, name)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError
        return {str(k): int(v) for k, v in parsed.items() if int(v) > 0}
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise AIHistoryProtectionError(f'{name} deve ser um JSON objeto com limites inteiros positivos.') from exc


def _month_start(now: datetime) -> datetime:
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def _used_tokens(
    db: Session,
    *,
    tenant_id: str,
    now: datetime,
    requester_id: str | None = None,
    cost_center: str | None = None,
) -> int:
    query = db.query(func.coalesce(func.sum(AIUsageLedger.total_estimated_tokens), 0)).filter(
        AIUsageLedger.tenant_id == tenant_id,
        AIUsageLedger.criado_em >= _month_start(now),
    )
    if requester_id is not None:
        query = query.filter(AIUsageLedger.requester_id == requester_id)
    if cost_center is not None:
        query = query.filter(AIUsageLedger.cost_center == cost_center)
    return int(query.scalar() or 0)


def assert_budget(
    db: Session,
    *,
    conversation: AIConversation,
    estimated_next_tokens: int,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> None:
    observed_at = now or datetime.now(UTC)
    requester_budgets = _json_budgets(env, 'AI_REQUESTER_MONTHLY_TOKEN_BUDGETS_JSON')
    cost_budgets = _json_budgets(env, 'AI_COST_CENTER_MONTHLY_TOKEN_BUDGETS_JSON')
    default_raw = _value(env, 'AI_MONTHLY_TOKEN_BUDGET_DEFAULT')
    default_budget = int(default_raw) if default_raw.isdigit() and int(default_raw) > 0 else None

    requester_budget = requester_budgets.get(conversation.requester_id, default_budget)
    if requester_budget is not None:
        used = _used_tokens(
            db,
            tenant_id=conversation.tenant_id,
            requester_id=conversation.requester_id,
            now=observed_at,
        )
        if used + estimated_next_tokens > requester_budget:
            raise AIUsageBudgetExceededError(
                f'Orçamento mensal estimado do solicitante excedido ({used}/{requester_budget} tokens).'
            )

    cost_budget = cost_budgets.get(conversation.cost_center, default_budget)
    if cost_budget is not None:
        used = _used_tokens(
            db,
            tenant_id=conversation.tenant_id,
            cost_center=conversation.cost_center,
            now=observed_at,
        )
        if used + estimated_next_tokens > cost_budget:
            raise AIUsageBudgetExceededError(
                f'Orçamento mensal estimado do centro de custo excedido ({used}/{cost_budget} tokens).'
            )


def record_usage(
    db: Session,
    *,
    conversation: AIConversation,
    prompt: str,
    response: str,
    correlation_id: str,
) -> AIUsageLedger:
    input_tokens = estimate_tokens(prompt)
    output_tokens = estimate_tokens(response)
    ledger = AIUsageLedger(
        conversation_id=conversation.id,
        tenant_id=conversation.tenant_id,
        requester_id=conversation.requester_id,
        cost_center=conversation.cost_center,
        provider=conversation.provider,
        model=conversation.model,
        correlation_id=correlation_id,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        total_estimated_tokens=input_tokens + output_tokens,
    )
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


def purge_expired_conversations(
    db: Session,
    *,
    env: Mapping[str, str] | None = None,
    tenant_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    days = retention_days(env)
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    query = db.query(AIConversation).filter(AIConversation.atualizado_em < cutoff)
    if tenant_id:
        query = query.filter(AIConversation.tenant_id == tenant_id)
    total = query.count()
    if total:
        query.delete(synchronize_session=False)
        db.commit()
    return {'retention_days': days, 'registros_removidos': total, 'cutoff': cutoff.isoformat()}


def delete_conversation(db: Session, conversation: AIConversation) -> None:
    db.delete(conversation)
    db.commit()
