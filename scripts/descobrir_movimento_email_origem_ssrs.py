#!/usr/bin/env python3
"""Descobre servidor/banco/objetos do SSRS sem expor credenciais."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.movimento_email.ssrs_discovery import descobrir_origem_ssrs  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Analisa arquivos .rdl/.rds exportados do SSRS e extrai metadados seguros da origem SQL.'
    )
    parser.add_argument(
        'caminho',
        nargs='?',
        default=os.environ.get('MOVIMENTO_EMAIL_SSRS_EXPORT_PATH', ''),
        help='Arquivo RDL/RDS ou diretório exportado. Alternativa: MOVIMENTO_EMAIL_SSRS_EXPORT_PATH.',
    )
    parser.add_argument('--output', help='Arquivo JSON de evidência a gravar.')
    parser.add_argument('--json', action='store_true', help='Imprime somente JSON.')
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.caminho:
        print('[ERRO] informe caminho RDL/RDS ou MOVIMENTO_EMAIL_SSRS_EXPORT_PATH', file=sys.stderr)
        return 2

    try:
        resultado = descobrir_origem_ssrs(Path(args.caminho))
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f'[ERRO] {exc}', file=sys.stderr)
        return 2

    conteudo = json.dumps(resultado, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        destino = Path(args.output)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding='utf-8')

    if args.json:
        print(conteudo, end='')
        return 0

    print('Descoberta SSRS — Prospecção Movimento')
    print(f"  arquivos analisados: {resultado['arquivos_analisados']}")
    print(f"  servidores: {', '.join(resultado['servidores']) or '[não identificado]'}")
    print(f"  bancos: {', '.join(resultado['bancos']) or '[não identificado]'}")
    print(f"  objetos candidatos: {len(resultado['objetos_sql_candidatos'])}")
    if resultado['data_sources_compartilhados_pendentes']:
        print('  data sources compartilhados ainda precisam ter o .rds exportado:')
        for referencia in resultado['data_sources_compartilhados_pendentes']:
            print(f'    - {referencia}')
    if resultado['dsn_molde_sem_credenciais']:
        print('  molde DSN seguro:')
        print(f"    {resultado['dsn_molde_sem_credenciais']}")
    else:
        print('  molde DSN: indisponível até existir um único servidor e banco identificados')
    if args.output:
        print(f'  evidência JSON: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
