"""Publicação governada de tarefas no Planner (issue #32).

Caminho aditivo e paralelo ao `publicar_tarefas_planner` (texto livre, sem
idempotência) já existente em `hub_lowcode.py` — este módulo não o substitui.
Reusa a mesma configuração de webhook e o mesmo log de integrações para que o
Painel de Integrações continue mostrando os dois caminhos juntos.

Idempotência: `idempotency_key = sha256(f"{source_id}|{payload_hash}")`, com
constraint UNIQUE na coluna — é essa constraint (não um check-then-insert) que
garante que duas chamadas concorrentes com o mesmo payload nunca criem duas
tarefas no Planner.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.planner_publish_attempt import PlannerPublishAttempt
from app.services.auditoria import registrar_evento
from app.services.hub_lowcode import (
    _postar_webhook_planner,
    obter_planner_webhook_config,
    salvar_log_integracao,
)

STATUS_ENFILEIRADO = 'enfileirado'
STATUS_PUBLICADO = 'publicado'
STATUS_DUPLICADO = 'duplicado'
STATUS_FALHOU_VALIDACAO = 'falhou_validacao'
STATUS_FALHOU_INTEGRACAO = 'falhou_integracao'

PRIORIDADES_VALIDAS = {'baixa', 'media', 'alta', 'urgente'}
MAX_TENTATIVAS_REPROCESSO = 5

_CAMPOS_PAYLOAD_HASH = ('plan_id', 'bucket_id', 'title', 'description', 'due_date', 'priority', 'requester')

_PADROES_SEGREDO = (
    re.compile(r'(x-webhook-key["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+', re.IGNORECASE),
    re.compile(r'(Bearer\s+)[A-Za-z0-9\-._~+/]+=*'),
)


def _mascarar(detalhe: str) -> str:
    """Remove possíveis segredos (chave do webhook, tokens Bearer) antes de
    persistir o erro (ADR-002)."""
    if not detalhe:
        return detalhe
    resultado = detalhe
    for padrao in _PADROES_SEGREDO:
        resultado = padrao.sub(r'\1[SEGREDO_REMOVIDO]', resultado)
    return resultado[:500]


def calcular_idempotency_key(payload: dict[str, Any]) -> tuple[str, str]:
    conteudo = {campo: payload.get(campo, '') for campo in _CAMPOS_PAYLOAD_HASH}
    payload_hash = hashlib.sha256(json.dumps(conteudo, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    idempotency_key = hashlib.sha256(f"{payload['source_id']}|{payload_hash}".encode('utf-8')).hexdigest()
    return idempotency_key, payload_hash


def _serializar(attempt: PlannerPublishAttempt) -> dict[str, Any]:
    return {
        'ok': attempt.status in (STATUS_PUBLICADO, STATUS_DUPLICADO),
        'status': attempt.status,
        'idempotency_key': attempt.idempotency_key,
        'attempt_id': attempt.id,
        'correlation_id': attempt.correlation_id,
        'planner_task_id': attempt.planner_task_id,
        'erro': attempt.ultimo_erro or None,
    }


async def _enviar_ao_webhook(db: Session, attempt: PlannerPublishAttempt) -> None:
    cfg = obter_planner_webhook_config(db)
    webhook_url = cfg.get('webhook_url') or ''

    if not webhook_url:
        attempt.status = STATUS_FALHOU_INTEGRACAO
        attempt.ultimo_erro = 'POWERAUTOMATE_PLANNER_WEBHOOK_URL não configurado'
        return

    payload = {
        'planId': attempt.plan_id,
        'bucketId': attempt.bucket_id,
        'title': attempt.title,
        'description': attempt.description,
        'dueDate': attempt.due_date,
        'priority': attempt.priority,
        'requester': attempt.requester,
        'sourceId': attempt.source_id,
        'correlationId': attempt.correlation_id,
    }
    headers: dict[str, str] = {'Content-Type': 'application/json'}
    webhook_key = cfg.get('webhook_key') or ''
    if webhook_key:
        headers['x-webhook-key'] = webhook_key

    try:
        resposta = await _postar_webhook_planner(webhook_url, payload, headers)
        attempt.status = STATUS_PUBLICADO
        attempt.planner_task_id = str(resposta.get('task_id') or resposta.get('id') or '') or None
        attempt.ultimo_erro = ''
    except httpx.HTTPStatusError as exc:
        attempt.status = STATUS_FALHOU_INTEGRACAO
        attempt.ultimo_erro = _mascarar(f'Flow retornou HTTP {exc.response.status_code}')
    except Exception as exc:
        attempt.status = STATUS_FALHOU_INTEGRACAO
        attempt.ultimo_erro = _mascarar(str(exc))


async def publicar_tarefa_planner_governada(db: Session, payload: dict[str, Any], correlation_id: str) -> dict[str, Any]:
    priority = (payload.get('priority') or '').strip().lower()
    if priority not in PRIORIDADES_VALIDAS:
        salvar_log_integracao(
            db, tipo='planner_publish', status='falhou_validacao', autor=payload.get('requester', ''),
            mensagem=f'priority inválida: "{payload.get("priority")}" (aceitos: {sorted(PRIORIDADES_VALIDAS)})',
            correlation_id=correlation_id,
        )
        return {
            'ok': False,
            'status': STATUS_FALHOU_VALIDACAO,
            'idempotency_key': '',
            'attempt_id': 0,
            'correlation_id': correlation_id,
            'planner_task_id': None,
            'erro': 'priority inválida',
        }

    idempotency_key, payload_hash = calcular_idempotency_key(payload)

    attempt = PlannerPublishAttempt(
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        correlation_id=correlation_id,
        source_id=payload['source_id'],
        plan_id=payload['plan_id'],
        bucket_id=payload['bucket_id'],
        title=payload['title'],
        description=payload.get('description', ''),
        due_date=payload['due_date'],
        priority=priority,
        requester=payload['requester'],
        status=STATUS_ENFILEIRADO,
        tentativas=0,
    )
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existente = db.query(PlannerPublishAttempt).filter(
            PlannerPublishAttempt.idempotency_key == idempotency_key
        ).first()
        if existente is None:
            raise
        resultado = _serializar(existente)
        if existente.status in (STATUS_PUBLICADO, STATUS_DUPLICADO):
            resultado['status'] = STATUS_DUPLICADO
            resultado['ok'] = True
        return resultado
    db.refresh(attempt)

    await _enviar_ao_webhook(db, attempt)
    attempt.tentativas += 1
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    salvar_log_integracao(
        db, tipo='planner_publish', status='sucesso' if attempt.status == STATUS_PUBLICADO else 'erro',
        autor=attempt.requester, titulo=attempt.title, mensagem=attempt.ultimo_erro or 'publicado no Planner',
        correlation_id=correlation_id,
    )
    registrar_evento(db, correlation_id, attempt.requester, 'PLANNER_TASK_PUBLICADO', 'planner_publish_attempts', attempt.id)

    return _serializar(attempt)


async def reprocessar_tentativa(db: Session, attempt_id: int, correlation_id: str) -> dict[str, Any]:
    attempt = db.get(PlannerPublishAttempt, attempt_id)
    if attempt is None:
        raise ValueError(f'Tentativa {attempt_id} não encontrada')
    if attempt.status in (STATUS_PUBLICADO, STATUS_DUPLICADO):
        raise ValueError(f'Tentativa {attempt_id} já está "{attempt.status}" — reprocessamento recusado para evitar duplicidade')
    if attempt.status != STATUS_FALHOU_INTEGRACAO:
        raise ValueError(f'Tentativa {attempt_id} com status "{attempt.status}" não é reprocessável')
    if attempt.tentativas >= MAX_TENTATIVAS_REPROCESSO:
        raise ValueError(f'Tentativa {attempt_id} excedeu o limite de {MAX_TENTATIVAS_REPROCESSO} tentativas')

    await _enviar_ao_webhook(db, attempt)
    attempt.tentativas += 1
    attempt.correlation_id = correlation_id
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    registrar_evento(db, correlation_id, attempt.requester, 'PLANNER_TASK_REPROCESSED', 'planner_publish_attempts', attempt.id)

    return _serializar(attempt)


def obter_status_tentativa(db: Session, attempt_id: int) -> dict[str, Any] | None:
    attempt = db.get(PlannerPublishAttempt, attempt_id)
    if attempt is None:
        return None
    return _serializar(attempt)


def listar_tentativas(db: Session, source_id: str | None = None, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = db.query(PlannerPublishAttempt)
    if source_id:
        query = query.filter(PlannerPublishAttempt.source_id == source_id)
    if status:
        query = query.filter(PlannerPublishAttempt.status == status)
    itens = query.order_by(PlannerPublishAttempt.criado_em.desc()).limit(limit).all()
    return [_serializar(item) for item in itens]
