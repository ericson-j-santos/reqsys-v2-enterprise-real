#!/usr/bin/env python3
"""Build and optionally send a ReqSys HITL approval email through SMTP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape
from pathlib import Path
from urllib.parse import urlparse


def _github_url(value: str, field: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError(f"{field} deve ser uma URL HTTPS do GitHub")
    return value.strip()


def build_email(
    *,
    sender: str,
    recipient: str,
    request_title: str,
    control_id: str,
    summary: str,
    request_url: str,
    evidence_url: str | None,
) -> tuple[EmailMessage, str]:
    request_link = _github_url(request_url, "request_url")
    evidence_link = _github_url(evidence_url, "evidence_url") if evidence_url else request_link
    if "@" not in sender or "@" not in recipient:
        raise ValueError("sender e recipient devem ser enderecos de e-mail")
    if not request_title.strip() or not control_id.strip() or not summary.strip():
        raise ValueError("request_title, control_id e summary sao obrigatorios")

    canonical = {
        "request_title": request_title.strip(),
        "control_id": control_id.strip(),
        "summary": summary.strip(),
        "request_url": request_link,
        "evidence_url": evidence_link,
    }
    request_sha256 = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    correlation_id = f"hitl-email-{request_sha256[:16]}"

    plain = f"""ReqSys — aprovação humana necessária

Solicitação: {request_title.strip()}
Controle/Escopo: {control_id.strip()}
Resumo: {summary.strip()}
Evidências: {evidence_link}

Para decidir, abra {request_link} e registre um comentário autenticado:
- /approve <justificativa>
- /reject <justificativa>
- /adjust <justificativa>

A decisão exige ator humano com permissão de escrita, manutenção ou administração.
Correlation ID: {correlation_id}
production_touched=false
"""

    html = f"""<!doctype html>
<html lang="pt-BR">
<body style="margin:0;background:#f4f6f9;font-family:Arial,sans-serif;color:#111827;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;">
<tr><td align="center" style="padding:24px;">
<table role="presentation" width="680" cellpadding="0" cellspacing="0"
style="width:100%;max-width:680px;background:#ffffff;border:1px solid #e5e7eb;">
<tr><td style="background:#0f172a;color:#ffffff;padding:22px;">
<h1 style="margin:0;font-size:22px;">ReqSys — aprovação humana necessária</h1>
<p style="margin:8px 0 0;color:#cbd5e1;font-size:13px;">{escape(control_id.strip())}</p>
</td></tr>
<tr><td style="padding:22px;">
<h2 style="margin:0 0 12px;font-size:18px;">{escape(request_title.strip())}</h2>
<p style="font-size:14px;line-height:21px;">{escape(summary.strip())}</p>
<p style="font-size:13px;"><a href="{escape(evidence_link)}">Abrir pacote de evidências</a></p>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:20px 0;">
<tr>
<td style="padding-right:8px;">
<a href="{escape(request_link)}"
style="display:inline-block;background:#15803d;color:#ffffff;
text-decoration:none;padding:11px 16px;border-radius:5px;font-weight:bold;">Aprovar</a>
</td>
<td style="padding-right:8px;">
<a href="{escape(request_link)}"
style="display:inline-block;background:#b91c1c;color:#ffffff;
text-decoration:none;padding:11px 16px;border-radius:5px;font-weight:bold;">Rejeitar</a>
</td>
<td>
<a href="{escape(request_link)}"
style="display:inline-block;background:#b45309;color:#ffffff;
text-decoration:none;padding:11px 16px;border-radius:5px;font-weight:bold;">Solicitar ajuste</a>
</td>
</tr>
</table>
<p style="font-size:12px;line-height:18px;color:#475569;">
Os botões abrem a solicitação no GitHub. Registre <code>/approve</code>,
<code>/reject</code> ou <code>/adjust</code> acompanhado de justificativa.
</p>
</td></tr>
<tr><td style="background:#f8fafc;padding:14px;font-size:11px;color:#64748b;">
Correlation ID: {escape(correlation_id)}<br>
SHA-256: {escape(request_sha256)}<br>
production_touched=false
</td></tr>
</table>
</td></tr>
</table>
</body></html>"""

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"[ReqSys][Aprovação] {request_title.strip()}"
    message["X-Correlation-ID"] = correlation_id
    message["X-ReqSys-Request-SHA256"] = request_sha256
    message.set_content(plain)
    message.add_alternative(html, subtype="html")
    return message, request_sha256


def send_smtp(
    message: EmailMessage,
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    mode: str,
    timeout: float,
) -> None:
    context = ssl.create_default_context()
    if mode == "ssl":
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
        return
    with smtplib.SMTP(host, port, timeout=timeout) as smtp:
        smtp.ehlo()
        if mode == "starttls":
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)


def _env_smtp_port() -> int:
    value = (os.environ.get("HITL_SMTP_PORT") or "").strip()
    if not value:
        return 587
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("HITL_SMTP_PORT deve ser numerico") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and optionally send a ReqSys HITL email")
    parser.add_argument("--request-title", required=True)
    parser.add_argument("--control-id", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--request-url", required=True)
    parser.add_argument("--evidence-url")
    parser.add_argument("--sender", default=os.environ.get("HITL_EMAIL_FROM", "reqsys@example.invalid"))
    parser.add_argument("--recipient", default=os.environ.get("HITL_EMAIL_TO", "owner@example.invalid"))
    parser.add_argument("--smtp-host", default=os.environ.get("HITL_SMTP_HOST", ""))
    parser.add_argument("--smtp-port", type=int, default=_env_smtp_port())
    parser.add_argument("--smtp-username", default=os.environ.get("HITL_SMTP_USERNAME", ""))
    parser.add_argument("--smtp-password", default=os.environ.get("HITL_SMTP_PASSWORD", ""))
    parser.add_argument(
        "--smtp-mode",
        choices=["plain", "starttls", "ssl"],
        default=os.environ.get("HITL_SMTP_MODE") or "starttls",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--eml-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()

    message, request_sha256 = build_email(
        sender=args.sender,
        recipient=args.recipient,
        request_title=args.request_title,
        control_id=args.control_id,
        summary=args.summary,
        request_url=args.request_url,
        evidence_url=args.evidence_url,
    )
    args.eml_output.parent.mkdir(parents=True, exist_ok=True)
    args.eml_output.write_bytes(message.as_bytes())

    configured = all([args.smtp_host, args.smtp_username, args.smtp_password])
    sent = False
    error = None
    if not args.dry_run and configured:
        try:
            send_smtp(
                message,
                host=args.smtp_host,
                port=args.smtp_port,
                username=args.smtp_username,
                password=args.smtp_password,
                mode=args.smtp_mode,
                timeout=args.timeout,
            )
            sent = True
        except Exception as exc:  # noqa: BLE001 - normalized into evidence without leaking credentials
            error = f"{type(exc).__name__}: {exc}"

    report = {
        "schema_version": "1.0.0",
        "contract": "reqsys-hitl-email-notification",
        "recipient": args.recipient,
        "request_sha256": request_sha256,
        "smtp_configured": configured,
        "dry_run": args.dry_run,
        "sent": sent,
        "error": error,
        "production_touched": False,
    }
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.strict and not (sent or args.dry_run):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
