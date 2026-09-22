#!/usr/bin/env python3
"""Send a ReqSys HITL approval request as a structured Teams Adaptive Card."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import uuid
from zoneinfo import ZoneInfo

try:
    from scripts.notificar_teams import DEFAULT_BASE_URL, enviar_mensagem
except ModuleNotFoundError:
    from notificar_teams import DEFAULT_BASE_URL, enviar_mensagem

_RETRYABLE_HTTP = {429, 500, 502, 503, 504}
_SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def _github_url(value: str, field: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError(f"{field} deve ser uma URL HTTPS do GitHub")
    return value.strip()


def _request_reference(request_url: str) -> str:
    parts = [part for part in urlparse(request_url).path.split("/") if part]
    for marker, label in (("pull", "PR"), ("issues", "Issue")):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts):
                return f"{label} #{parts[index + 1]}"
    return "Solicitação GitHub"


def _formatted_sao_paulo(value: datetime | None = None) -> str:
    instant = value or datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    local = instant.astimezone(_SAO_PAULO)
    return local.strftime("%d/%m/%Y %H:%M") + " (America/Sao_Paulo)"


def _normalized_fields(
    *,
    request_title: str,
    control_id: str,
    summary: str,
    request_url: str,
    evidence_url: str | None,
) -> tuple[str, str, str, str, str]:
    request_link = _github_url(request_url, "request_url")
    evidence_link = _github_url(evidence_url, "evidence_url") if evidence_url else request_link
    title = request_title.strip()
    control = control_id.strip()
    text = summary.strip()
    if not title or not control or not text:
        raise ValueError("request_title, control_id e summary sao obrigatorios")
    return title, control, text, request_link, evidence_link


def build_message(
    *,
    request_title: str,
    control_id: str,
    summary: str,
    request_url: str,
    evidence_url: str | None,
) -> str:
    title, control, text, request_link, evidence_link = _normalized_fields(
        request_title=request_title,
        control_id=control_id,
        summary=summary,
        request_url=request_url,
        evidence_url=evidence_url,
    )
    return "\n\n".join(
        [
            "APROVAÇÃO HUMANA NECESSÁRIA",
            f"Solicitação: {title}",
            f"Controle/Escopo: {control}",
            f"Resumo: {text}",
            f"Evidências: {evidence_link}",
            "Decisão autenticada no GitHub:",
            "/approve <justificativa>\n/reject <justificativa>\n/adjust <justificativa>",
            f"Abrir solicitação: {request_link}",
            "production_touched=false",
        ]
    )


def build_adaptive_card(
    *,
    request_title: str,
    control_id: str,
    summary: str,
    request_url: str,
    evidence_url: str | None,
    environment: str,
    correlation_id: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    title, control, text, request_link, evidence_link = _normalized_fields(
        request_title=request_title,
        control_id=control_id,
        summary=summary,
        request_url=request_url,
        evidence_url=evidence_url,
    )
    environment_name = environment.strip() or "Governança (não produtivo)"
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "msteams": {"width": "Full"},
        "body": [
            {
                "type": "Container",
                "style": "emphasis",
                "bleed": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "ReqSys HITL — aprovação humana",
                        "weight": "Bolder",
                        "size": "Large",
                        "wrap": True,
                    },
                    {
                        "type": "TextBlock",
                        "text": title,
                        "spacing": "Small",
                        "wrap": True,
                    },
                ],
            },
            {
                "type": "TextBlock",
                "text": text,
                "spacing": "Medium",
                "wrap": True,
            },
            {
                "type": "FactSet",
                "spacing": "Medium",
                "facts": [
                    {"title": "PR/Issue", "value": _request_reference(request_link)},
                    {"title": "Controle", "value": control},
                    {"title": "Ambiente", "value": environment_name},
                    {"title": "Horário", "value": _formatted_sao_paulo(generated_at)},
                    {"title": "Correlation ID", "value": correlation_id},
                    {"title": "Produção", "value": "production_touched=false"},
                ],
            },
            {
                "type": "TextBlock",
                "text": "Decisão autenticada no GitHub",
                "weight": "Bolder",
                "spacing": "Medium",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": (
                    "Abra a solicitação e registre um comentário humano com permissão de escrita:\n\n"
                    "`/approve <justificativa>`\n\n"
                    "`/reject <justificativa>`\n\n"
                    "`/adjust <justificativa>`"
                ),
                "fontType": "Monospace",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"[Abrir pacote de evidências]({evidence_link})",
                "spacing": "Medium",
                "wrap": True,
            },
        ],
        "actions": [
            {"type": "Action.OpenUrl", "title": "Aprovar no GitHub", "url": request_link},
            {"type": "Action.OpenUrl", "title": "Rejeitar no GitHub", "url": request_link},
            {"type": "Action.OpenUrl", "title": "Solicitar ajuste", "url": request_link},
        ],
    }


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
        "eventType": "hitl-approval-request",
        "renderMode": "adaptive-card",
        "adaptiveCard": adaptive_card,
        "adaptiveCardJson": json.dumps(adaptive_card, ensure_ascii=False, separators=(",", ":")),
    }
    if dry_run:
        return {
            "entregue": False,
            "dry_run": True,
            "canal_usado": "flow_bot_adaptive_direct",
            "destino_tipo": "chat",
            "correlation_id": correlation_id,
            "provider_response": {"planned": True, "render_mode": "adaptive-card"},
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
                "User-Agent": "reqsys-hitl-adaptive-card/1.0",
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


def send_request(
    *,
    request_title: str,
    control_id: str,
    summary: str,
    request_url: str,
    evidence_url: str | None,
    base_url: str,
    destination_id: str | None,
    recipient_policy: str,
    delivery_mode: str,
    mode: str,
    destination_type: str,
    dry_run: bool,
    timeout: float,
    environment: str = "Governança (não produtivo)",
    webhook_url: str | None = None,
    webhook_recipient: str | None = None,
    correlation_id: str | None = None,
    generated_at: datetime | None = None,
) -> dict:
    corr = correlation_id or str(uuid.uuid4())
    message = build_message(
        request_title=request_title,
        control_id=control_id,
        summary=summary,
        request_url=request_url,
        evidence_url=evidence_url,
    )
    card = build_adaptive_card(
        request_title=request_title,
        control_id=control_id,
        summary=summary,
        request_url=request_url,
        evidence_url=evidence_url,
        environment=environment,
        correlation_id=corr,
        generated_at=generated_at,
    )
    canonical = json.dumps(
        {"adaptive_card": card, "fallback_text": message},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    request_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    direct_recipient = (webhook_recipient or destination_id or "").strip()
    direct_url = (webhook_url or "").strip()
    direct_result: dict[str, Any] | None = None
    if direct_url and direct_recipient:
        direct_result = _send_adaptive_webhook(
            webhook_url=direct_url,
            recipient=direct_recipient,
            title=f"ReqSys HITL — {request_title}",
            message=message,
            adaptive_card=card,
            correlation_id=corr,
            timeout=timeout,
            dry_run=dry_run,
        )
        if direct_result.get("entregue") or direct_result.get("dry_run"):
            result = direct_result
        else:
            result = enviar_mensagem(
                base_url=base_url,
                texto=message,
                titulo=f"ReqSys HITL — {request_title}",
                modo=mode,
                destino_tipo=destination_type,
                destino_id=destination_id,
                autor="reqsys-hitl",
                permitir_fallback=True,
                dry_run=dry_run,
                timeout=timeout,
                recipient_policy=recipient_policy,
                delivery_mode=delivery_mode,
            )
            provider = dict(result.get("provider_response") or {})
            provider["adaptive_direct_error"] = direct_result.get("erro") or direct_result.get("motivo")
            result["provider_response"] = provider
            result["fallback_usado"] = True
    else:
        result = enviar_mensagem(
            base_url=base_url,
            texto=message,
            titulo=f"ReqSys HITL — {request_title}",
            modo=mode,
            destino_tipo=destination_type,
            destino_id=destination_id,
            autor="reqsys-hitl",
            permitir_fallback=True,
            dry_run=dry_run,
            timeout=timeout,
            recipient_policy=recipient_policy,
            delivery_mode=delivery_mode,
        )

    return {
        "schema_version": "1.2.0",
        "contract": "reqsys-hitl-teams-notification",
        "render_mode": "adaptive-card",
        "adaptive_card_version": "1.2",
        "control_id": control_id,
        "request_url": request_url,
        "request_sha256": request_sha256,
        "correlation_id": corr,
        "generated_at_sao_paulo": _formatted_sao_paulo(generated_at),
        "environment": environment,
        "recipient_policy": recipient_policy,
        "delivery_mode": delivery_mode,
        "direct_adaptive_route_configured": bool(direct_url and direct_recipient),
        "explicit_destination_fallback_configured": bool(destination_id),
        "notification": result,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a HITL approval request through Teams")
    parser.add_argument("--request-title", required=True)
    parser.add_argument("--control-id", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--request-url", required=True)
    parser.add_argument("--evidence-url")
    parser.add_argument("--environment", default=os.environ.get("HITL_ENVIRONMENT", "Governança (não produtivo)"))
    parser.add_argument("--base-url", default=os.environ.get("TEAMS_GATEWAY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--destination-id", default=os.environ.get("TEAMS_GATEWAY_DESTINO_ID"))
    parser.add_argument("--webhook-url", default=os.environ.get("TEAMS_WEBHOOK_URL"))
    parser.add_argument("--webhook-recipient", default=os.environ.get("TEAMS_WEBHOOK_RECIPIENT"))
    parser.add_argument(
        "--recipient-policy",
        default=os.environ.get("HITL_RECIPIENT_POLICY", "hitl-approvers"),
    )
    parser.add_argument(
        "--delivery-mode",
        default=os.environ.get("HITL_DELIVERY_MODE", "all"),
        choices=["all", "first_success", "channel"],
    )
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "graph_delegado", "webhook", "graph_app_only", "bot", "flow_bot"],
    )
    parser.add_argument(
        "--destination-type",
        default="auto",
        choices=["auto", "chat", "chat_1a1", "canal", "webhook"],
    )
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = send_request(
        request_title=args.request_title,
        control_id=args.control_id,
        summary=args.summary,
        request_url=args.request_url,
        evidence_url=args.evidence_url,
        environment=args.environment,
        base_url=args.base_url,
        destination_id=args.destination_id,
        webhook_url=args.webhook_url,
        webhook_recipient=args.webhook_recipient,
        recipient_policy=args.recipient_policy,
        delivery_mode=args.delivery_mode,
        mode=args.mode,
        destination_type=args.destination_type,
        dry_run=args.dry_run,
        timeout=args.timeout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    notification = payload["notification"]
    delivered = bool(notification.get("entregue")) or bool(notification.get("dry_run"))
    if not delivered:
        print(
            "::warning::Solicitacao HITL registrada, mas nenhuma notificacao Teams foi entregue.",
            flush=True,
        )
    if args.strict and not delivered:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
