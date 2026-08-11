#!/usr/bin/env python3
"""Confirma ao vivo os nomes reais das 4 views/tabelas de origem do e-mail
Prospecção Movimento — Portabilidade Consignado (#2861, gap #1 — ver
docs/architecture/movimento-email-pipeline.md).

Hoje `app/services/movimento_email/sql/*.sql` usa nomes placeholder
(`vw_prospeccao_movimento_*`) porque nenhuma credencial de origem foi
configurada nesta sessão. Este script fecha esse gap assim que alguém tiver
o DSN real:

  python scripts/verificar_movimento_email_fontes.py status
      Mostra se MOVIMENTO_EMAIL_SOURCE_DSN está configurado no .env (nunca
      imprime a connection string em texto puro).

  python scripts/verificar_movimento_email_fontes.py verificar
      Conecta no SQL Server real via pyodbc e:
        1. procura, em INFORMATION_SCHEMA.TABLES/VIEWS, candidatos cujo nome
           contenha "prospec", "movimento", "pendenc", "fechamento",
           "consignado" ou "portabilidade";
        2. checa se os 4 nomes hoje assumidos em sql/*.sql já existem e, se
           existirem, compara as colunas encontradas com as que o código
           espera (ver `_COLUNAS_ESPERADAS` abaixo).

Não grava nada no .env (a connection string completa deve ser configurada
manualmente em MOVIMENTO_EMAIL_SOURCE_DSN — é sensível e específica demais
do ambiente para captura campo a campo, ao contrário do padrão usado em
scripts/configurar_redmine_sync_queue.py).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / 'backend'))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_ROOT / '.env', override=False)

from app.core.config import Settings  # noqa: E402

_PADROES_CANDIDATOS = ('prospec', 'movimento', 'pendenc', 'fechamento', 'consignado', 'portabilidade')

# Nomes hoje assumidos em app/services/movimento_email/sql/*.sql -> colunas
# que o código espera (ver models.py / repository.py).
_VIEWS_ASSUMIDAS: dict[str, list[str]] = {
    'vw_prospeccao_movimento_fechamento_diario': ['indicador', 'valor', 'observacao', 'data_referencia'],
    'vw_prospeccao_movimento_pendencias_cadastro': ['protocolo', 'cliente', 'cpf', 'pendencia', 'dias_em_aberto', 'responsavel', 'data_referencia'],
    'vw_prospeccao_movimento_pendencias_historicas': ['periodo_referencia', 'pendencia', 'quantidade', 'percentual', 'data_referencia'],
    'vw_prospeccao_movimento_pendencias_observacao': ['protocolo', 'tipo_inconsistencia', 'descricao', 'etapa', 'data_referencia'],
}


def _linha(texto: str = '') -> None:
    print(texto)


def _titulo(texto: str) -> None:
    _linha()
    _linha('=' * 78)
    _linha(f' {texto}')
    _linha('=' * 78)


def cmd_status(_args: argparse.Namespace) -> int:
    _titulo('Status — origem de dados do e-mail Prospecção Movimento (#2861)')
    cfg = Settings()
    dsn = cfg.movimento_email_source_dsn
    if dsn:
        _linha(f'  [OK]     MOVIMENTO_EMAIL_SOURCE_DSN configurado ({len(dsn)} caracteres)')
        _linha('  Rode "verificar" para confirmar os nomes reais das views contra o SQL Server.')
        return 0
    _linha('  [FALTA]  MOVIMENTO_EMAIL_SOURCE_DSN não configurado no .env')
    _linha('  Sem isso, o job (/v1/movimento-email/jobs/executar) nunca consegue extrair dados reais.')
    _linha('  Peça à equipe de dados a connection string do SQL Server que hoje alimenta o SSRS legado')
    _linha('  de Prospecção Movimento e grave em .env, ex.:')
    _linha('    MOVIMENTO_EMAIL_SOURCE_DSN=Driver={ODBC Driver 18 for SQL Server};Server=...;Database=...;UID=...;PWD=...;Encrypt=yes')
    return 1


def _listar_candidatos(cursor) -> list[tuple[str, str, str]]:
    cursor.execute(
        """
        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
    )
    linhas = cursor.fetchall()
    candidatos = []
    for schema, nome, tipo in linhas:
        nome_lower = nome.lower()
        if any(padrao in nome_lower for padrao in _PADROES_CANDIDATOS):
            candidatos.append((schema, nome, tipo))
    return candidatos


def _colunas_de(cursor, nome_view: str) -> list[str] | None:
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
        nome_view,
    )
    linhas = cursor.fetchall()
    if not linhas:
        return None
    return [str(linha[0]) for linha in linhas]


def cmd_verificar(_args: argparse.Namespace) -> int:
    cfg = Settings()
    if not cfg.movimento_email_source_dsn:
        _titulo('Bloqueado')
        _linha('  MOVIMENTO_EMAIL_SOURCE_DSN não configurado — rode "status" para instruções.')
        return 1

    try:
        import pyodbc
    except ImportError:
        _titulo('Bloqueado')
        _linha('  Pacote "pyodbc" não instalado neste ambiente. Rode: pip install -r backend/requirements.txt')
        return 1

    _titulo('Conectando no SQL Server de origem')
    try:
        conexao = pyodbc.connect(cfg.movimento_email_source_dsn, timeout=cfg.movimento_email_query_timeout_seconds)
    except pyodbc.Error as exc:
        _linha(f'  [ERRO]   Falha ao conectar: {exc}')
        return 1

    erros: list[str] = []
    try:
        cursor = conexao.cursor()

        _titulo('Candidatos por nome (INFORMATION_SCHEMA.TABLES)')
        candidatos = _listar_candidatos(cursor)
        if not candidatos:
            _linha('  Nenhuma tabela/view com nome contendo prospec/movimento/pendenc/fechamento/'
                   'consignado/portabilidade foi encontrada neste banco.')
            erros.append('Nenhum candidato de nome encontrado — confirme se o DSN aponta para o banco correto.')
        else:
            for schema, nome, tipo in candidatos:
                _linha(f'  [{tipo:<10}] {schema}.{nome}')

        _titulo('Views assumidas em sql/*.sql — existem?')
        for nome_view, colunas_esperadas in _VIEWS_ASSUMIDAS.items():
            colunas_reais = _colunas_de(cursor, nome_view)
            if colunas_reais is None:
                _linha(f'  [FALTA]  {nome_view}')
                erros.append(f'"{nome_view}" não existe neste banco — atualize sql/*.sql com o nome real.')
                continue
            faltando = [c for c in colunas_esperadas if c not in colunas_reais]
            if faltando:
                _linha(f'  [DIVERGE] {nome_view} — colunas esperadas ausentes: {", ".join(faltando)}')
                erros.append(f'"{nome_view}" existe mas faltam colunas: {", ".join(faltando)} (colunas reais: {", ".join(colunas_reais)})')
            else:
                _linha(f'  [OK]     {nome_view} — todas as colunas esperadas presentes')
    finally:
        conexao.close()

    _titulo('Resumo')
    if erros:
        _linha(f'  {len(erros)} problema(s) encontrado(s):')
        for item in erros:
            _linha(f'    - {item}')
        _linha('\n  Use a lista de candidatos acima para corrigir os nomes em')
        _linha('  backend/app/services/movimento_email/sql/*.sql e rode de novo.')
        return 1
    _linha('  Todas as 4 views existem com as colunas esperadas — pronto para produção.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='comando', required=True)

    p_status = sub.add_parser('status', help='Mostra se MOVIMENTO_EMAIL_SOURCE_DSN está configurado.')
    p_status.set_defaults(func=cmd_status)

    p_verificar = sub.add_parser('verificar', help='Conecta no SQL Server real e confirma/corrige os nomes das views.')
    p_verificar.set_defaults(func=cmd_verificar)

    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
