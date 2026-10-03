#!/usr/bin/env python3
"""Notify real BACEN human-action changes without fabricating authority."""

from __future__ import annotations

import argparse
from email.message import EmailMessage
from html import escape
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from scripts.notificar_teams import DEFAULT_BASE_URL, enviar_mensagem
    from scripts.notify_hitl_approval_email import send_smtp
except ModuleNotFoundError:
    from notificar_teams import DEFAULT_BASE_URL, enviar_mensagem
    from notify_hitl_approval_email import send_smtp


def _github_url(value: str, field: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError(f"{field} must be an HTTPS GitHub URL")
    return value.strip()


def load_plan(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("plan must be an object")
    if document.get("contract") != "reqsys-bacen-human-action-issue-sync":
        raise ValueError("unsupported plan contract")
    return document


def build_notification(
    *,
    plan: dict[str, Any],
    repository: str,
    run_url: str,
    issues_url: str,
) -> dict[str, Any]:
    if "/" not in repository.strip():
        raise ValueError("repository must use owner/name")
    evidence_link = _github_url(run_url, "run_url")
    action_link = _github_url(issues_url, "issues_url")
    summary = plan.get("summary") or {}
    create_count = int(summary.get("create") or 0)
    update_count = int(summary.get("update") or 0)
    close_count = int(summary.get("close") or 0)
    operations = plan.get("operations") or []
    if not isinstance(operations, list):
        raise ValueError("operations must be a list")

    actionable_controls = sorted(
        {
            str(operation.get("control_id") or "").strip()
            for operation in operations
            if isinstance(operation, dict)
            and operation.get("action") in {"create", "update"}
            and str(operation.get("control_id") or "").strip()
        }
    )
    should_notify = create_count + update_count > 0
    controls_text = ", ".join(actionable_controls) if actionable_controls else "nenhum"
    text = "\n".join(
        [
            "ReqSys — ações formais BACEN atualizadas",
            f"Controles com ação nova/atualizada: {controls_text}",
            f"Issues criadas: {create_count}",
            f"Issues atualizadas/reabertas: {update_count}",
            f"Issues encerradas: {close_count}",
            "Aprovação, responsável pessoal e prazo continuam dependentes de autoridade real.",
            f"Abrir backlog formal: {action_link}",
            f"Evidência do run: {evidence_link}",
            "production_touched=false",
        ]
    )
    canonical = {
        "repository": repository.strip(),
        "run_url": evidence_link,
        "issues_url": action_link,
        "create": create_count,
        "update": update_count,
        "close": close_count,
        "controls": actionable_controls,
    }
    notification_sha256 = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-bacen-human-action-notification",
        "repository": repository.strip(),
        "should_notify": should_notify,
        "counts": {
            "create": create_count,
            "update": update_count,
            "close": close_count,
        },
        "actionable_controls": actionable_controls,
        "title": "ReqSys — ações formais BACEN requerem atenção",
        "text": text,
        "issues_url": action_link,
        "evidence_url": evidence_link,
        "notification_sha256": notification_sha256,
        "approvals_fabricated": False,
        "personal_assignees_fabricated": False,
        "due_dates_fabricated": False,
        "production_touched": False,
    }


def build_email(
    *,
    sender: str,
    recipient: str,
    notification: dict[str, Any],
) -> EmailMessage:
    if "@" not in sender or "@" not in recipient:
        raise ValueError("sender and recipient must be e-mail addresses")
    title = str(notification["title"])
    text = str(notification["text"])
    issues_url = str(notification["issues_url"])
    evidence_url = str(notification["evidence_url"])
    digest = str(notification["notification_sha256"])

    html = f"""<!doctype html>
<html lang="pt-BR">
<body style="margin:0;background:#f4f6f9;font-family:Arial,sans-serif;color:#111827;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:24px;">
<table role="presentation" width="680" cellpadding="0" cellspacing="0"
style="width:100%;max-width:680px;background:#fff;border:1px solid #e5e7eb;">
<tr><td style="background:#0f172a;color:#fff;padding:22px;">
<h1 style="margin:0;font-size:22px;">{escape(title)}</h1>
</td></tr>
<tr><td style="padding:22px;">
<p style="font-size:14px;line-height:22px;white-space:pre-line;">{escape(text)}</p>
<p><a href="{escape(issues_url)}">Abrir backlog formal no GitHub</a></p>
<p><a href="{escape(evidence_url)}">Abrir evidência do workflow</a></p>
<p style="font-size:12px;color:#475569;">
Nenhuma aprovação, pessoa responsável ou prazo foi criado pela automação.
</p>
</td></tr>
<tr><td style="background:#f8fafc;padding:14px;font-size:11px;color:#64748b;">
SHA-256: {escape(digest)}<br>production_touched=false
</td></tr>
</table>
</td></tr>
</table>
</body></html>"""

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = "[ReqSys][BACEN] Ações formais requerem atenção"
    message["X-ReqSys-Notification-SHA256"] = digest
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    return message


def execute_notification(
    *,
    notification: dict[str, Any],
    base_url: str,
    recipient_policy: str,
    delivery_mode: str,
    dry_run: bool,
    timeout: float,
    email_from: str,
    email_to: str,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    smtp_mode: str,
    eml_output: Path,
) -> dict[str, Any]:
    if not notification["should_notify"]:
        return {
            "should_notify": False,
            "teams": {"attempted": False},
            "email": {"attempted": False},
        }

    teams_result = enviar_mensagem(
        base_url=base_url,
        texto=str(notification["text"]),
        titulo=str(notification["title"]),
        modo="auto",
        destino_tipo="auto",
        destino_id=None,
        autor="reqsys-bacen-governance",
        permitir_fallback=False,
        dry_run=dry_run,
        timeout=timeout,
        recipient_policy=recipient_policy,
        delivery_mode=delivery_mode,
    )

    email_configured = all(
        [
            email_from.strip(),
            email_to.strip(),
            smtp_host.strip(),
            smtp_username.strip(),
            smtp_password,
        ]
    )
    email_sent = False
    email_error: str | None = None
    email_dry_run = bool(dry_run and email_from.strip() and email_to.strip())
    if email_from.strip() and email_to.strip():
        message = build_email(
            sender=email_from.strip(),
            recipient=email_to.strip(),
            notification=notification,
        )
        eml_output.parent.mkdir(parents=True, exist_ok=True)
        eml_output.write_bytes(message.as_bytes())
        if not dry_run and email_configured:
            try:
                send_smtp(
                    message,
                    host=smtp_host.strip(),
                    port=smtp_port,
                    username=smtp_username.strip(),
                    password=smtp_password,
                    mode=smtp_mode,
                    timeout=timeout,
                )
                email_sent = True
            except Exception as exc:  # noqa: BLE001
                email_error = type(exc).__name__

    return {
        "should_notify": True,
        "teams": {
            "attempted": True,
            "delivered": bool(teams_result.get("entregue")),
            "dry_run": bool(teams_result.get("dry_run")),
            "channel": teams_result.get("canal_usado"),
            "error": teams_result.get("erro") or teams_result.get("motivo"),
        },
        "email": {
            "attempted": bool(email_from.strip() and email_to.strip()),
            "configured": email_configured,
            "sent": email_sent,
            "dry_run": email_dry_run,
            "error": email_error,
        },
    }


def _smtp_port() -> int:
    value = (os.environ.get("HITL_SMTP_PORT") or "").strip()
    return int(value) if value else 587


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--issues-url", required=True)
    parser.add_argument("--base-url", default=os.environ.get("TEAMS_GATEWAY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--recipient-policy", default=os.environ.get("HITL_RECIPIENT_POLICY", "hitl-approvers"))
    parser.add_argument("--delivery-mode", default=os.environ.get("HITL_DELIVERY_MODE", "all"))
    parser.add_argument("--email-from", default=os.environ.get("HITL_EMAIL_FROM", ""))
    parser.add_argument("--email-to", default=os.environ.get("HITL_EMAIL_TO", ""))
    parser.add_argument("--smtp-host", default=os.environ.get("HITL_SMTP_HOST", ""))
    parser.add_argument("--smtp-port", type=int, default=_smtp_port())
    parser.add_argument("--smtp-username", default=os.environ.get("HITL_SMTP_USERNAME", ""))
    parser.add_argument("--smtp-password", default=os.environ.get("HITL_SMTP_PASSWORD", ""))
    parser.add_argument(
        "--smtp-mode",
        choices=["plain", "starttls", "ssl"],
        default=os.environ.get("HITL_SMTP_MODE") or "starttls",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--eml-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    notification = build_notification(
        plan=load_plan(args.plan),
        repository=args.repository,
        run_url=args.run_url,
        issues_url=args.issues_url,
    )
    delivery = execute_notification(
        notification=notification,
        base_url=args.base_url,
        recipient_policy=args.recipient_policy,
        delivery_mode=args.delivery_mode,
        dry_run=args.dry_run,
        timeout=args.timeout,
        email_from=args.email_from,
        email_to=args.email_to,
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        smtp_username=args.smtp_username,
        smtp_password=args.smtp_password,
        smtp_mode=args.smtp_mode,
        eml_output=args.eml_output,
    )
    report = {**notification, "delivery": delivery}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "BACEN human-action notification: "
        f"should_notify={notification['should_notify']} "
        f"create={notification['counts']['create']} "
        f"update={notification['counts']['update']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
