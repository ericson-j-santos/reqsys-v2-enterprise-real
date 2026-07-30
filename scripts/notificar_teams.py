#!/usr/bin/env python3
"""Envia notificacoes ao Teams via o Teams Messaging Gateway do ReqSys.

Destinos individuais podem ser informados diretamente para compatibilidade.
Para operacao normal, use recipient_policy: o gateway resolve destinatarios
ativos no banco, sem exigir alteracao de secrets quando a equipe mudar.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://reqsys-api.fly.dev"


def enviar_mensagem(
    *,
    base_url: str,
    texto: str,
    titulo: str,
    modo: str,
    destino_tipo: str,
    destino_id: str | None,
    autor: str,
    permitir_fallback: bool,
    dry_run: bool,
    timeout: float,
    recipient_policy: str | None = None,
    delivery_mode: str = "all",
) -> dict[str, Any]:
    payload = {
        "destino_tipo": destino_tipo,
        "modo": modo,
        "destino_id": destino_id,
        "texto": texto,
        "autor": autor,
        "permitir_fallback": permitir_fallback,
        "dry_run": dry_run,
        "metadata": {"titulo": titulo, "assinatura": "ReqSys"},
    }
    policy = (recipient_policy or "").strip()
    if policy:
        payload["delivery_mode"] = delivery_mode
        endpoint = f"/v1/teams-gateway/recipient-policies/{quote(policy, safe='')}/messages"
    else:
        endpoint = "/v1/teams-gateway/messages"

    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}{endpoint}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "reqsys-notificar-teams/1.1"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return {"entregue": False, "erro": f"http_{exc.code}", "detail": detail}
    except (URLError, TimeoutError) as exc:
        return {"entregue": False, "erro": "network_error", "detail": str(exc)}

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return {"entregue": False, "erro": "json_invalid", "detail": str(exc)}

    data = parsed.get("data") if isinstance(parsed, dict) else None
    if not isinstance(data, dict):
        return {"entregue": False, "erro": "payload_invalido", "detail": parsed}
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Envia mensagem via Teams Messaging Gateway do ReqSys")
    parser.add_argument("--texto", required=True, help="Corpo da mensagem")
    parser.add_argument("--titulo", default="ReqSys", help="Titulo da mensagem")
    parser.add_argument(
        "--modo",
        default="auto",
        choices=["auto", "graph_delegado", "webhook", "graph_app_only", "bot", "flow_bot"],
    )
    parser.add_argument(
        "--destino-tipo",
        default="chat",
        choices=["auto", "chat", "chat_1a1", "canal", "webhook"],
    )
    parser.add_argument("--destino-id", default=os.environ.get("TEAMS_GATEWAY_DESTINO_ID"))
    parser.add_argument("--recipient-policy", default=os.environ.get("TEAMS_RECIPIENT_POLICY"))
    parser.add_argument(
        "--delivery-mode",
        default=os.environ.get("TEAMS_DELIVERY_MODE", "all"),
        choices=["all", "first_success", "channel"],
    )
    parser.add_argument("--base-url", default=os.environ.get("TEAMS_GATEWAY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--autor", default="reqsys-ci")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fallback", action="store_true", help="Desabilita fallback automatico de canal")
    parser.add_argument("--output", help="Arquivo JSON de evidencia")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Retorna codigo de saida != 0 quando nenhuma mensagem e entregue",
    )
    args = parser.parse_args()

    if not args.destino_id and not args.recipient_policy and args.modo in ("flow_bot", "graph_delegado"):
        print(
            "::warning::destino_id e recipient_policy ausentes; o gateway pode nao encontrar rota para chat.",
            file=sys.stderr,
        )

    resultado = enviar_mensagem(
        base_url=args.base_url,
        texto=args.texto,
        titulo=args.titulo,
        modo=args.modo,
        destino_tipo=args.destino_tipo,
        destino_id=args.destino_id,
        autor=args.autor,
        permitir_fallback=not args.no_fallback,
        dry_run=args.dry_run,
        timeout=args.timeout,
        recipient_policy=args.recipient_policy,
        delivery_mode=args.delivery_mode,
    )

    if args.output:
        Path(args.output).write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))

    entregue = bool(resultado.get("entregue")) or bool(resultado.get("dry_run"))
    if not entregue:
        print(
            f"::warning::Notificacao Teams nao entregue: {resultado.get('erro') or resultado.get('motivo')}",
            file=sys.stderr,
        )
    if args.strict and not entregue:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
