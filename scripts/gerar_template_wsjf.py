#!/usr/bin/env python3
"""Regenera o template canonico `templates/wsjf/WSJF.xlsx.base64`.

O template versionado e a fonte do WSJF.xlsx enviado ao tenant por
`scripts/bootstrap_wsjf_m365_dev.py`. Ele e gerado — nunca editado a mao — a
partir de `wsjf_workbook_package.gerar_wsjf_xlsx()`, e
`backend/tests/test_wsjf_workbook_package.py` falha se o arquivo versionado
divergir do gerador.

    python scripts/gerar_template_wsjf.py           # regrava o template
    python scripts/gerar_template_wsjf.py --check   # so verifica (CI)
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'backend'))

from wsjf_workbook_package import (  # noqa: E402
    TABELA,
    gerar_wsjf_xlsx,
    validar_workbook_wsjf,
)

TEMPLATE = RAIZ / 'templates' / 'wsjf' / 'WSJF.xlsx.base64'
LARGURA = 76


def codificar(xlsx: bytes) -> str:
    texto = base64.b64encode(xlsx).decode('ascii')
    linhas = [texto[i : i + LARGURA] for i in range(0, len(texto), LARGURA)]
    return '\n'.join(linhas) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description='Gera o template canonico WSJF.xlsx')
    parser.add_argument('--check', action='store_true', help='nao grava; falha se estiver desatualizado')
    args = parser.parse_args()

    xlsx = gerar_wsjf_xlsx()
    validacao = validar_workbook_wsjf(xlsx)
    if not validacao['ok']:
        print(f"Template gerado invalido: {validacao['erros']}", file=sys.stderr)
        return 1

    conteudo = codificar(xlsx)
    atual = TEMPLATE.read_text(encoding='ascii') if TEMPLATE.exists() else ''
    if args.check:
        if atual != conteudo:
            print(f'{TEMPLATE} desatualizado; rode python scripts/gerar_template_wsjf.py', file=sys.stderr)
            return 1
        print(f'{TEMPLATE} em dia ({TABELA}, {len(xlsx)} bytes)')
        return 0

    TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATE.write_text(conteudo, encoding='ascii')
    print(f'{TEMPLATE} regravado ({TABELA}, {len(xlsx)} bytes)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
