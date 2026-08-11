from __future__ import annotations

from scripts.governance.enterprise_runtime_governance_gates import ROOT, scan_content


def test_scan_content_nao_bloqueia_argumento_password_legitimo() -> None:
    payload = (
        "sender = SmtpEmailSender("
        + "pass"
        + "word=smtp_secret, use_tls=True)\n"
    )
    findings = scan_content(ROOT / "backend/app/api/movimento_email.py", payload)

    assert findings == []


def test_scan_content_bloqueia_connection_string_sql_server() -> None:
    findings = scan_content(
        ROOT / "backend/app/api/movimento_email.py",
        'dsn = "Server=prod-db.internal;Database=reqsys;User ID=svc"\n',
    )

    assert len(findings) == 1
    assert findings[0].code == "SEC_CONNECTION_STRING"
    assert findings[0].severity == "HIGH"
