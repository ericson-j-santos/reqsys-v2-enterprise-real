from __future__ import annotations

from email.message import EmailMessage

from app.core.config import settings
from app.schemas.report_builder_delivery import ReportBuilderEmailRequest
from app.services.movimento_email.sender_factory import (
    criar_sender_email_movimento,
    resolver_provedor_envio,
    resolver_remetente_configurado,
)
from app.services.paginated_report_factory import gerar_paginated_report


def _montar_mensagem(
    *,
    payload: ReportBuilderEmailRequest,
    remetente: str,
    correlation_id: str,
    definition_sha256: str,
    rdl_xml: str,
) -> EmailMessage:
    report_name = payload.report.report_name
    display_name = payload.report.display_name
    filename = f'{report_name}.rdl'
    destinatarios = [str(item) for item in payload.recipients]

    message = EmailMessage()
    message['From'] = remetente
    message['To'] = ', '.join(destinatarios)
    message['Subject'] = payload.subject or f'ReqSys Report Builder — {display_name}'
    message['X-Correlation-ID'] = correlation_id
    message['X-Report-SHA256'] = definition_sha256

    corpo = payload.body or (
        f'Relatório {display_name} gerado pela aplicação ReqSys Report Builder.\n\n'
        f'Correlation ID: {correlation_id}\n'
        f'SHA-256 da definição RDL: {definition_sha256}\n'
        f'Anexo: {filename}\n'
    )
    message.set_content(corpo)
    message.add_attachment(
        rdl_xml.encode('utf-8'),
        maintype='application',
        subtype='xml',
        filename=filename,
    )
    return message


def gerar_e_enviar_relatorio(payload: ReportBuilderEmailRequest) -> dict:
    # A geração é sempre isolada de publicação Fabric. O dry_run abaixo controla
    # exclusivamente a escrita externa do e-mail.
    report_request = payload.report.model_copy(update={'dry_run': True})
    report = gerar_paginated_report(report_request)
    correlation_id = report['correlation_id']
    provider = resolver_provedor_envio()

    if payload.dry_run:
        remetente = resolver_remetente_configurado(settings, permitir_placeholder=True)
        message = _montar_mensagem(
            payload=payload,
            remetente=remetente,
            correlation_id=correlation_id,
            definition_sha256=report['definition_sha256'],
            rdl_xml=report['rdl_xml'],
        )
        status = 'planned'
        external_write_performed = False
    else:
        sender, remetente, provider = criar_sender_email_movimento(settings)
        message = _montar_mensagem(
            payload=payload,
            remetente=remetente,
            correlation_id=correlation_id,
            definition_sha256=report['definition_sha256'],
            rdl_xml=report['rdl_xml'],
        )
        sender.enviar(message)
        status = 'sent'
        external_write_performed = True

    return {
        'schema_version': '1.0.0',
        'capability': 'ReqSys Report Builder Email Delivery',
        'status': status,
        'correlation_id': correlation_id,
        'report': {
            'report_name': report['report_name'],
            'display_name': report['display_name'],
            'target_environment': report['target_environment'],
            'definition_sha256': report['definition_sha256'],
            'attachment_name': f"{report['report_name']}.rdl",
        },
        'delivery': {
            'provider': provider,
            'sender': remetente,
            'recipients': [str(item) for item in payload.recipients],
            'external_write_performed': external_write_performed,
        },
    }
