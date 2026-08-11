"""Job diário (`jobs.py` da documentação original): dispara o pipeline
extração -> transformação -> renderização -> fila (ADR-001, ADR-003).
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.services.auditoria import registrar_evento
from app.services.movimento_email import queue_repository as fila
from app.services.movimento_email.email_service import (
    render_email_movimento_html,
    render_email_movimento_text,
)
from app.services.movimento_email.repository import ExtracaoError, ProspeccaoMovimentoRepository
from app.services.movimento_email.transform import montar_contexto

logger = logging.getLogger('reqsys.movimento_email.jobs')

ATOR_JOB = 'movimento_email_job_diario'


def executar_job_diario(
    db: Session,
    repository: ProspeccaoMovimentoRepository,
    *,
    data_referencia: date,
    correlation_id: str,
    destinatarios: list[str],
    max_retries: int = fila.DEFAULT_MAX_TENTATIVAS,
) -> dict:
    """Extrai os 4 datasets, monta o contexto, renderiza o e-mail e enfileira
    para envio. Não envia diretamente — o consumer (`consumer.py`) é quem
    fala com o SMTP, mantendo o job idempotente e revisável antes do envio."""
    try:
        fechamento = repository.get_fechamento(data_referencia)
        pendencias_cadastro = repository.get_pendencias_cadastro(data_referencia)
        pendencias_historicas = repository.get_pendencias_historicas(data_referencia)
        pendencias_observacao = repository.get_pendencias_observacao(data_referencia)
    except ExtracaoError as exc:
        logger.error('movimento_email_job_extracao_falhou correlation_id=%s erro=%s', correlation_id, exc)
        registrar_evento(db, correlation_id, ATOR_JOB, 'MOVIMENTO_EMAIL_JOB_EXTRACAO_FALHOU', 'movimento_email_dispatch', 0)
        raise

    contexto = montar_contexto(
        data_referencia=data_referencia,
        correlation_id=correlation_id,
        fechamento=fechamento,
        pendencias_cadastro=pendencias_cadastro,
        pendencias_historicas=pendencias_historicas,
        pendencias_observacao=pendencias_observacao,
    )

    assunto = f'Prospecção Movimento — Resumo diário {data_referencia.isoformat()}'
    html_body = render_email_movimento_html(contexto)
    text_body = render_email_movimento_text(contexto)

    item = fila.enfileirar(
        db,
        correlation_id=correlation_id,
        data_referencia=data_referencia,
        destinatarios=destinatarios,
        assunto=assunto,
        html_body=html_body,
        text_body=text_body,
        max_retries=max_retries,
    )
    registrar_evento(db, correlation_id, ATOR_JOB, 'MOVIMENTO_EMAIL_JOB_ENFILEIRADO', 'movimento_email_dispatch', item.id)

    return {
        'dispatch_id': item.id,
        'correlation_id': correlation_id,
        'data_referencia': data_referencia.isoformat(),
        'total_fechamento': len(fechamento),
        'total_pendencias': contexto.total_pendencias,
        'status': item.status,
    }
