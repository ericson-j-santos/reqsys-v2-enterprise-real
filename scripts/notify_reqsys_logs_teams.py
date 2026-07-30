#!/usr/bin/env python3
"""Envia ao Teams resumos seguros de falhas e logs operacionais do ReqSys."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

DEFAULT_API_URL = "https://api.github.com"
DEFAULT_POLICY = "reqsys-operations"
_MAX_GITHUB_PAGES = 5
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
                "User-Agent": "reqsys-log-teams-notifier/1.0",
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


def build_message(event: LogEvent) -> str:
    lines = [
        f"Status: {event.status}",
        f"Severidade: {event.severity}",
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
    if event.run_url:
        lines.append(f"Evidencia: {event.run_url}")
    lines.append(
        "Observacao: o Teams recebe somente resumo sanitizado; "
        "logs brutos permanecem no sistema de origem."
    )
    return "\n".join(lines)


def _write_evidence(
    path: str | None,
    *,
    event: LogEvent,
    message: str,
    delivery: dict[str, Any],
) -> None:
    if not path:
        return
    document = {
        "schema_version": "1.0.0",
        "event": {
            **asdict(event),
            "details": {"count": len(event.details)},
            "summary": redact_text(event.summary),
        },
        "message_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
        "delivery": delivery,
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
        run_url=args.run_url.strip() if args.run_url else None,
        workflow=redact_text(args.workflow.strip()) if args.workflow else None,
        run_id=str(args.run_id).strip() if args.run_id else None,
        correlation_id=redact_text(correlation_id),
    )
    message = build_message(event)

    try:
        from scripts.notificar_teams import enviar_mensagem
    except ModuleNotFoundError:
        from notificar_teams import enviar_mensagem

    delivery = enviar_mensagem(
        base_url=args.base_url,
        texto=message,
        titulo=f"ReqSys Logs — {event.severity.upper()} — {event.environment}",
        modo="auto",
        destino_tipo="chat",
        destino_id=args.destino_id,
        autor="reqsys-log-notifier",
        permitir_fallback=True,
        dry_run=args.dry_run,
        timeout=args.timeout,
        recipient_policy=args.recipient_policy,
        delivery_mode=args.delivery_mode,
    )
    _write_evidence(args.output, event=event, message=message, delivery=delivery)
    print(
        json.dumps(
            {"correlation_id": event.correlation_id, "delivery": delivery},
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
