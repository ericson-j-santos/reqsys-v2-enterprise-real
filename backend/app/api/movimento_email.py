"""API da rotina de e-mail diário de Prospecção Movimento — Portabilidade
Consignado (Funcionalidade #2861: migração da rotina SSRS legada para
Python). Ver docs/architecture/movimento-email-pipeline.md.
"""

from __future__ import annotations

import logging
from datetime import datetime as dt
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.core.service_tokens import require_admin_or_service_token
from app.db import get_db
from app.schemas.movimento_email import MovimentoEmailConsumirRequest, MovimentoEmailJobRequest
from app.services.email_mime_report_service import EmailIdentity
from app.services.movimento_email import queue_repository as fila
from app.services.movimento_email.consumer import consumir_fila_email_movimento
from app.services.movimento_email.jobs import executar_job_diario
from app.services.movimento_email.repository import ExtracaoError, SqlServerProspeccaoMovimentoRepository
from app.services.movimento_email.smtp_sender import EnvioEmailError, SmtpEmailSender

logger = logging.getLogger('reqsys.movimento_email_api')

router = APIRouter(prefix='/v1/movimento-email', tags=['Movimento Email (#2861)'])

# Instância única para permitir override em testes via app.dependency_overrides
# (mesmo padrão de teams_gateway.py / redmine_sync.py).
require_job_auth = require_admin_or_service_token('movimento_email:job')
require_consumir_auth = require_admin_or_service_token('movimento_email:consumir')


def _classificar_saude(contagens: dict[str, int]) -> str:
    if contagens.get(fila.STATUS_ERROR, 0) > 0:
        return 'vermelho'
    if contagens.get(fila.STATUS_PROCESSING, 0) > 0:
        return 'azul'
    return 'verde'


@router.get('/status', dependencies=[Depends(require_admin)])
async def movimento_email_status(db: Session = Depends(get_db)):
    """Contagem por status na fila `movimento_email_dispatch` (estados
    ADR-007: verde=saudável, azul=em execução, vermelho=falha crítica)."""
    contagens = fila.snapshot(db)
    return ok({'contagens': contagens, 'saude': _classificar_saude(contagens)})


@router.post('/jobs/executar')
async def movimento_email_job_executar(
    payload: MovimentoEmailJobRequest = MovimentoEmailJobRequest(),
    ctx=Depends(require_job_auth),
    db: Session = Depends(get_db),
):
    """Executa o job diário: extrai os 4 datasets do SQL Server de origem,
    renderiza o e-mail e enfileira para envio (não envia diretamente — ver
    `/fila/consumir`).

    Autenticação: JWT admin (humano) OU `X-Service-Token` escopado para
    `movimento_email:job` (para acionar via agendador/cron externo).
    """
    if not settings.movimento_email_source_dsn:
        raise HTTPException(status_code=409, detail='MOVIMENTO_EMAIL_SOURCE_DSN não configurado')

    destinatarios = payload.destinatarios or settings.movimento_email_recipients_list
    if not destinatarios:
        raise HTTPException(status_code=409, detail='Nenhum destinatário configurado (MOVIMENTO_EMAIL_RECIPIENTS ou payload.destinatarios)')

    correlation_id = resolver_correlation_id()
    repository = SqlServerProspeccaoMovimentoRepository(
        settings.movimento_email_source_dsn,
        query_timeout_seconds=settings.movimento_email_query_timeout_seconds,
    )
    try:
        resultado = executar_job_diario(
            db,
            repository,
            data_referencia=payload.data_referencia or dt.now(timezone.utc).date(),
            correlation_id=correlation_id,
            destinatarios=[str(e) for e in destinatarios],
            max_retries=settings.movimento_email_max_tentativas,
        )
    except ExtracaoError as exc:
        raise HTTPException(status_code=502, detail=f'Falha ao extrair dados de origem: {exc}') from None
    return ok(resultado, correlation_id)


@router.post('/fila/consumir')
async def movimento_email_fila_consumir(
    payload: MovimentoEmailConsumirRequest = MovimentoEmailConsumirRequest(),
    ctx=Depends(require_consumir_auth),
    db: Session = Depends(get_db),
):
    """Processa um lote da fila de envio: libera reservas travadas (timeout
    configurável via MOVIMENTO_EMAIL_RESERVA_TIMEOUT_MINUTOS, padrão 15min —
    ver CLAUDE.md do usuário) e envia via SMTP os itens `PENDING`.

    `dry_run=true` mostra o que SERIA enviado sem chamar o SMTP nem gravar
    nada (formato de resposta deliberadamente distinto de um envio real).
    """
    if not payload.dry_run and not settings.movimento_email_smtp_host:
        raise HTTPException(status_code=409, detail='MOVIMENTO_EMAIL_SMTP_HOST não configurado')

    correlation_id = resolver_correlation_id()
    sender = None
    if not payload.dry_run:
        sender = SmtpEmailSender(
            host=settings.movimento_email_smtp_host,
            port=settings.movimento_email_smtp_port,
            username=settings.movimento_email_smtp_user,
            password=settings.movimento_email_smtp_password,
            use_tls=settings.movimento_email_smtp_use_tls,
        )
    try:
        resultado = consumir_fila_email_movimento(
            db,
            sender,
            remetente=EmailIdentity(settings.movimento_email_smtp_from or settings.movimento_email_smtp_user).as_header(),
            lote_max=payload.lote_max or settings.movimento_email_lote_max,
            reserva_timeout_minutos=settings.movimento_email_reserva_timeout_minutos,
            dry_run=payload.dry_run,
        )
    except EnvioEmailError as exc:
        raise HTTPException(status_code=502, detail=f'Falha ao enviar e-mail via SMTP: {exc}') from None
    return ok(resultado, correlation_id)
