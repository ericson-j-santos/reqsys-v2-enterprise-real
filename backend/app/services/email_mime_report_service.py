"""Servico governado para relatorios executivos por e-mail MIME HTML.

Objetivo:
- preservar HTML/CSS em clientes compativeis;
- manter alternativa texto para clientes restritivos;
- carregar correlation_id na estrutura auditavel;
- evitar envio real em testes unitarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from typing import Iterable


@dataclass(frozen=True)
class EmailIdentity:
    """Identidade de e-mail com nome opcional."""

    email: str
    name: str | None = None

    def as_header(self) -> str:
        if self.name:
            return formataddr((self.name, self.email))
        return self.email


@dataclass(frozen=True)
class ExecutiveStatusCard:
    """Card executivo do relatorio."""

    label: str
    value: str
    status: str
    description: str


STATUS_COLORS: dict[str, dict[str, str]] = {
    "SUCCESS": {"background": "#ecfdf5", "border": "#10b981", "text": "#065f46"},
    "INFO": {"background": "#eff6ff", "border": "#3b82f6", "text": "#1e3a8a"},
    "WARNING": {"background": "#fffbeb", "border": "#f59e0b", "text": "#92400e"},
    "FAILURE": {"background": "#fef2f2", "border": "#ef4444", "text": "#991b1b"},
    "CRITICAL": {"background": "#450a0a", "border": "#dc2626", "text": "#ffffff"},
}


def _normalize_status(status: str) -> str:
    normalized = status.strip().upper()
    return normalized if normalized in STATUS_COLORS else "INFO"


def render_exec_report_html(*, title: str, subtitle: str, correlation_id: str, cards: Iterable[ExecutiveStatusCard]) -> str:
    """Renderiza HTML executivo com CSS inline compativel com Gmail/Outlook."""

    rendered_cards: list[str] = []
    for card in cards:
        status = _normalize_status(card.status)
        colors = STATUS_COLORS[status]
        rendered_cards.append(
            """
            <td style="width:33%;padding:8px;vertical-align:top;">
              <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;background:{background};border-left:6px solid {border};border-radius:8px;">
                <tr><td style="padding:14px;font-family:Arial,sans-serif;">
                  <div style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:{text};font-weight:bold;">{label}</div>
                  <div style="font-size:22px;line-height:28px;color:{text};font-weight:bold;margin-top:4px;">{value}</div>
                  <div style="font-size:12px;line-height:18px;color:{text};margin-top:6px;">{description}</div>
                </td></tr>
              </table>
            </td>
            """.format(
                background=colors["background"],
                border=colors["border"],
                text=colors["text"],
                label=escape(card.label),
                value=escape(card.value),
                description=escape(card.description),
            )
        )

    return """
<!doctype html>
<html lang="pt-BR">
  <body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;color:#111827;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f4f6f9;border-collapse:collapse;">
      <tr>
        <td align="center" style="padding:24px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="900" style="max-width:900px;width:100%;background:#ffffff;border-collapse:collapse;border:1px solid #e5e7eb;">
            <tr>
              <td style="background:#0f172a;color:#ffffff;padding:24px;font-family:Arial,sans-serif;">
                <h1 style="margin:0;font-size:24px;line-height:30px;">{title}</h1>
                <p style="margin:8px 0 0 0;color:#cbd5e1;font-size:14px;line-height:20px;">{subtitle}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:20px;">
                <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;"><tr>{cards}</tr></table>
                <h2 style="font-size:18px;margin:24px 0 12px 0;color:#111827;">Evidencia operacional</h2>
                <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;border:1px solid #cbd5e1;background:#f8fafc;">
                  <tr><td style="padding:14px;font-size:13px;line-height:20px;">
                    <strong>Correlation ID:</strong> {correlation_id}<br>
                    <strong>Formato:</strong> MIME multipart/alternative com HTML e texto fallback<br>
                    <strong>Governanca:</strong> CSS inline, rastreabilidade e compatibilidade executiva
                  </td></tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="background:#111827;color:#cbd5e1;padding:14px;font-size:12px;line-height:18px;">
                REQSYS Runtime Governance Platform • Auditoria ativa • Rastreabilidade habilitada
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".format(
        title=escape(title),
        subtitle=escape(subtitle),
        cards="".join(rendered_cards),
        correlation_id=escape(correlation_id),
    )


def render_exec_report_text(*, title: str, subtitle: str, correlation_id: str, cards: Iterable[ExecutiveStatusCard]) -> str:
    """Renderiza fallback texto para clientes sem HTML."""

    lines = [title, subtitle, "", "STATUS", "------"]
    for card in cards:
        lines.append(f"[{_normalize_status(card.status)}] {card.label}: {card.value} - {card.description}")
    lines.extend(["", f"Correlation ID: {correlation_id}", "Formato: texto fallback de MIME multipart/alternative"])
    return "\n".join(lines)


def build_exec_report_message(
    *,
    sender: EmailIdentity,
    recipients: Iterable[EmailIdentity],
    subject: str,
    title: str,
    subtitle: str,
    correlation_id: str,
    cards: Iterable[ExecutiveStatusCard],
) -> EmailMessage:
    """Monta mensagem MIME com texto e HTML preservado."""

    cards_list = list(cards)
    message = EmailMessage()
    message["From"] = sender.as_header()
    message["To"] = ", ".join(recipient.as_header() for recipient in recipients)
    message["Subject"] = subject
    message["X-Correlation-ID"] = correlation_id
    message["X-ReqSys-Report-Type"] = "executive-runtime-governance"

    text_body = render_exec_report_text(title=title, subtitle=subtitle, correlation_id=correlation_id, cards=cards_list)
    html_body = render_exec_report_html(title=title, subtitle=subtitle, correlation_id=correlation_id, cards=cards_list)

    message.set_content(text_body, subtype="plain", charset="utf-8")
    message.add_alternative(html_body, subtype="html", charset="utf-8")
    return message
