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
from app.services.movimento_email.smtp_sender import (
    EmailSender,
    EnvioEmailError,
    SmtpEmailSender,
)

PROVEDOR_SMTP = 'smtp'
PROVEDOR_GRAPH = 'graph'
_PROVEDORES = {PROVEDOR_SMTP, PROVEDOR_GRAPH}
_SMTP_LOCAL_SINK_HOSTS = {'localhost', '127.0.0.1', '::1', 'mailhog', 'mailpit'}


class ConfiguracaoEnvioError(EnvioEmailError):
    """Configuração ausente ou inválida antes de tentar o envio."""


def avaliar_prontidao_entrega_externa(settings: Any) -> dict[str, Any]:
    """Avalia se o transporte configurado pode sair do ambiente local.

    Coletores como MailHog são provedores SMTP válidos para desenvolvimento,
    mas não constituem transporte externo nem evidência de entrega.
    """
    provedor = resolver_provedor_envio()
    if provedor == PROVEDOR_GRAPH:
        tenant_id, client_id, client_secret = _credenciais_graph(settings)
        configurado = all(
            str(valor or '').strip()
            for valor in (
                tenant_id,
                client_id,
                client_secret,
                get_secret('MOVIMENTO_EMAIL_GRAPH_SENDER', ''),
            )
        )
        return {
            'provider': provedor,
            'external_delivery_capable': configurado,
            'reason': 'ready' if configurado else 'graph_configuration_incomplete',
        }

    host = str(settings.movimento_email_smtp_host or '').strip().lower().rstrip('.')
    remetente = str(settings.movimento_email_smtp_from or settings.movimento_email_smtp_user or '').lower()
    coletor_local = host in _SMTP_LOCAL_SINK_HOSTS or remetente.endswith(('@localhost>', '@localhost'))
    configurado = bool(host) and not coletor_local
    return {
        'provider': provedor,
        'external_delivery_capable': configurado,
        'reason': 'ready' if configurado else ('local_sink_configured' if coletor_local else 'smtp_configuration_incomplete'),
    }


def _credenciais_graph(settings: Any) -> tuple[str, str, str]:
    """Prefere a identidade segregada de e-mail e preserva compatibilidade."""
    tenant_id = str(getattr(settings, 'movimento_email_graph_tenant_id', '') or '').strip()
    client_id = str(getattr(settings, 'movimento_email_graph_client_id', '') or '').strip()
    client_secret = str(getattr(settings, 'movimento_email_graph_client_secret', '') or '')
    if tenant_id or client_id or client_secret:
        return tenant_id, client_id, client_secret
    return (
        str(settings.azure_tenant_id or '').strip(),
        str(settings.azure_client_id or '').strip(),
        str(settings.azure_client_secret or ''),
    )


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
        tenant_id, client_id, client_secret = _credenciais_graph(settings)
        faltantes = [
            nome
            for nome, valor in (
                ('MOVIMENTO_EMAIL_GRAPH_TENANT_ID', tenant_id),
                ('MOVIMENTO_EMAIL_GRAPH_CLIENT_ID', client_id),
                ('MOVIMENTO_EMAIL_GRAPH_CLIENT_SECRET', client_secret),
            )
            if not str(valor or '').strip()
        ]
        if faltantes:
            raise ConfiguracaoEnvioError('Microsoft Graph não configurado: ' + ', '.join(faltantes))
        endereco = _endereco_graph()
        sender = GraphEmailSender(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
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
