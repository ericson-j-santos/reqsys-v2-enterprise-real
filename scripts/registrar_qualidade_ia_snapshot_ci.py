#!/usr/bin/env python3
"""Chamado pelo workflow qualidade-ia-snapshot.yml para registrar 1 snapshot por ambiente.

Le AMBIENTE e API_URL do ambiente de execucao, chama POST /v1/qualidade-ia/snapshot
naquele ambiente, publica o resultado no GITHUB_STEP_SUMMARY e emite um aviso do
Actions (::warning) se o score_geral estiver abaixo do limiar de atencao.
"""

from __future__ import annotations

import json
import os
import urllib.request

LIMIAR_ATENCAO = 70.0


def main() -> int:
    ambiente = os.environ['AMBIENTE']
    api_url = os.environ['API_URL'].rstrip('/')

    req = urllib.request.Request(f'{api_url}/v1/qualidade-ia/snapshot', method='POST')  # noqa: S310
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        resposta = json.loads(resp.read().decode('utf-8'))

    print(json.dumps(resposta, indent=2, ensure_ascii=False))
    score = resposta['data']['score_geral']

    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a', encoding='utf-8') as summary:
            summary.write(f'### Qualidade IA — {ambiente}\nscore_geral: **{score}**\n')

    if score < LIMIAR_ATENCAO:
        print(
            f'::warning title=Qualidade IA abaixo do esperado ({ambiente})::'
            f'score_geral={score} — revisar requisitos pendentes com '
            'scripts/relatorio_qualidade_ia_pendentes.py'
        )

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
