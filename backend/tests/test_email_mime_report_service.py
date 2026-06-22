from email.message import EmailMessage

from app.services.email_mime_report_service import (
    EmailIdentity,
    ExecutiveStatusCard,
    build_exec_report_message,
    render_exec_report_html,
    render_exec_report_text,
)


def _cards():
    return [
        ExecutiveStatusCard(
            label="Status Operacional",
            value="SUCCESS",
            status="SUCCESS",
            description="Fluxo validado com evidencia.",
        ),
        ExecutiveStatusCard(
            label="Monitoramento",
            value="ATIVO",
            status="INFO",
            description="Analise inteligente habilitada.",
        ),
        ExecutiveStatusCard(
            label="Severidade",
            value="INFORMATIVA",
            status="WARNING",
            description="Sem acao critica imediata.",
        ),
    ]


def test_render_exec_report_html_preserva_cores_inline_e_correlation_id():
    html = render_exec_report_html(
        title="REQSYS • Relatorio Executivo Operacional",
        subtitle="Monitoramento Inteligente",
        correlation_id="REQSYS-MIME-HTML-TEST-001",
        cards=_cards(),
    )

    assert "REQSYS-MIME-HTML-TEST-001" in html
    assert "#ecfdf5" in html
    assert "#10b981" in html
    assert "#eff6ff" in html
    assert "#3b82f6" in html
    assert "#fffbeb" in html
    assert "#f59e0b" in html
    assert "Content-Type:" not in html
    assert "MIME-Version:" not in html


def test_render_exec_report_text_cria_fallback_sem_html():
    text = render_exec_report_text(
        title="REQSYS",
        subtitle="Fallback",
        correlation_id="REQSYS-MIME-HTML-TEST-002",
        cards=_cards(),
    )

    assert "REQSYS-MIME-HTML-TEST-002" in text
    assert "[SUCCESS] Status Operacional: SUCCESS" in text
    assert "<table" not in text
    assert "#10b981" not in text


def test_build_exec_report_message_cria_multipart_alternative_com_headers_auditaveis():
    message = build_exec_report_message(
        sender=EmailIdentity(email="noreply@reqsys.local", name="ReqSys Runtime"),
        recipients=[EmailIdentity(email="ericson.takay@gmail.com", name="Ericson")],
        subject="[REQSYS] Relatorio Executivo Operacional",
        title="REQSYS • Relatorio Executivo Operacional",
        subtitle="Runtime Governance",
        correlation_id="REQSYS-MIME-HTML-TEST-003",
        cards=_cards(),
    )

    assert isinstance(message, EmailMessage)
    assert message["X-Correlation-ID"] == "REQSYS-MIME-HTML-TEST-003"
    assert message["X-ReqSys-Report-Type"] == "executive-runtime-governance"
    assert message.is_multipart()

    parts = list(message.iter_parts())
    content_types = [part.get_content_type() for part in parts]

    assert content_types == ["text/plain", "text/html"]
    assert "REQSYS-MIME-HTML-TEST-003" in parts[0].get_content()
    assert "#10b981" in parts[1].get_content()
    assert "border-left:6px" in parts[1].get_content()
