#!/usr/bin/env python3
"""
Copia os dados de um SQLite existente para um Postgres ja com o schema criado
(via `alembic upgrade head` ou `Base.metadata.create_all`), tabela por tabela,
na ordem de dependencia de foreign keys.

Uso:
  python scripts/migrate_sqlite_to_postgres.py \
      --sqlite-url sqlite:////data/reqsys.db \
      --postgres-url postgresql+psycopg2://user:pass@host:5432/reqsys

  python scripts/migrate_sqlite_to_postgres.py --sqlite-url ... --postgres-url ... --dry-run

Pre-requisitos:
  - O Postgres de destino ja deve ter o schema (rode `alembic upgrade head` ou
    deixe a app subir uma vez com create_all antes de migrar os dados).
  - Faca um backup do SQLite de origem antes (scripts/backup_database.py) e do
    Postgres de destino se ele ja tiver dados.

Ver docs/runbooks/migracao-postgres-fly.md para o procedimento completo de
corte em hml/prod (Fly.io).
"""
import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, insert, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

import app.main  # noqa: E402,F401  (registra todos os models em Base.metadata)
from app.db import Base  # noqa: E402


def conectar_postgres(postgres_url: str):
    """create_engine + connect com mensagem clara se a conexao falhar.

    No Windows com locale pt-BR, psycopg2/libpq pode devolver a mensagem de
    erro (credenciais invalidas, banco inexistente, conexao recusada) num
    encoding que nao e UTF-8, e o driver quebra com UnicodeDecodeError em vez
    de expor o erro real de conexao. Convertemos isso numa mensagem legivel.
    """
    engine = create_engine(postgres_url)
    try:
        conexao = engine.connect()
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            f'Falha ao conectar em {postgres_url.split("@")[-1]}: o driver nao '
            'conseguiu decodificar a mensagem de erro do Postgres (comum no '
            'Windows com locale pt-BR). A causa real costuma ser credenciais '
            'invalidas, banco inexistente ou host/porta incorretos — confira '
            'esses dados manualmente (ex.: `psql` com a mesma URL).'
        ) from exc
    return engine, conexao


def migrar(sqlite_url: str, postgres_url: str, dry_run: bool) -> dict:
    origem = create_engine(sqlite_url)
    destino, conn_destino_ctx = conectar_postgres(postgres_url)

    resumo: dict[str, int] = {}

    try:
        with origem.connect() as conn_origem:
            tabelas_origem = set(inspect(conn_origem).get_table_names())
            for tabela in Base.metadata.sorted_tables:
                if tabela.name not in tabelas_origem:
                    resumo[tabela.name] = 0
                    continue

                linhas = [dict(row._mapping) for row in conn_origem.execute(tabela.select())]
                resumo[tabela.name] = len(linhas)

                if dry_run or not linhas:
                    continue

                conn_destino_ctx.execute(insert(tabela), linhas)

        if not dry_run:
            conn_destino_ctx.commit()
    finally:
        conn_destino_ctx.close()

    return resumo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sqlite-url', required=True)
    parser.add_argument('--postgres-url', required=True)
    parser.add_argument('--dry-run', action='store_true', help='So conta as linhas por tabela, nao escreve nada')
    args = parser.parse_args()

    if not args.postgres_url.startswith('postgresql'):
        print('ERRO: --postgres-url precisa ser um destino postgresql://', file=sys.stderr)
        return 1
    if not args.sqlite_url.startswith('sqlite'):
        print('ERRO: --sqlite-url precisa ser uma origem sqlite://', file=sys.stderr)
        return 1

    resumo = migrar(args.sqlite_url, args.postgres_url, args.dry_run)

    total = sum(resumo.values())
    for tabela, count in resumo.items():
        if count:
            print(f'  {tabela}: {count} linha(s)')
    print(f"{'[dry-run] ' if args.dry_run else ''}Total: {total} linha(s) em {len(resumo)} tabela(s)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
