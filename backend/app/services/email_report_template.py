"""Template HTML responsivo para relatórios operacionais por e-mail.

Objetivo:
- Transformar relatórios tabulares em comunicação executiva por status.
- Manter compatibilidade com Outlook/Gmail usando HTML com CSS inline.
- Evitar JavaScript, CDN, SVG dinâmico e dependências externas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from typing import Iterable, Literal

Status = Literal["success", "warning", "critical", "info", "processing"]

_STATUS_STYLE: dict[Status, dict[str, str]] = {
    "success": {"label": "NORMAL", "bg": "#0F7B3F", "fg": "#FFFFFF", "soft": "#E8F5EE"},
    "warning": {"label": "ATENCAO", "bg": "#B85C00", "fg": "#FFFFFF", "soft": "#FFF3E0"},
    "critical": {"label": "CRITICO", "bg": "#B42318", "fg": "#FFFFFF", "soft": "#FDECEC"},
    "info": {"label": "INFORMATIVO", "bg": "#005CA9", "fg": "#FFFFFF", "soft": "#EAF3FC"},
    "processing": {"label": "PROCESSANDO", "bg": "#5B5F97", "fg": "#FFFFFF", "soft": "#F0F1FA"},
}


@dataclass(frozen=True)
class KpiEmail:
    titulo: str
    valor: str
    status: Status = "info"
    detalhe: str = ""


@dataclass(frozen=True)
class AlertaEmail:
    titulo: str
    descricao: str
    status: Status = "warning"


@dataclass(frozen=True)
class LinhaProcessoEmail:
    processo: str
    indicador: str
    percentual: int
    status: Status
    detalhe: str = ""


@dataclass(frozen=True)
class RelatorioEmail:
    titulo: str
    ambiente: str
    status_geral: Status
    resumo_executivo: str
    kpis: list[KpiEmail] = field(default_factory=list)
    alertas: list[AlertaEmail] = field(default_factory=list)
    processos: list[LinhaProcessoEmail] = field(default_factory=list)
    correlation_id: str = "nao-informado"
    versao: str = "v1"
    gerado_em: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _badge(status: Status, texto: str | None = None) -> str:
    style = _STATUS_STYLE[status]
    label = texto or style["label"]
    return (
        f'<span style="display:inline-block;background:{style["bg"]};color:{style["fg"]};'
        'padding:5px 10px;border-radius:999px;font-size:12px;font-weight:700;'
        'letter-spacing:.2px;text-transform:uppercase;">'
        f'{escape(label)}</span>'
    )


def _progress(percentual: int, status: Status) -> str:
    safe_value = max(0, min(100, int(percentual)))
    color = _STATUS_STYLE[status]["bg"]
    return (
        '<div style="background:#E5E7EB;border-radius:8px;height:10px;width:100%;overflow:hidden;">'
        f'<div style="background:{color};width:{safe_value}%;height:10px;border-radius:8px;"></div>'
        '</div>'
    )


def _render_kpis(kpis: Iterable[KpiEmail]) -> str:
    cards = []
    for kpi in kpis:
        style = _STATUS_STYLE[kpi.status]
        cards.append(
            '<td style="width:25%;padding:8px;vertical-align:top;">'
            f'<div style="border:1px solid #E5E7EB;border-left:5px solid {style["bg"]};border-radius:12px;padding:14px;background:#FFFFFF;">'
            f'<div style="font-size:12px;color:#667085;font-weight:700;text-transform:uppercase;">{escape(kpi.titulo)}</div>'
            f'<div style="font-size:24px;color:#101828;font-weight:800;margin-top:6px;">{escape(kpi.valor)}</div>'
            f'<div style="font-size:12px;color:#667085;margin-top:4px;">{escape(kpi.detalhe)}</div>'
            '</div></td>'
        )
    if not cards:
        return ""
    rows = []
    for index in range(0, len(cards), 4):
        rows.append(f'<tr>{"".join(cards[index:index + 4])}</tr>')
    return '<table role="presentation" style="width:100%;border-collapse:collapse;">' + ''.join(rows) + '</table>'


def _render_alertas(alertas: Iterable[AlertaEmail]) -> str:
    items = []
    for alerta in alertas:
        style = _STATUS_STYLE[alerta.status]
        items.append(
            f'<tr><td style="padding:10px;border-bottom:1px solid #EAECF0;background:{style["soft"]};">'
            f'{_badge(alerta.status)} '
            f'<strong style="color:#101828;">{escape(alerta.titulo)}</strong>'
            f'<div style="color:#475467;font-size:13px;margin-top:4px;">{escape(alerta.descricao)}</div>'
            '</td></tr>'
        )
    if not items:
        return '<p style="color:#475467;margin:0;">Nenhum alerta crítico no período.</p>'
    return '<table role="presentation" style="width:100%;border-collapse:collapse;border-radius:12px;overflow:hidden;">' + ''.join(items) + '</table>'


def _render_processos(processos: Iterable[LinhaProcessoEmail]) -> str:
    rows = []
    for item in processos:
        rows.append(
            '<tr>'
            f'<td style="padding:10px;border-bottom:1px solid #EAECF0;color:#101828;font-weight:700;">{escape(item.processo)}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #EAECF0;color:#475467;">{escape(item.indicador)}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #EAECF0;width:180px;">{_progress(item.percentual, item.status)}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #EAECF0;text-align:right;">{_badge(item.status, str(item.percentual) + "%")}</td>'
            '</tr>'
        )
    if not rows:
        return ""
    return (
        '<table role="presentation" style="width:100%;border-collapse:collapse;background:#FFFFFF;border:1px solid #EAECF0;border-radius:12px;overflow:hidden;">'
        '<tr style="background:#F9FAFB;">'
        '<th align="left" style="padding:10px;color:#475467;font-size:12px;text-transform:uppercase;">Processo</th>'
        '<th align="left" style="padding:10px;color:#475467;font-size:12px;text-transform:uppercase;">Indicador</th>'
        '<th align="left" style="padding:10px;color:#475467;font-size:12px;text-transform:uppercase;">Evolucao</th>'
        '<th align="right" style="padding:10px;color:#475467;font-size:12px;text-transform:uppercase;">Status</th>'
        '</tr>'
        + ''.join(rows)
        + '</table>'
    )


def renderizar_relatorio_email(relatorio: RelatorioEmail) -> str:
    """Renderiza HTML autocontido e compatível com clientes de e-mail."""
    status = _STATUS_STYLE[relatorio.status_geral]
    gerado = relatorio.gerado_em.strftime("%d/%m/%Y %H:%M:%S UTC")
    return f"""
<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F2F4F7;font-family:Arial,Helvetica,sans-serif;color:#101828;">
  <table role="presentation" style="width:100%;border-collapse:collapse;background:#F2F4F7;padding:0;margin:0;">
    <tr><td align="center" style="padding:24px 12px;">
      <table role="presentation" style="max-width:760px;width:100%;border-collapse:collapse;background:#FFFFFF;border-radius:16px;overflow:hidden;border:1px solid #EAECF0;">
        <tr>
          <td style="background:{status['bg']};color:{status['fg']};padding:24px;">
            <div style="font-size:12px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;">Relatorio operacional</div>
            <h1 style="margin:6px 0 10px 0;font-size:24px;line-height:1.25;">{escape(relatorio.titulo)}</h1>
            <div>{_badge(relatorio.status_geral, status['label'])}</div>
          </td>
        </tr>
        <tr><td style="padding:20px 24px;background:#FFFFFF;">
          <p style="margin:0;color:#475467;font-size:14px;line-height:1.6;">{escape(relatorio.resumo_executivo)}</p>
        </td></tr>
        <tr><td style="padding:0 16px 16px 16px;">{_render_kpis(relatorio.kpis)}</td></tr>
        <tr><td style="padding:20px 24px;background:#F9FAFB;">
          <h2 style="margin:0 0 10px 0;font-size:16px;">Alertas prioritarios</h2>
          {_render_alertas(relatorio.alertas)}
        </td></tr>
        <tr><td style="padding:20px 24px;background:#FFFFFF;">
          <h2 style="margin:0 0 10px 0;font-size:16px;">Indicadores por processo</h2>
          {_render_processos(relatorio.processos)}
        </td></tr>
        <tr><td style="padding:16px 24px;background:#101828;color:#D0D5DD;font-size:12px;line-height:1.6;">
          Ambiente: {escape(relatorio.ambiente)}<br>
          Versao: {escape(relatorio.versao)}<br>
          Correlation-ID: {escape(relatorio.correlation_id)}<br>
          Gerado em: {escape(gerado)}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
""".strip()
