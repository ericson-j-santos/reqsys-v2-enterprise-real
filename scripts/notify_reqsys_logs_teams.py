#!/usr/bin/env python3
"""Envia ao Teams resumos seguros de falhas e logs operacionais do ReqSys."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import uuid

DEFAULT_API_URL = "https://api.github.com"
DEFAULT_POLICY = "reqsys-operations"
_MAX_GITHUB_PAGES = 5
_MAX_CARD_DETAILS = 8
_RETRYABLE_HTTP = {429, 500, 502, 503, 504}
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:token|secret|password|passwd|api[_-]?key)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(https?://[^\s?]+\?[^\s]*?(?:token|sig|signature|key)=)[^&\s]+"),
)
_EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")


@dataclass(frozen=True)
class LogEvent:
    source: str
    environment: str
    severity: str
    status: str
    summary: str
    details: tuple[str, ...]
    run_url: str | None
    workflow: str | None
    run_id: str | None
    correlation_id: str


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def redact_text(value: str) -> str:
    """Remove credenciais e identificadores pessoais comuns de texto operacional."""
    sanitized = value.replace("\x00", " ")
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    sanitized = _EMAIL_PATTERN.sub("[EMAIL_REDACTED]", sanitized)
    return sanitized


def sanitize_for_evidence(value: Any) -> Any:
    """Remove dados sensíveis de estruturas retornadas por provedores externos."""
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in {
                "destino_id",
                "destination_id",
                "recipient",
                "recipients",
                "to",
            }:
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = sanitize_for_evidence(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_evidence(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_evidence(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def normalize_details(
    values: list[str] | tuple[str, ...],
    *,
    max_lines: int = 20,
    max_chars: int = 500,
) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in values:
        for line in str(raw).splitlines():
            clean = " ".join(redact_text(line).split())
            if not clean:
                continue
            normalized.append(clean[:max_chars])
            if len(normalized) >= max_lines:
                return tuple(normalized)
    return tuple(normalized)


def fetch_github_jobs(
    *,
    repository: str,
    run_id: str,
    token: str,
    api_url: str = DEFAULT_API_URL,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    if not repository or not run_id or not token:
        raise ValueError("repository, run_id e token sao obrigatorios para consultar jobs do GitHub")

    jobs: list[dict[str, Any]] = []
    for page in range(1, _MAX_GITHUB_PAGES + 1):
        endpoint = (
            f"{api_url.rstrip('/')}/repos/{repository}/actions/runs/{run_id}/jobs"
            f"?per_page=100&page={page}"
        )
        request = Request(
            endpoint,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "reqsys-log-teams-notifier/1.1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:500]
            raise RuntimeError(f"github_http_{exc.code}: {redact_text(detail)}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"github_jobs_unavailable: {redact_text(str(exc))}") from exc

        page_jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        if not isinstance(page_jobs, list):
            raise RuntimeError("github_jobs_payload_invalid")
        jobs.extend(job for job in page_jobs if isinstance(job, dict))
        if len(page_jobs) < 100:
            break
    return jobs


def summarize_failed_jobs(jobs: list[dict[str, Any]]) -> tuple[str, ...]:
    details: list[str] = []
    for job in jobs:
        conclusion = str(job.get("conclusion") or "unknown").lower()
        if conclusion in {"success", "skipped", "neutral"}:
            continue
        job_name = str(job.get("name") or "job sem nome")
        details.append(f"Job: {job_name} — {conclusion}")
        steps = job.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                step_conclusion = str(step.get("conclusion") or "").lower()
                if step_conclusion in {"failure", "cancelled", "timed_out", "action_required"}:
                    details.append(f"Etapa: {step.get('name') or 'sem nome'} — {step_conclusion}")
    return normalize_details(details, max_lines=25)


def _safe_github_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return None
    return value.strip()


def _severity_label(value: str) -> str:
    return {
        "critical": "CRÍTICO",
        "error": "ERRO",
        "warning": "ATENÇÃO",
    }.get(value.strip().lower(), value.strip().upper() or "ALERTA")


def _severity_color(value: str) -> str:
    return "Warning" if value.strip().lower() == "warning" else "Attention"


def _status_label(value: str) -> str:
    return {
        "cancelled": "Cancelado",
        "failure": "Falha",
        "timed_out": "Tempo excedido",
        "action_required": "Ação necessária",
        "reported": "Reportado",
    }.get(value.strip().lower(), value.strip().replace("_", " ").title() or "Desconhecido")


def build_message(event: LogEvent) -> str:
    lines = [
        f"Status: {_status_label(event.status)}",
        f"Severidade: {_severity_label(event.severity)}",
        f"Origem: {event.source}",
        f"Ambiente/branch: {event.environment}",
        f"Resumo: {redact_text(event.summary)}",
        f"Correlation ID: {event.correlation_id}",
    ]
    if event.workflow:
        lines.append(f"Workflow: {redact_text(event.workflow)}")
    if event.run_id:
        lines.append(f"Run ID: {event.run_id}")
    if event.details:
        lines.append("Falhas identificadas:")
        lines.extend(f"- {line}" for line in event.details)
    if _safe_github_url(event.run_url):
        lines.append(f"Evidencia: {event.run_url}")
    lines.append(
        "Observacao: o Teams recebe somente resumo sanitizado; "
        "logs brutos permanecem no sistema de origem."
    )
    return "\n".join(lines)


def build_adaptive_card(event: LogEvent) -> dict[str, Any]:
    facts = [
        {"title": "Status", "value": _status_label(event.status)},
        {"title": "Severidade", "value": _severity_label(event.severity)},
        {"title": "Ambiente", "value": event.environment},
        {"title": "Origem", "value": event.source},
    ]
    if event.workflow:
        facts.append({"title": "Workflow", "value": event.workflow})
    if event.run_id:
        facts.append({"title": "Run ID", "value": event.run_id})
    facts.append({"title": "Correlation ID", "value": event.correlation_id})

    body: list[dict[str, Any]] = [
        {
            "type": "Container",
            "style": "emphasis",
            "bleed": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": "ReqSys · Alerta operacional",
                    "weight": "Bolder",
                    "size": "Large",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": f"{_severity_label(event.severity)} · {event.environment}",
                    "weight": "Bolder",
                    "color": _severity_color(event.severity),
                    "spacing": "Small",
                    "wrap": True,
                },
            ],
        },
        {
            "type": "TextBlock",
            "text": redact_text(event.summary),
            "size": "Medium",
            "weight": "Bolder",
            "spacing": "Medium",
            "wrap": True,
        },
        {
            "type": "FactSet",
            "spacing": "Medium",
            "facts": facts,
        },
    ]

    if event.details:
        visible_details = event.details[:_MAX_CARD_DETAILS]
        detail_items: list[dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": "Falhas identificadas",
                "weight": "Bolder",
                "wrap": True,
            }
        ]
        detail_items.extend(
            {
                "type": "TextBlock",
                "text": f"• {line}",
                "spacing": "Small",
                "wrap": True,
            }
            for line in visible_details
        )
        hidden_count = len(event.details) - len(visible_details)
        if hidden_count > 0:
            detail_items.append(
                {
                    "type": "TextBlock",
                    "text": f"+ {hidden_count} item(ns) adicional(is) no GitHub Actions",
                    "isSubtle": True,
                    "spacing": "Small",
                    "wrap": True,
                }
            )
        body.append(
            {
                "type": "Container",
                "style": "attention",
                "spacing": "Medium",
                "items": detail_items,
            }
        )

    body.append(
        {
            "type": "TextBlock",
            "text": (
                "O cartão contém somente um resumo sanitizado. "
                "Os logs completos permanecem no GitHub Actions."
            ),
            "isSubtle": True,
            "spacing": "Medium",
            "wrap": True,
        }
    )

    card: dict[str, Any] = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "msteams": {"width": "Full"},
        "body": body,
    }
    run_url = _safe_github_url(event.run_url)
    if run_url:
        card["actions"] = [
            {
                "type": "Action.OpenUrl",
                "title": "Abrir execução no GitHub",
                "url": run_url,
            }
        ]
    return card


def _send_adaptive_webhook(
    *,
    webhook_url: str,
    recipient: str,
    title: str,
    message: str,
    adaptive_card: dict[str, Any],
    correlation_id: str,
    timeout: float,
    dry_run: bool,
) -> dict[str, Any]:
    payload = {
        "to": recipient,
        "title": title,
        "content": message,
        "signature": "ReqSys",
        "stampDate": datetime.now(UTC).isoformat(),
        "correlationId": correlation_id,
        "eventType": "reqsys-log-alert",
        "renderMode": "adaptive-card",
        "adaptiveCard": adaptive_card,
        "adaptiveCardJson": json.dumps(
            adaptive_card,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    if dry_run:
        return {
            "entregue": False,
            "dry_run": True,
            "canal_usado": "flow_bot_adaptive_direct",
            "destino_tipo": "chat",
            "correlation_id": correlation_id,
            "provider_response": {
                "planned": True,
                "render_mode": "adaptive-card",
                "event_type": "reqsys-log-alert",
            },
        }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error = "unknown"
    for attempt in range(1, 4):
        request = Request(
            webhook_url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "reqsys-log-adaptive-card/1.0",
                "X-Correlation-ID": correlation_id,
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                provider = json.loads(raw) if raw.strip() else {}
                if not isinstance(provider, dict):
                    provider = {"value": provider}
                return {
                    "entregue": 200 <= int(response.status) < 300,
                    "dry_run": False,
                    "canal_usado": "flow_bot_adaptive_direct",
                    "destino_tipo": "chat",
                    "correlation_id": correlation_id,
                    "status_code": int(response.status),
                    "provider_response": {
                        "render_mode": "adaptive-card",
                        "attempt": attempt,
                        **provider,
                    },
                }
        except HTTPError as exc:
            last_error = f"http_{exc.code}"
            if exc.code not in _RETRYABLE_HTTP or attempt == 3:
                break
        except (URLError, TimeoutError) as exc:
            last_error = f"network_error:{type(exc).__name__}"
            if attempt == 3:
                break
        time.sleep(min(2 ** (attempt - 1), 4))

    return {
        "entregue": False,
        "dry_run": False,
        "canal_usado": "flow_bot_adaptive_direct",
        "destino_tipo": "chat",
        "correlation_id": correlation_id,
        "erro": last_error,
        "motivo": "adaptive_webhook_failed",
        "provider_response": {"render_mode": "adaptive-card"},
    }


def send_notification(
    *,
    event: LogEvent,
    base_url: str,
    destination_id: str | None,
    recipient_policy: str,
    delivery_mode: str,
    webhook_url: str | None,
    webhook_recipient: str | None,
    dry_run: bool,
    timeout: float,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    message = build_message(event)
    card = build_adaptive_card(event)
    title = f"ReqSys Logs — {_severity_label(event.severity)} — {event.environment}"

    direct_url = (webhook_url or "").strip()
    direct_recipient = (webhook_recipient or destination_id or "").strip()
    direct_result: dict[str, Any] | None = None

    if direct_url and direct_recipient:
        direct_result = _send_adaptive_webhook(
            webhook_url=direct_url,
            recipient=direct_recipient,
            title=title,
            message=message,
            adaptive_card=card,
            correlation_id=event.correlation_id,
            timeout=timeout,
            dry_run=dry_run,
        )
        if direct_result.get("entregue") or direct_result.get("dry_run"):
            return message, card, direct_result

    try:
        from scripts.notificar_teams import enviar_mensagem
    except ModuleNotFoundError:
        from notificar_teams import enviar_mensagem

    fallback = enviar_mensagem(
        base_url=base_url,
        texto=message,
        titulo=title,
        modo="auto",
        destino_tipo="chat",
        destino_id=destination_id,
        autor="reqsys-log-notifier",
        permitir_fallback=True,
        dry_run=dry_run,
        timeout=timeout,
        recipient_policy=recipient_policy,
        delivery_mode=delivery_mode,
    )
    if direct_result is not None:
        provider = dict(fallback.get("provider_response") or {})
        provider.update(
            {
                "adaptive_direct_error": direct_result.get("erro")
                or direct_result.get("motivo"),
                "requested_render_mode": "adaptive-card",
            }
        )
        fallback["provider_response"] = provider
        fallback["fallback_usado"] = True
    return message, card, fallback


def _write_evidence(
    path: str | None,
    *,
    event: LogEvent,
    message: str,
    adaptive_card: dict[str, Any],
    delivery: dict[str, Any],
) -> None:
    if not path:
        return
    card_json = json.dumps(
        adaptive_card,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    document = {
        "schema_version": "1.1.0",
        "render_mode": "adaptive-card",
        "adaptive_card_version": adaptive_card.get("version"),
        "event": {
            **asdict(event),
            "details": {"count": len(event.details)},
            "summary": redact_text(event.summary),
        },
        "message_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
        "adaptive_card_sha256": hashlib.sha256(card_json.encode("utf-8")).hexdigest(),
        "delivery": sanitize_for_evidence(delivery),
    }
    Path(path).write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Notifica resumos seguros de logs do ReqSys no Teams"
    )
    parser.add_argument("--source", default=os.environ.get("REQSYS_LOG_SOURCE", "manual"))
    parser.add_argument(
        "--environment", default=os.environ.get("REQSYS_LOG_ENVIRONMENT", "unknown")
    )
    parser.add_argument("--severity", default=os.environ.get("REQSYS_LOG_SEVERITY", "error"))
    parser.add_argument("--status", default=os.environ.get("REQSYS_LOG_STATUS", "failure"))
    parser.add_argument(
        "--summary",
        default=os.environ.get("REQSYS_LOG_SUMMARY", "Falha operacional no ReqSys"),
    )
    parser.add_argument("--details", default=os.environ.get("REQSYS_LOG_DETAILS", ""))
    parser.add_argument("--run-url", default=os.environ.get("REQSYS_LOG_RUN_URL"))
    parser.add_argument("--workflow", default=os.environ.get("REQSYS_LOG_WORKFLOW"))
    parser.add_argument("--run-id", default=os.environ.get("REQSYS_LOG_RUN_ID"))
    parser.add_argument("--correlation-id", default=os.environ.get("REQSYS_LOG_CORRELATION_ID"))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument(
        "--github-api-url", default=os.environ.get("GITHUB_API_URL", DEFAULT_API_URL)
    )
    parser.add_argument(
        "--recipient-policy",
        default=os.environ.get("TEAMS_RECIPIENT_POLICY", DEFAULT_POLICY),
    )
    parser.add_argument(
        "--delivery-mode",
        default=os.environ.get("TEAMS_DELIVERY_MODE", "all"),
        choices=["all", "first_success", "channel"],
    )
    parser.add_argument("--destino-id", default=os.environ.get("TEAMS_GATEWAY_DESTINO_ID"))
    parser.add_argument("--webhook-url", default=os.environ.get("TEAMS_WEBHOOK_URL"))
    parser.add_argument(
        "--webhook-recipient",
        default=os.environ.get("TEAMS_WEBHOOK_RECIPIENT"),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("TEAMS_GATEWAY_BASE_URL", "https://reqsys-api.fly.dev"),
    )
    parser.add_argument("--output", default=os.environ.get("REQSYS_LOG_OUTPUT"))
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument(
        "--from-workflow-run",
        action="store_true",
        default=_env_bool("REQSYS_LOG_FROM_WORKFLOW_RUN"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=_env_bool("REQSYS_LOG_DRY_RUN"),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=_env_bool("REQSYS_LOG_STRICT"),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    correlation_id = args.correlation_id or f"reqsys-log-{args.run_id or uuid.uuid4()}"
    details = normalize_details([args.details])

    if args.from_workflow_run:
        try:
            jobs = fetch_github_jobs(
                repository=args.repository or "",
                run_id=args.run_id or "",
                token=args.github_token or "",
                api_url=args.github_api_url,
                timeout=min(args.timeout, 30.0),
            )
            workflow_details = summarize_failed_jobs(jobs)
            details = normalize_details([*workflow_details, *details], max_lines=25)
        except (ValueError, RuntimeError) as exc:
            details = normalize_details(
                [*details, f"Coleta de jobs indisponivel: {exc}"],
                max_lines=25,
            )

    event = LogEvent(
        source=redact_text(args.source.strip() or "manual"),
        environment=redact_text(args.environment.strip() or "unknown"),
        severity=redact_text(args.severity.strip() or "error"),
        status=redact_text(args.status.strip() or "failure"),
        summary=redact_text(args.summary.strip() or "Falha operacional no ReqSys"),
        details=details,
        run_url=_safe_github_url(args.run_url),
        workflow=redact_text(args.workflow.strip()) if args.workflow else None,
        run_id=str(args.run_id).strip() if args.run_id else None,
        correlation_id=redact_text(correlation_id),
    )
    message, card, delivery = send_notification(
        event=event,
        base_url=args.base_url,
        destination_id=args.destino_id,
        recipient_policy=args.recipient_policy,
        delivery_mode=args.delivery_mode,
        webhook_url=args.webhook_url,
        webhook_recipient=args.webhook_recipient,
        dry_run=args.dry_run,
        timeout=args.timeout,
    )
    _write_evidence(
        args.output,
        event=event,
        message=message,
        adaptive_card=card,
        delivery=delivery,
    )
    safe_delivery = sanitize_for_evidence(delivery)
    print(
        json.dumps(
            {
                "correlation_id": event.correlation_id,
                "render_mode": "adaptive-card",
                "delivery": safe_delivery,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    delivered = bool(delivery.get("entregue")) or bool(delivery.get("dry_run"))
    if args.strict and not delivered:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
