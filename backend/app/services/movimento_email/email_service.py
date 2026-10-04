"""Renderização HTML/texto do e-mail de Prospecção Movimento e montagem da
mensagem MIME (substitui o template SSRS legado — Funcionalidade #2861).

Reaproveita `EmailIdentity` de `email_mime_report_service.py` em vez de
duplicar o mesmo wrapper de `formataddr` para um segundo tipo de relatório.
"""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.email_mime_report_service import EmailIdentity
from app.services.movimento_email.models import ContextoEmailMovimento

_TEMPLATES_DIR = Path(__file__).resolve().parent / 'templates'

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(['html']),
)


def render_email_movimento_html(contexto: ContextoEmailMovimento) -> str:
    """Renderiza o template `email_movimento.html` com o contexto agregado."""
    template = _env.get_template('email_movimento.html')
    return template.render(
        data_referencia=contexto.data_referencia.isoformat(),
        correlation_id=contexto.correlation_id,
        fechamento=contexto.fechamento,
        pendencias_cadastro=contexto.pendencias_cadastro,
        pendencias_historicas=contexto.pendencias_historicas,
        pendencias_observacao=contexto.pendencias_observacao,
    )


def render_email_movimento_text(contexto: ContextoEmailMovimento) -> str:
    """Renderiza um fallback em texto puro para clientes de e-mail sem suporte a HTML."""
    linhas = [
        f'Prospecção Movimento — Portabilidade Consignado ({contexto.data_referencia.isoformat()})',
        '',
        'FECHAMENTO DIÁRIO',
        '------------------',
    ]
    if contexto.fechamento:
        linhas.extend(f'{item.indicador}: {item.valor} ({item.observacao})' for item in contexto.fechamento)
    else:
        linhas.append('Sem indicadores de fechamento para a data de referência.')

    linhas.extend(['', f'PENDÊNCIAS DE CADASTRAMENTO ({len(contexto.pendencias_cadastro)})', '-' * 40])
    if contexto.pendencias_cadastro:
        linhas.extend(
            f'{item.protocolo} | {item.cliente} | {item.cpf} | {item.pendencia} | '
            f'{item.dias_em_aberto} dias | {item.responsavel}'
            for item in contexto.pendencias_cadastro
        )
    else:
        linhas.append('Sem pendências de cadastramento em aberto.')

    linhas.extend(['', 'PENDÊNCIAS HISTÓRICAS', '----------------------'])
    if contexto.pendencias_historicas:
        linhas.extend(
            f'{item.periodo_referencia} | {item.pendencia} | {item.quantidade} ({item.percentual:.1f}%)'
            for item in contexto.pendencias_historicas
        )
    else:
        linhas.append('Sem histórico de pendências para o período.')

    linhas.extend(['', 'PENDÊNCIAS DE OBSERVAÇÃO/TRATAMENTO', '------------------------------------'])
    if contexto.pendencias_observacao:
        linhas.extend(
            f'{item.protocolo} | {item.tipo_inconsistencia} | {item.descricao} | {item.etapa}'
            for item in contexto.pendencias_observacao
        )
    else:
        linhas.append('Sem inconsistências de observação/tratamento pendentes.')

    linhas.extend(['', f'Correlation ID: {contexto.correlation_id}'])
    return '\n'.join(linhas)


def build_email_movimento_message(
    *,
    sender: EmailIdentity,
    recipients: Iterable[EmailIdentity],
    contexto: ContextoEmailMovimento,
) -> EmailMessage:
    """Monta a mensagem MIME (texto + HTML) pronta para envio/enfileiramento."""
    message = EmailMessage()
    message['From'] = sender.as_header()
    message['To'] = ', '.join(recipient.as_header() for recipient in recipients)
    message['Subject'] = (
        f'Prospecção Movimento — Resumo diário {contexto.data_referencia.isoformat()}'
    )
    message['X-Correlation-ID'] = contexto.correlation_id
    message['X-ReqSys-Report-Type'] = 'prospeccao-movimento-diario'

    message.set_content(render_email_movimento_text(contexto), subtype='plain', charset='utf-8')
    message.add_alternative(render_email_movimento_html(contexto), subtype='html', charset='utf-8')
    return message
