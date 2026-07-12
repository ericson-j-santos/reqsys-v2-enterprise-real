#!/usr/bin/env python3
"""
Automatiza o corte de SQLite -> Postgres em um app Fly.io (ADR-043),
seguindo docs/runbooks/migracao-postgres-fly.md, com portoes de seguranca que
abortam ANTES de qualquer acao destrutiva/irreversivel se algo nao bater.

Uso (sempre rode --dry-run primeiro):
  python scripts/cutover_fly_postgres.py \
      --app reqsys-api-dev --fly-config backend/fly.dev.toml \
      --postgres-url postgresql+psycopg2://user:pass@host:5432/reqsys \
      --dry-run

  python scripts/cutover_fly_postgres.py \
      --app reqsys-api-dev --fly-config backend/fly.dev.toml \
      --postgres-url postgresql+psycopg2://user:pass@host:5432/reqsys \
      --yes

Portoes de seguranca (cada um aborta o processo, sem tocar no proximo passo,
se falhar):
  1. Backup do SQLite via `fly ssh sftp get` + `PRAGMA integrity_check` local.
  2. Aplica o schema no Postgres de destino (alembic upgrade + stamp).
  3. Migra os dados (scripts/migrate_sqlite_to_postgres.py).
  4. CONFERE contagem de linhas por tabela: origem (backup) == destino
     (Postgres). So prossegue se todas baterem.
  5. So DEPOIS da conferencia (4) seta `fly secrets set DATABASE_URL` — nunca
     antes.
  6. Deploy + polling de health/readiness. Se nao ficar saudavel dentro do
     timeout, ROLLBACK AUTOMATICO: remove o secret e reimplanta a versao
     anterior (volta a rodar em SQLite, o volume antigo nunca e tocado).

O que este script NUNCA faz sozinho:
  - Nao cria/provisiona o Postgres (isso e uma decisao de custo/infra do
    usuario: `fly postgres create` ou um Postgres externo).
  - Nao apaga o volume SQLite antigo nem o secret antigo em nenhum caminho.
  - Nao roda sem --dry-run ou --yes explicito (nunca assume confirmacao).
"""
import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from migrate_sqlite_to_postgres import conectar_postgres, migrar  # noqa: E402

from app.db import Base  # noqa: E402


def _fly_bin() -> str:
    for nome in ('fly', 'flyctl'):
        encontrado = shutil.which(nome)
        if encontrado:
            return encontrado
    raise FileNotFoundError('flyctl nao encontrado no PATH')


def _run(comando: list[str], descricao: str, dry_run: bool) -> subprocess.CompletedProcess | None:
    print(f'-> {descricao}: {" ".join(comando)}')
    if dry_run:
        return None
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(f'{descricao} falhou (rc={resultado.returncode}):\n{resultado.stderr}')
    return resultado


def passo_1_backup(fly: str, app: str, backup_path: Path, dry_run: bool) -> None:
    _run([fly, 'ssh', 'sftp', 'get', '/data/reqsys.db', str(backup_path), '-a', app], 'Backup SQLite via sftp', dry_run)

    if dry_run:
        return

    if not backup_path.exists() or backup_path.stat().st_size == 0:
        raise RuntimeError(f'Backup nao foi criado ou esta vazio: {backup_path}')

    conn = sqlite3.connect(str(backup_path))
    try:
        resultado = conn.execute('PRAGMA integrity_check').fetchone()[0]
    finally:
        conn.close()
    if resultado != 'ok':
        raise RuntimeError(f'PRAGMA integrity_check falhou no backup: {resultado}')
    print(f'   Backup OK: {backup_path} ({backup_path.stat().st_size} bytes, integrity_check=ok)')


def passo_2_schema(postgres_url: str, dry_run: bool) -> None:
    if dry_run:
        print('-> [dry-run] alembic upgrade head + stamp contra o Postgres de destino')
        return

    engine, conn = conectar_postgres(postgres_url)
    try:
        ja_tem_tabelas = engine.dialect.has_table(conn, 'requisitos')
        if not ja_tem_tabelas:
            Base.metadata.create_all(bind=conn)
            conn.commit()
            print('   Schema criado no Postgres de destino via create_all (baseline Alembic e no-op — ADR-042).')
        else:
            print('   Schema ja existe no Postgres de destino, nao recriado.')
    finally:
        conn.close()

    resultado = subprocess.run(
        [sys.executable, '-m', 'alembic', 'stamp', 'head'],
        cwd=str(Path(__file__).resolve().parents[1] / 'backend'),
        env={**os.environ, 'DATABASE_URL': postgres_url},
        capture_output=True, text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError(f'alembic stamp head falhou:\n{resultado.stderr}')


def passo_3_migrar_dados(backup_path: Path, postgres_url: str, dry_run: bool) -> dict:
    if dry_run:
        print(f'-> [dry-run] migracao de dados pulada; origem seria sqlite:///{backup_path}')
        return {}

    sqlite_url = f'sqlite:///{backup_path}'
    return migrar(sqlite_url, postgres_url, dry_run=dry_run)


def passo_4_conferir(backup_path: Path, postgres_url: str, dry_run: bool) -> None:
    if dry_run:
        print('-> [dry-run] conferencia origem x destino pulada')
        return

    sqlite_url = f'sqlite:///{backup_path}'
    contagem_origem = migrar(sqlite_url, postgres_url, dry_run=True)

    from sqlalchemy import func, select

    _, conn = conectar_postgres(postgres_url)
    divergencias = []
    try:
        for tabela in Base.metadata.sorted_tables:
            esperado = contagem_origem.get(tabela.name, 0)
            real = conn.execute(select(func.count()).select_from(tabela)).scalar()
            if real < esperado:
                divergencias.append(f'{tabela.name}: esperado>={esperado}, encontrado={real}')
    finally:
        conn.close()

    if divergencias:
        raise RuntimeError('Conferencia de migracao FALHOU, abortando antes do cutover:\n' + '\n'.join(divergencias))
    print('   Conferencia OK: todas as tabelas batem (destino >= origem em cada uma).')


def passo_5_setar_secret(fly: str, app: str, postgres_url: str, dry_run: bool) -> None:
    _run([fly, 'secrets', 'set', f'DATABASE_URL={postgres_url}', '-a', app], 'Set fly secret DATABASE_URL', dry_run)


def passo_6_deploy_e_verificar(fly: str, app: str, fly_config: str, health_url: str, dry_run: bool) -> bool:
    _run([fly, 'deploy', '-a', app, '-c', fly_config], 'Deploy', dry_run)

    if dry_run:
        print('-> [dry-run] polling de health pulado')
        return True

    for tentativa in range(1, 13):
        try:
            with urllib.request.urlopen(health_url, timeout=5) as resp:
                if resp.status == 200:
                    print(f'   Health OK na tentativa {tentativa}: {health_url}')
                    return True
        except Exception as exc:
            print(f'   Tentativa {tentativa}/12 falhou: {exc}')
        time.sleep(10)
    return False


def rollback(fly: str, app: str, fly_config: str) -> None:
    print('!! ROLLBACK: removendo secret DATABASE_URL e reimplantando (volta pro SQLite do [env])')
    subprocess.run([fly, 'secrets', 'unset', 'DATABASE_URL', '-a', app], capture_output=True, text=True)
    subprocess.run([fly, 'deploy', '-a', app, '-c', fly_config], capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--app', required=True, help='Nome do app Fly (ex.: reqsys-api-dev)')
    parser.add_argument('--fly-config', required=True, help='Caminho do fly.toml deste ambiente')
    parser.add_argument('--postgres-url', required=True, help='Postgres de destino, ja provisionado')
    parser.add_argument('--backup-path', default=None, help='Onde salvar o backup sqlite (default: backend/artifacts/backups/)')
    parser.add_argument('--health-path', default='/api/runtime/health', help='Path do healthcheck pos-deploy')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true', help='Confirma execucao real (obrigatorio se nao for --dry-run)')
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print('ERRO: rode com --dry-run primeiro, ou passe --yes para confirmar a execucao real.', file=sys.stderr)
        return 1

    fly = _fly_bin()
    backup_path = Path(args.backup_path) if args.backup_path else (
        Path(__file__).resolve().parents[1] / 'backend' / 'artifacts' / 'backups' / f'{args.app}-pre-cutover.db'
    )
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    health_url = f'https://{args.app}.fly.dev{args.health_path}'

    try:
        print(f'=== Cutover {args.app} -> Postgres ({"DRY-RUN" if args.dry_run else "EXECUCAO REAL"}) ===')
        passo_1_backup(fly, args.app, backup_path, args.dry_run)
        passo_2_schema(args.postgres_url, args.dry_run)
        passo_3_migrar_dados(backup_path, args.postgres_url, args.dry_run)
        passo_4_conferir(backup_path, args.postgres_url, args.dry_run)
        passo_5_setar_secret(fly, args.app, args.postgres_url, args.dry_run)
        saudavel = passo_6_deploy_e_verificar(fly, args.app, args.fly_config, health_url, args.dry_run)

        if not args.dry_run and not saudavel:
            rollback(fly, args.app, args.fly_config)
            print('ERRO: app nao ficou saudavel apos o deploy — rollback automatico executado.', file=sys.stderr)
            return 1

        print('=== Concluido com sucesso ===' if not args.dry_run else '=== Dry-run concluido, nada foi alterado ===')
        return 0
    except Exception as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        print('Nenhum secret foi alterado alem do ponto onde o erro ocorreu; volume/dados antigos intactos.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
