#!/usr/bin/env python3
"""Relatorio somente-leitura dos requisitos que estao derrubando o score de Qualidade IA.

O score em backend/app/services/ai_quality.py e calculado a partir de dados reais
(requisitos aprovados, cobertura de descricao, incidentes de auditoria). Este script
NAO altera nenhum registro: ele so lista, por ambiente, quais requisitos estao fora
das categorias "aprovado"/"em_analise"/"rejeitado" (portanto contam como "pendente"
e penalizam acuracia/relevancia/consistencia), para que um humano decida a triagem.

Uso:
    python scripts/relatorio_qualidade_ia_pendentes.py \
        --api-url https://reqsys-api.fly.dev=prod \
        --api-url https://reqsys-api-stg.fly.dev=hml \
        --api-url https://reqsys-api-dev.fly.dev=dev
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any

# Mantido em sincronia manual com backend/app/services/requisitos_metricas.py
STATUS_APROVADOS = frozenset({
    'aprovado', 'aprovados', 'concluido', 'concluído', 'concluida',
    'done', 'finalizado', 'implementado', 'encerrado',
})
STATUS_EM_ANALISE = frozenset({'em_analise', 'em analise', 'validado', 'estruturado', 'backlog'})
STATUS_REJEITADOS = frozenset({'rejeitado', 'rejeitados', 'cancelado'})


def _get_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - URL fixa, sem input de usuario
        return json.loads(resp.read().decode('utf-8'))


def _classificar(status: str) -> str:
    normalizado = (status or '').strip().lower()
    if normalizado in STATUS_APROVADOS:
        return 'aprovado'
    if normalizado in STATUS_EM_ANALISE or 'analise' in normalizado:
        return 'em_analise'
    if normalizado in STATUS_REJEITADOS:
        return 'rejeitado'
    return 'pendente'


def analisar_ambiente(nome: str, api_url: str) -> dict[str, Any]:
    payload = _get_json(f'{api_url.rstrip("/")}/v1/requisitos')
    requisitos = payload.get('data') or []
    pendentes = []
    contagem = {'aprovado': 0, 'em_analise': 0, 'rejeitado': 0, 'pendente': 0}
    for item in requisitos:
        categoria = _classificar(item.get('status', ''))
        contagem[categoria] += 1
        if categoria == 'pendente':
            pendentes.append(item)
    return {
        'ambiente': nome,
        'api_url': api_url,
        'total': len(requisitos),
        'contagem': contagem,
        'pendentes': [
            {'codigo': p.get('codigo'), 'titulo': p.get('titulo'), 'status': p.get('status')}
            for p in pendentes
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--api-url',
        action='append',
        default=[],
        metavar='URL=NOME',
        help='Ex.: https://reqsys-api.fly.dev=prod (repetivel)',
    )
    args = parser.parse_args(argv)

    alvos = args.api_url or [
        'https://reqsys-api.fly.dev=prod',
        'https://reqsys-api-stg.fly.dev=hml',
        'https://reqsys-api-dev.fly.dev=dev',
    ]

    resultados = []
    for alvo in alvos:
        url, _, nome = alvo.partition('=')
        nome = nome or url
        try:
            resultados.append(analisar_ambiente(nome, url))
        except Exception as exc:  # noqa: BLE001 - relatorio nao deve derrubar por 1 ambiente fora do ar
            resultados.append({'ambiente': nome, 'api_url': url, 'erro': str(exc)})

    print('# Relatorio de requisitos pendentes de triagem (Qualidade IA)\n')
    for r in resultados:
        if 'erro' in r:
            print(f"## {r['ambiente']} ({r['api_url']}) — indisponivel: {r['erro']}\n")
            continue
        print(f"## {r['ambiente']} ({r['api_url']})")
        print(f"Total: {r['total']} | aprovado={r['contagem']['aprovado']} "
              f"em_analise={r['contagem']['em_analise']} rejeitado={r['contagem']['rejeitado']} "
              f"pendente={r['contagem']['pendente']}")
        if r['pendentes']:
            print('\n| Codigo | Titulo | Status atual |')
            print('| --- | --- | --- |')
            for p in r['pendentes']:
                print(f"| {p['codigo']} | {p['titulo']} | {p['status']} |")
        print()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
