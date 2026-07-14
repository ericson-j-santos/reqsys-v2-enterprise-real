#!/usr/bin/env python3
"""Envia notificacoes ao Teams via o Teams Messaging Gateway do ReqSys.

Usado pela automacao de CI para avisar sobre mudancas no repositorio (push/commit
em main) e sobre o resultado de deploys/sincronizacao de ambientes. Nao decide o
canal aqui: delega ao gateway (POST /v1/teams-gateway/messages, modo=auto por
padrao) a escolha de rota e o fallback, que ja tem retry/circuit breaker no lado
do servidor (ADR-010). Falha de entrega nao derruba o build por padrao — use
--strict para propagar o erro quando isso for desejado.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
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
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/v1/teams-gateway/messages",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "reqsys-notificar-teams/1.0"},
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
    parser.add_argument("--base-url", default=os.environ.get("TEAMS_GATEWAY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--autor", default="reqsys-ci")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fallback", action="store_true", help="Desabilita fallback automatico de canal")
    parser.add_argument("--output", help="Arquivo JSON de evidencia")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Retorna codigo de saida != 0 quando a mensagem nao for entregue (por padrao, so avisa)",
    )
    args = parser.parse_args()

    if not args.destino_id and args.modo in ("flow_bot", "graph_delegado"):
        print(
            "::warning::destino_id ausente (env TEAMS_GATEWAY_DESTINO_ID ou --destino-id) — modo pode falhar.",
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
    )

    if args.output:
        Path(args.output).write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))

    entregue = bool(resultado.get("entregue")) or bool(resultado.get("dry_run"))
    if not entregue:
        print(f"::warning::Notificacao Teams nao entregue: {resultado.get('erro') or resultado.get('motivo')}", file=sys.stderr)
    if args.strict and not entregue:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
