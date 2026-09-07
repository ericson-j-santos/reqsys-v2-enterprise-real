"""Seleção governada do provedor de envio da Prospecção Movimento.

Mantém SMTP por compatibilidade e permite Microsoft Graph como alvo preferencial
sem duplicar segredos: o Graph reutiliza AZURE_TENANT_ID/AZURE_CLIENT_ID/
AZURE_CLIENT_SECRET e exige apenas a caixa remetente autorizada.
"""

from __future__ import annotations

from email.utils import parseaddr
from typing import Any

from app.core.secrets import get_secret
from app.services.email_mime_report_service import EmailIdentity
from app.services.movimento_email.graph_sender import GraphEmailSender
from app.services.movimento_email.smtp_sender import EmailSender, EnvioEmailError, SmtpEmailSender

PROVEDOR_SMTP = 'smtp'
PROVEDOR_GRAPH = 'graph'
_PROVEDORES = {PROVEDOR_SMTP, PROVEDOR_GRAPH}


class ConfiguracaoEnvioError(EnvioEmailError):
    """Configuração ausente ou inválida antes de tentar o envio."""


def resolver_provedor_envio() -> str:
    provedor = (get_secret('MOVIMENTO_EMAIL_PROVIDER', PROVEDOR_SMTP) or PROVEDOR_SMTP).strip().lower()
    if provedor not in _PROVEDORES:
        raise ConfiguracaoEnvioError(
            f'MOVIMENTO_EMAIL_PROVIDER inválido: {provedor!r}; use smtp ou graph'
        )
    return provedor


def _endereco_graph() -> str:
    valor = (get_secret('MOVIMENTO_EMAIL_GRAPH_SENDER', '') or '').strip()
    _, endereco = parseaddr(valor)
    if not endereco or '@' not in endereco or '\n' in valor or '\r' in valor:
        raise ConfiguracaoEnvioError('MOVIMENTO_EMAIL_GRAPH_SENDER não configurado ou inválido')
    return endereco


def resolver_remetente_configurado(settings: Any, *, permitir_placeholder: bool = False) -> str:
    provedor = resolver_provedor_envio()
    if provedor == PROVEDOR_GRAPH:
        try:
            return EmailIdentity(_endereco_graph()).as_header()
        except ConfiguracaoEnvioError:
            if permitir_placeholder:
                return 'dry-run@example.invalid'
            raise

    valor = (settings.movimento_email_smtp_from or settings.movimento_email_smtp_user or '').strip()
    if not valor:
        if permitir_placeholder:
            return 'dry-run@example.invalid'
        raise ConfiguracaoEnvioError('MOVIMENTO_EMAIL_SMTP_FROM/USER não configurado')
    return EmailIdentity(valor).as_header()


def criar_sender_email_movimento(settings: Any) -> tuple[EmailSender, str, str]:
    provedor = resolver_provedor_envio()

    if provedor == PROVEDOR_GRAPH:
        faltantes = [
            nome
            for nome, valor in (
                ('AZURE_TENANT_ID', settings.azure_tenant_id),
                ('AZURE_CLIENT_ID', settings.azure_client_id),
                ('AZURE_CLIENT_SECRET', settings.azure_client_secret),
            )
            if not str(valor or '').strip()
        ]
        if faltantes:
            raise ConfiguracaoEnvioError('Microsoft Graph não configurado: ' + ', '.join(faltantes))
        endereco = _endereco_graph()
        sender = GraphEmailSender(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
            sender_user=endereco,
        )
        return sender, EmailIdentity(endereco).as_header(), provedor

    if not settings.movimento_email_smtp_host:
        raise ConfiguracaoEnvioError('MOVIMENTO_EMAIL_SMTP_HOST não configurado')
    remetente = resolver_remetente_configurado(settings)
    sender = SmtpEmailSender(
        host=settings.movimento_email_smtp_host,
        port=settings.movimento_email_smtp_port,
        username=settings.movimento_email_smtp_user,
        password=settings.movimento_email_smtp_password,
        use_tls=settings.movimento_email_smtp_use_tls,
    )
    return sender, remetente, provedor
