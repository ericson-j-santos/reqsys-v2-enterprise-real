"""Adapter de envio SMTP (ADR-010: timeout + retry + circuit breaker).

Porta (`EmailSender`) + implementação real (`SmtpEmailSender`). Nunca loga a
senha SMTP (ADR-002) — qualquer exceção do `smtplib` é mascarada antes de
subir para o chamador.
"""

from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.resilience import CircuitBreaker, call_with_retry

logger = logging.getLogger('reqsys.movimento_email.smtp')

_CIRCUIT = CircuitBreaker(name='movimento_email_smtp', failure_threshold=3, cooldown_seconds=60)

_PADRAO_SENHA = re.compile(r'(senha|password|pwd)["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', re.IGNORECASE)


class EnvioEmailError(RuntimeError):
    """Falha ao enviar e-mail via SMTP após as tentativas de retry."""


def _mascarar(detalhe: str) -> str:
    return _PADRAO_SENHA.sub(r'\1=[SEGREDO_REMOVIDO]', detalhe)[:500]


class EmailSender(Protocol):
    def enviar(self, message: EmailMessage) -> None: ...


class SmtpEmailSender:
    """Adapter real: envia via SMTP com STARTTLS. Credenciais resolvidas pelo
    chamador via `get_secret` (nunca hardcoded)."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        if not host:
            raise EnvioEmailError('SMTP host (MOVIMENTO_EMAIL_SMTP_HOST) não configurado')
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def _enviar_uma_vez(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout_seconds) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(message)

    def enviar(self, message: EmailMessage) -> None:
        try:
            call_with_retry(
                lambda: self._enviar_uma_vez(message),
                max_retries=self._max_retries,
                backoff_seconds=1.0,
                retry_on=(smtplib.SMTPException, OSError),
                circuit=_CIRCUIT,
            )
        except (smtplib.SMTPException, OSError) as exc:
            erro_mascarado = _mascarar(str(exc))
            logger.error('movimento_email_smtp_falhou erro=%s', erro_mascarado)
            raise EnvioEmailError(erro_mascarado) from exc
