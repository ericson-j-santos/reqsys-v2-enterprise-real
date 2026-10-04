#!/usr/bin/env python3
"""Replica requisitos de producao para hml/dev, anonimizando o campo solicitante (LGPD).

Escopo deliberadamente limitado a `requisitos`: NAO replica `auditoria` nem
`recommendation_ia`. O trilha de auditoria de cada ambiente deve refletir apenas
eventos reais daquele ambiente (ADR-003) — fabricar eventos de auditoria em
hml/dev a partir de producao contaminaria a evidencia operacional daquele
ambiente.

Mascaramento: o campo `solicitante` (nome/e-mail) e substituido por um
pseudonimo estavel derivado de hash, nunca pelo valor original. Titulo e
descricao sao preservados (conteudo de produto, necessario para o teste ser
realista), com uma marca de origem anexada a descricao para rastreabilidade
e para permitir reexecucao idempotente (registros ja replicados sao pulados).

Por padrao roda em modo DRY-RUN (so mostra o que faria). Use --execute para
gravar de fato nos ambientes de destino.

Uso:
    python scripts/replicate_requisitos_anonimizado.py \
        --source https://api.prod.example \
        --target https://api.stg.example \
        --target https://api.dev.example
        # adicione --execute para gravar de verdade
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from typing import Any

try:
    from scripts.runtime_url_policy import require_authorized_runtime_url
except ModuleNotFoundError:  # execução direta: python scripts/replicate_requisitos_anonimizado.py
    from runtime_url_policy import require_authorized_runtime_url

ORIGEM_MARCADOR = 'origem-replicacao-anonimizada'


def _get_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    url = require_authorized_runtime_url(url, label="URL de leitura da replicação")
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - URL operacional validada pela política compartilhada
        return json.loads(resp.read().decode('utf-8'))


def _post_json(url: str, body: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    url = require_authorized_runtime_url(url, label="URL de escrita da replicação")
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


def _pseudonimo(solicitante: str) -> str:
    digest = hashlib.sha256(solicitante.strip().lower().encode('utf-8')).hexdigest()[:8]
    return f'demo-{digest}@reqsys-anonimizado.local'


def _marca_origem(codigo_origem: str) -> str:
    return f'\n\n[{ORIGEM_MARCADOR}: {codigo_origem}]'


def montar_payload_anonimizado(requisito: dict[str, Any]) -> dict[str, Any]:
    codigo_origem = requisito['codigo']
    return {
        'titulo': requisito['titulo'],
        'descricao': requisito['descricao'] + _marca_origem(codigo_origem),
        'urgencia': requisito.get('urgencia', 'media'),
        'area': requisito['area'],
        'sistema': requisito['sistema'],
        'solicitante': _pseudonimo(requisito['solicitante']),
        'impacto_regulatorio': requisito.get('impacto_regulatorio', False),
    }


def ja_replicado(descricoes_existentes: set[str], codigo_origem: str) -> bool:
    marca = f'{ORIGEM_MARCADOR}: {codigo_origem}'
    return any(marca in descricao for descricao in descricoes_existentes)


def replicar(source_url: str, target_url: str, execute: bool, limit: int | None) -> dict[str, Any]:
    source_url = require_authorized_runtime_url(source_url, label="runtime de origem")
    target_url = require_authorized_runtime_url(target_url, label="runtime de destino")
    origem = _get_json(f'{source_url}/v1/requisitos').get('data') or []
    destino_atual = _get_json(f'{target_url}/v1/requisitos').get('data') or []
    descricoes_existentes = {item.get('descricao', '') for item in destino_atual}

    if limit is not None:
        origem = origem[:limit]

    planejado = []
    for requisito in origem:
        if ja_replicado(descricoes_existentes, requisito['codigo']):
            planejado.append({'codigo_origem': requisito['codigo'], 'acao': 'pular (ja replicado)'})
            continue
        payload = montar_payload_anonimizado(requisito)
        planejado.append({
            'codigo_origem': requisito['codigo'],
            'acao': 'criar' if execute else 'criaria (dry-run)',
            'payload': payload,
        })
        if execute:
            criado = _post_json(f'{target_url}/v1/requisitos', payload)
            planejado[-1]['resultado'] = criado.get('data', {}).get('codigo')

    return {'source': source_url, 'target': target_url, 'itens': planejado}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', required=True, help='Runtime autorizado de origem')
    parser.add_argument('--target', action='append', required=True, help='Runtime autorizado de destino; repetível')
    parser.add_argument('--limit', type=int, default=None, help='Limitar quantidade de requisitos de origem')
    parser.add_argument('--execute', action='store_true', help='Grava de fato (sem isso, roda em dry-run)')
    args = parser.parse_args(argv)

    if not args.execute:
        print('=== DRY-RUN (nada sera gravado; use --execute para aplicar) ===\n')

    resultados = [replicar(args.source, target, args.execute, args.limit) for target in args.target]

    for r in resultados:
        print(f"## {r['source']} -> {r['target']}")
        for item in r['itens']:
            print(f"  - {item['codigo_origem']}: {item['acao']}")
        print()

    print(json.dumps(resultados, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
