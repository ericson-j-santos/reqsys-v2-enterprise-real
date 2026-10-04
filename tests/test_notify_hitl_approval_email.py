from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.notify_hitl_approval_email import build_email


def test_build_email_contains_html_actions_and_audit_headers():
    issue_url = "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1111"
    message, request_hash = build_email(
        sender="reqsys@example.com",
        recipient="owner@example.com",
        request_title="Aprovar fluxo HITL",
        control_id="REQSYS-HITL-001",
        summary="Validar o novo fluxo de aprovacao.",
        request_url=issue_url,
        evidence_url=f"{issue_url}#evidence",
    )
    html_part = next(part for part in message.iter_parts() if part.get_content_type() == "text/html")
    html = html_part.get_content()
    assert "Aprovar" in html
    assert "Rejeitar" in html
    assert "Solicitar ajuste" in html
    assert message["X-ReqSys-Request-SHA256"] == request_hash
    assert len(request_hash) == 64


def test_build_email_rejects_invalid_recipient_or_url():
    with pytest.raises(ValueError):
        build_email(
            sender="reqsys@example.com",
            recipient="invalid",
            request_title="Aprovar fluxo HITL",
            control_id="REQSYS-HITL-001",
            summary="Validar o novo fluxo.",
            request_url="https://github.com/org/repo/issues/1",
            evidence_url=None,
        )
    with pytest.raises(ValueError):
        build_email(
            sender="reqsys@example.com",
            recipient="owner@example.com",
            request_title="Aprovar fluxo HITL",
            control_id="REQSYS-HITL-001",
            summary="Validar o novo fluxo.",
            request_url="javascript:alert(1)",
            evidence_url=None,
        )
