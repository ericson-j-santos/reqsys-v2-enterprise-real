"""Consumer da fila de e-mail (`consome_fila_emails.py` da documentação
original) — cleanup de reservas travadas -> reserva de lote -> envio SMTP ->
marcação do resultado (ADR-001, ADR-003, ADR-010).

`dry_run=True` nunca chama o SMTP nem grava nada; o formato de retorno é
deliberadamente diferente de um envio real (`seriam_enviados`, sem
`enviados`/`falhas`) para nunca parecer, estruturalmente, um sucesso real.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any

from sqlalchemy.orm import Session

from app.models.movimento_email_dispatch import MovimentoEmailDispatch
from app.services.auditoria import registrar_evento
from app.services.movimento_email import queue_repository as fila
from app.services.movimento_email.smtp_sender import EmailSender, EnvioEmailError

logger = logging.getLogger('reqsys.movimento_email.consumer')

ATOR_CONSUMER = 'movimento_email_consumer'


def _montar_mensagem(item: MovimentoEmailDispatch, *, remetente: str) -> EmailMessage:
    message = EmailMessage()
    message['From'] = remetente
    message['To'] = item.destinatarios
    message['Subject'] = item.assunto
    message['X-Correlation-ID'] = item.correlation_id
    message['X-ReqSys-Report-Type'] = 'prospeccao-movimento-diario'
    message.set_content(item.text_body, subtype='plain', charset='utf-8')
    message.add_alternative(item.html_body, subtype='html', charset='utf-8')
    return message


def consumir_fila_email_movimento(
    db: Session,
    sender: EmailSender,
    *,
    remetente: str,
    lote_max: int = fila.DEFAULT_LOTE_MAX,
    reserva_timeout_minutos: int = fila.DEFAULT_RESERVA_TIMEOUT_MINUTOS,
    dry_run: bool = False,
) -> dict[str, Any]:
    reservas_liberadas = fila.limpar_reservas_travadas(db, timeout_minutos=reserva_timeout_minutos)

    if dry_run:
        pendentes_preview = (
            db.query(MovimentoEmailDispatch)
            .filter(MovimentoEmailDispatch.status == fila.STATUS_PENDING)
            .order_by(MovimentoEmailDispatch.created_at.asc())
            .limit(lote_max)
            .all()
        )
        return {
            'dry_run': True,
            'enviado': False,
            'reservas_liberadas': reservas_liberadas,
            'total_pendentes_no_lote': len(pendentes_preview),
            'seriam_processados': [
                {'id': item.id, 'correlation_id': item.correlation_id, 'assunto': item.assunto}
                for item in pendentes_preview
            ],
        }

    lote = fila.reservar_lote(db, lote_max=lote_max)
    enviados = 0
    falhas = 0
    itens_processados: list[dict[str, Any]] = []

    for item in lote:
        try:
            message = _montar_mensagem(item, remetente=remetente)
            sender.enviar(message)
            fila.marcar_enviado(db, item)
            registrar_evento(db, item.correlation_id, ATOR_CONSUMER, 'MOVIMENTO_EMAIL_ENVIADO', 'movimento_email_dispatch', item.id)
            enviados += 1
            itens_processados.append({'id': item.id, 'correlation_id': item.correlation_id, 'status': fila.STATUS_SENT})
        except EnvioEmailError as exc:
            fila.marcar_erro(db, item, str(exc))
            registrar_evento(db, item.correlation_id, ATOR_CONSUMER, 'MOVIMENTO_EMAIL_FALHOU', 'movimento_email_dispatch', item.id)
            falhas += 1
            itens_processados.append({
                'id': item.id, 'correlation_id': item.correlation_id,
                'status': item.status, 'tentativas': item.retry_count,
            })

    return {
        'dry_run': False,
        'reservas_liberadas': reservas_liberadas,
        'processados': len(lote),
        'enviados': enviados,
        'falhas': falhas,
        'itens': itens_processados,
    }
