from datetime import datetime

from app.services.email_report_template import (
    AlertaEmail,
    KpiEmail,
    LinhaProcessoEmail,
    RelatorioEmail,
    renderizar_relatorio_email,
)


def test_renderizar_relatorio_email_com_status_e_rastreabilidade():
    relatorio = RelatorioEmail(
        titulo="Relatorio Diario de Operacao",
        ambiente="producao",
        status_geral="warning",
        resumo_executivo="Operacao com degradacao parcial e sem parada total.",
        kpis=[KpiEmail("SLA", "92%", "warning", "Abaixo da meta de 95%")],
        alertas=[AlertaEmail("Fila elevada", "Fila acima do limite operacional", "warning")],
        processos=[LinhaProcessoEmail("Envio de e-mail", "Entregabilidade", 92, "warning")],
        correlation_id="corr-123",
        versao="v1.0.0",
        gerado_em=datetime(2026, 6, 22, 12, 0, 0),
    )

    html = renderizar_relatorio_email(relatorio)

    assert "Relatorio Diario de Operacao" in html
    assert "ATENCAO" in html
    assert "SLA" in html
    assert "Fila elevada" in html
    assert "Envio de e-mail" in html
    assert "corr-123" in html
    assert "<script" not in html.lower()
    assert "cdn" not in html.lower()


def test_renderizar_relatorio_email_escapa_html_de_entrada():
    relatorio = RelatorioEmail(
        titulo="<script>alert(1)</script>",
        ambiente="homologacao",
        status_geral="critical",
        resumo_executivo="Falha <b>critica</b>",
    )

    html = renderizar_relatorio_email(relatorio)

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Falha &lt;b&gt;critica&lt;/b&gt;" in html
    assert "<script>alert(1)</script>" not in html
