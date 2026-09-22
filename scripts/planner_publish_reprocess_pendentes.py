#!/usr/bin/env python3
"""Reprocessa em lote tentativas de publicação do Planner que falharam na
integração (status `falhou_integracao`), fechando o loop de "reprocessamento
automático" da issue #32 — até aqui só existia o endpoint manual
`POST /v1/hub-lowcode/planner/publish/{id}/reprocessar`.

Não construído como um worker/fila com estado próprio: a cada execução lista
as tentativas em `falhou_integracao` via `GET /v1/hub-lowcode/planner/publish`
e chama o endpoint de reprocesso já existente para cada uma, até um limite de
lote. A idempotência e o limite de tentativas continuam garantidos pelo
próprio backend (`reprocessar_tentativa` em `planner_publish.py`) — este
script nunca decide sozinho se algo é seguro reenviar, só orquestra chamadas
ao endpoint que já decide isso.

Uso:
  python scripts/planner_publish_reprocess_pendentes.py \
      --base-url https://reqsys-api-dev.fly.dev \
      --service-token "$PLANNER_PUBLISH_SERVICE_TOKEN" \
      [--lote-max 10] [--evidence-file artifacts/planner-reprocess.json] [--strict]

Nunca imprime o service token. Best-effort por padrão (exit 0 mesmo com
falhas individuais de reprocesso) -- use --strict para propagar erro se
qualquer chamada inesperada (não um 409 de limite/duplicidade) ocorrer.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

STATUS_FALHOU_INTEGRACAO = 'falhou_integracao'


def _http_request(method: str, url: str, *, headers: dict[str, str], timeout: int) -> tuple[int, dict]:
    req = Request(url, method=method)
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {'detail': raw.decode('utf-8', errors='replace')}
    except URLError as exc:
        raise SystemExit(f'Falha de rede em {method} {url}: {exc.reason}')


def listar_pendentes(base_url: str, service_token: str, limit: int, timeout: int) -> list[dict[str, Any]]:
    status, body = _http_request(
        'GET',
        f'{base_url}/v1/hub-lowcode/planner/publish?status={STATUS_FALHOU_INTEGRACAO}&limit={limit}',
        headers={'X-Service-Token': service_token},
        timeout=timeout,
    )
    if status != 200:
        raise SystemExit(f'Falha ao listar tentativas pendentes: HTTP {status} — {body}')
    return body.get('data', {}).get('items', [])


def reprocessar(base_url: str, service_token: str, attempt_id: int, timeout: int) -> tuple[int, dict]:
    return _http_request(
        'POST',
        f'{base_url}/v1/hub-lowcode/planner/publish/{attempt_id}/reprocessar',
        headers={'X-Service-Token': service_token},
        timeout=timeout,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--service-token', required=True)
    parser.add_argument('--lote-max', type=int, default=10, help='Máximo de tentativas reprocessadas por execução.')
    parser.add_argument('--timeout', type=int, default=20)
    parser.add_argument('--evidence-file', default=None, help='Caminho para gravar o resumo em JSON.')
    parser.add_argument('--strict', action='store_true', help='Sai com erro se alguma chamada retornar status inesperado (não 200/409).')
    args = parser.parse_args()

    base_url = args.base_url.rstrip('/')
    pendentes = listar_pendentes(base_url, args.service_token, args.lote_max, args.timeout)

    resultados: list[dict[str, Any]] = []
    inesperados = 0
    for item in pendentes[: args.lote_max]:
        attempt_id = item['attempt_id']
        status_http, resposta = reprocessar(base_url, args.service_token, attempt_id, args.timeout)
        if status_http == 200:
            desfecho = 'publicado' if resposta.get('data', {}).get('status') == 'publicado' else 'ainda_falhando'
        elif status_http == 409:
            desfecho = 'recusado_pelo_backend'  # já publicado/duplicado, ou limite de tentativas excedido
        else:
            desfecho = 'erro_inesperado'
            inesperados += 1
        resultados.append({'attempt_id': attempt_id, 'status_http': status_http, 'desfecho': desfecho})
        time.sleep(0.2)  # não martelar o webhook do Planner em sequência

    resumo = {
        'schema_version': '1.0.0',
        'contract': 'reqsys-planner-publish-reprocess-pendentes',
        'gerado_em': int(time.time()),
        'base_url': base_url,
        'total_pendentes_encontrados': len(pendentes),
        'total_processados_neste_lote': len(resultados),
        'total_inesperados': inesperados,
        'resultados': resultados,
    }

    print(json.dumps(resumo, ensure_ascii=False, indent=2))

    if args.evidence_file:
        path = Path(args.evidence_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    if args.strict and inesperados:
        raise SystemExit(f'{inesperados} chamada(s) de reprocesso retornaram status inesperado.')


if __name__ == '__main__':
    main()
