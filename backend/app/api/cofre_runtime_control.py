from __future__ import annotations

import json
import os
import re
import signal
import threading
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.core.service_tokens import ServiceAuthContext, require_admin_or_service_token
from app.db import get_db
from app.models.auditoria import AuditoriaEvento
from app.services.auditoria import registrar_evento

router = APIRouter(prefix='/v1/cofre/runtime', tags=['Cofre Runtime Control'])
_require_runtime_admin = require_admin_or_service_token('cofre:runtime_evidence')

_RUNTIME_SHA_RE = re.compile(r'^[0-9a-f]{40}$')
_RUNTIME_RESTART_CONFIRM = 'RESTART-COFRE-DEV-RUNTIME'
_RUNTIME_RESTART_AUDIT_ACTION = 'COFRE_RUNTIME_RESTART_REQUESTED'
_RUNTIME_BOOT_ID = uuid4().hex
_restart_lock = threading.Lock()


class RuntimeRestartPayload(BaseModel):
    expected_sha: str
    confirm: str

    @field_validator('expected_sha')
    @classmethod
    def sha_valido(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _RUNTIME_SHA_RE.fullmatch(normalized):
            raise ValueError('expected_sha deve ser um SHA Git completo de 40 caracteres')
        return normalized

    @field_validator('confirm')
    @classmethod
    def confirmacao_valida(cls, value: str) -> str:
        if value != _RUNTIME_RESTART_CONFIRM:
            raise ValueError('confirmação de restart inválida')
        return value


def runtime_state() -> dict:
    environment = (os.getenv('REQSYS_RUNTIME_ENVIRONMENT') or '').strip().lower()
    runtime_sha = (os.getenv('GITHUB_SHA') or '').strip().lower()
    enabled = (os.getenv('COFRE_RUNTIME_SELF_RESTART_ENABLED') or '').strip().lower() in {
        '1',
        'true',
        'yes',
        'on',
    }
    return {
        'environment': environment,
        'runtime_sha': runtime_sha,
        'boot_id': _RUNTIME_BOOT_ID,
        'self_restart_enabled': enabled,
    }


def _terminate_container_main_process() -> None:
    # PC24x7 usa container Linux com restart: unless-stopped. Encerrar PID 1
    # reinicia somente o container da API, sem acesso ao Docker socket/host.
    if os.name == 'nt':
        os._exit(0)
    os.kill(1, signal.SIGTERM)


def schedule_runtime_restart(delay_seconds: float = 1.5) -> None:
    timer = threading.Timer(delay_seconds, _terminate_container_main_process)
    timer.daemon = True
    timer.start()


def _audit(
    db: Session,
    *,
    correlation_id: str,
    actor: str,
    action: str,
    entity_id: str,
    payload: dict,
) -> None:
    registrar_evento(
        db,
        correlation_id,
        actor,
        action,
        'cofre_runtime',
        entity_id,
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


@router.get('/control-status')
def control_status(ctx: ServiceAuthContext = Depends(_require_runtime_admin)):
    del ctx
    state = runtime_state()
    return ok({
        'runtime_target': 'pc24x7',
        **state,
        'production_touched': False,
        'sensitive_values_exposed': False,
    })


@router.post('/restart', status_code=status.HTTP_202_ACCEPTED)
def restart_dev_runtime(
    payload: RuntimeRestartPayload,
    ctx: ServiceAuthContext = Depends(_require_runtime_admin),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    correlation_id = (x_correlation_id or '').strip()
    if not correlation_id:
        raise HTTPException(status_code=400, detail='X-Correlation-Id é obrigatório')

    state = runtime_state()
    if state['environment'] != 'dev':
        raise HTTPException(status_code=403, detail='Restart remoto permitido somente em DEV')
    if not state['self_restart_enabled']:
        raise HTTPException(status_code=409, detail='Restart remoto não habilitado neste runtime')
    if not _RUNTIME_SHA_RE.fullmatch(str(state['runtime_sha'])):
        raise HTTPException(status_code=409, detail='Runtime não publica GITHUB_SHA válido')
    if state['runtime_sha'] != payload.expected_sha:
        raise HTTPException(status_code=409, detail='runtime_sha_mismatch')

    with _restart_lock:
        existing = (
            db.query(AuditoriaEvento)
            .filter(
                AuditoriaEvento.correlation_id == correlation_id,
                AuditoriaEvento.acao == _RUNTIME_RESTART_AUDIT_ACTION,
                AuditoriaEvento.entidade_id == payload.expected_sha,
            )
            .first()
        )
        if existing is not None:
            return ok({
                'accepted': False,
                'duplicate': True,
                'environment': 'dev',
                'runtime_sha': payload.expected_sha,
                'boot_id': state['boot_id'],
                'restart_scheduled': False,
                'production_touched': False,
                'sensitive_values_exposed': False,
            })

        _audit(
            db,
            correlation_id=correlation_id,
            actor=ctx.ator,
            action=_RUNTIME_RESTART_AUDIT_ACTION,
            entity_id=payload.expected_sha,
            payload={
                'environment': 'dev',
                'runtime_target': 'pc24x7',
                'boot_id': state['boot_id'],
                'production_touched': False,
            },
        )
        schedule_runtime_restart()

    return ok({
        'accepted': True,
        'duplicate': False,
        'environment': 'dev',
        'runtime_sha': payload.expected_sha,
        'boot_id': state['boot_id'],
        'restart_scheduled': True,
        'production_touched': False,
        'sensitive_values_exposed': False,
    })
