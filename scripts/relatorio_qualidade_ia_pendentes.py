#!/usr/bin/env python3
"""Relatorio somente-leitura dos requisitos que estao derrubando o score de Qualidade IA.

O score em backend/app/services/ai_quality.py e calculado a partir de dados reais
(requisitos aprovados, cobertura de descricao, incidentes de auditoria). Este script
NAO altera nenhum registro: ele so lista, por ambiente, quais requisitos estao fora
das categorias "aprovado"/"em_analise"/"rejeitado" (portanto contam como "pendente"
e penalizam acuracia/relevancia/consistencia), para que um humano decida a triagem.

Uso:
    python scripts/relatorio_qualidade_ia_pendentes.py \
        --api-url https://api.example.net=prod \
        --api-url https://api-stg.example.net=hml \
        --api-url https://api-dev.example.net=dev
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any

try:
    from scripts.runtime_url_policy import require_authorized_runtime_url
except ModuleNotFoundError:  # execução direta: python scripts/<arquivo>.py
    from runtime_url_policy import require_authorized_runtime_url

# Mantido em sincronia manual com backend/app/services/requisitos_metricas.py
STATUS_APROVADOS = frozenset({
    'aprovado', 'aprovados', 'concluido', 'concluído', 'concluida',
    'done', 'finalizado', 'implementado', 'encerrado',
})
STATUS_EM_ANALISE = frozenset({'em_analise', 'em analise', 'validado', 'estruturado', 'backlog'})
STATUS_REJEITADOS = frozenset({'rejeitado', 'rejeitados', 'cancelado'})


def _get_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
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
    api_url = _require_https_api_url(api_url)
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


def _require_https_api_url(value: str) -> str:
    api_url = require_authorized_runtime_url(value, label='URL da API de Qualidade IA')
    if not api_url.startswith('https://'):
        raise ValueError('URL da API de Qualidade IA deve usar HTTPS')
    return api_url


def _parse_target(value: str) -> tuple[str, str]:
    url, separator, name = value.partition('=')
    if not separator or not name.strip():
        raise ValueError("--api-url deve seguir o formato URL=NOME")
    return _require_https_api_url(url), name.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--api-url',
        action='append',
        default=[],
        metavar='URL=NOME',
        help='Ex.: https://api.example.net=prod (repetivel)',
    )
    args = parser.parse_args(argv)

    if not args.api_url:
        parser.error('informe ao menos um --api-url URL=NOME')

    try:
        alvos = [_parse_target(alvo) for alvo in args.api_url]
    except ValueError as exc:
        parser.error(str(exc))

    resultados = []
    for url, nome in alvos:
        try:
            resultados.append(analisar_ambiente(nome, url))
        except Exception as exc:  # noqa: BLE001 - um ambiente indisponível não derruba o relatório
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
