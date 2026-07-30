#!/usr/bin/env python3
"""Send a ReqSys HITL approval request through the existing Teams Gateway."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

try:
    from scripts.notificar_teams import DEFAULT_BASE_URL, enviar_mensagem
except ModuleNotFoundError:  # Direct execution: python scripts/notify_hitl_approval_teams.py
    from notificar_teams import DEFAULT_BASE_URL, enviar_mensagem


def _github_url(value: str, field: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError(f"{field} deve ser uma URL HTTPS do GitHub")
    return value.strip()


def build_message(
    *,
    request_title: str,
    control_id: str,
    summary: str,
    request_url: str,
    evidence_url: str | None,
) -> str:
    request_link = _github_url(request_url, "request_url")
    evidence_link = _github_url(evidence_url, "evidence_url") if evidence_url else request_link
    title = request_title.strip()
    control = control_id.strip()
    text = summary.strip()
    if not title or not control or not text:
        raise ValueError("request_title, control_id e summary sao obrigatorios")

    return "\n".join(
        [
            "**Aprovação humana necessária**",
            "",
            f"**Solicitação:** {title}",
            f"**Controle/Escopo:** `{control}`",
            f"**Resumo:** {text}",
            f"**Evidências:** [abrir pacote de evidências]({evidence_link})",
            "",
            "**Decisão autenticada no GitHub**",
            f"- [Aprovar]({request_link}) — comentar `/approve <justificativa>`",
            f"- [Rejeitar]({request_link}) — comentar `/reject <justificativa>`",
            f"- [Solicitar ajuste]({request_link}) — comentar `/adjust <justificativa>`",
            "",
            "A decisão será aceita somente de um ator humano com permissão de escrita, manutenção ou administração.",
            "`production_touched=false`",
        ]
    )


def send_request(
    *,
    request_title: str,
    control_id: str,
    summary: str,
    request_url: str,
    evidence_url: str | None,
    base_url: str,
    destination_id: str | None,
    mode: str,
    destination_type: str,
    dry_run: bool,
    timeout: float,
) -> dict:
    message = build_message(
        request_title=request_title,
        control_id=control_id,
        summary=summary,
        request_url=request_url,
        evidence_url=evidence_url,
    )
    request_sha256 = hashlib.sha256(message.encode("utf-8")).hexdigest()
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
    )
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-hitl-teams-notification",
        "control_id": control_id,
        "request_url": request_url,
        "request_sha256": request_sha256,
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
    parser.add_argument("--base-url", default=os.environ.get("TEAMS_GATEWAY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--destination-id", default=os.environ.get("TEAMS_GATEWAY_DESTINO_ID"))
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "graph_delegado", "webhook", "graph_app_only", "bot", "flow_bot"],
    )
    parser.add_argument(
        "--destination-type",
        default="chat",
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
        base_url=args.base_url,
        destination_id=args.destination_id,
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
    if args.strict and not delivered:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
