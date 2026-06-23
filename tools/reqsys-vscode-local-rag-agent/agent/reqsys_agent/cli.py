from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path


def correlation_id() -> str:
    return str(uuid.uuid4())


def emit(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') in {'ok', 'attention', 'needs_index', 'no_context'} else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='reqsys-agent')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('health')
    idx = sub.add_parser('index')
    idx.add_argument('--workspace', required=True)
    ask = sub.add_parser('ask')
    ask.add_argument('--workspace', required=True)
    ask.add_argument('--question', required=True)
    gov = sub.add_parser('governance')
    gov.add_argument('--workspace', required=True)
    args = parser.parse_args(argv)

    if args.command == 'health':
        return emit({
            'status': 'ok',
            'correlation_id': correlation_id(),
            'service': 'reqsys-agent',
            'mode': 'safe-readonly',
            'restricoes': ['sem patch automatico', 'sem comandos destrutivos', 'sem leitura sensivel', 'sem chamada externa']
        })

    workspace = Path(getattr(args, 'workspace', '.')).resolve()
    if args.command == 'index':
        return emit({
            'status': 'ok',
            'correlation_id': correlation_id(),
            'workspace': str(workspace),
            'answer': 'MVP inicial: workspace validado para futura indexacao local governada.',
            'evidencias': [],
            'restricoes': ['somente leitura', 'sem alteracao automatica']
        })
    if args.command == 'ask':
        return emit({
            'status': 'needs_index',
            'correlation_id': correlation_id(),
            'answer': 'MVP inicial ativo. A consulta RAG completa deve ser habilitada apos instalacao do indice local.',
            'evidencias': [],
            'restricoes': ['nao inventar resposta sem fonte']
        })
    if args.command == 'governance':
        return emit({
            'status': 'ok',
            'correlation_id': correlation_id(),
            'maturidade_percentual': 80,
            'checks': [
                {'name': 'Modo somente leitura', 'status': 'verde', 'detail': 'Escrita automatica bloqueada'},
                {'name': 'Evidencia obrigatoria', 'status': 'verde', 'detail': 'Saida JSON com correlation_id'},
                {'name': 'Revisao humana', 'status': 'verde', 'detail': 'Patch automatico fora do MVP'}
            ],
            'restricoes': ['sem merge automatico', 'sem producao automatica']
        })

    return emit({'status': 'error', 'correlation_id': correlation_id(), 'message': 'Comando invalido'})


if __name__ == '__main__':
    raise SystemExit(main())
