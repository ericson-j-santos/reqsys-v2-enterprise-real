#!/usr/bin/env python3
"""
Backup do banco (Postgres via pg_dump, SQLite via copia do arquivo) com
rotacao automatica de backups antigos.

Uso:
  python scripts/backup_database.py                 # roda um backup + rotacao
  python scripts/backup_database.py --retention-days 30
  python scripts/backup_database.py --dry-run        # so mostra o que faria

Variaveis de ambiente (lidas via .env / cofre, mesma resolucao da app):
  DATABASE_URL              alvo do backup (postgresql+psycopg2://... ou sqlite:///...)
  BACKUP_DIR                default: backend/artifacts/backups
  BACKUP_RETENTION_DAYS     default: 14 (dias); arquivos mais antigos sao apagados apos o backup
  PG_DUMP_PATH              override do caminho do binario pg_dump, se nao estiver no PATH
                            (ex.: instalacao padrao do Windows nao adiciona ao PATH:
                            "C:\\Program Files\\PostgreSQL\\<versao>\\bin\\pg_dump.exe")

Ver docs/ADR/ADR-043-backup-rotacao-retencao.md para o racional e os gates.
"""
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.core.config import settings  # noqa: E402
from app.core.telemetry import log_erro, log_evento  # noqa: E402

_DEFAULT_RETENTION_DAYS = 14
_BACKUP_DIR_DEFAULT = Path(__file__).resolve().parents[1] / 'backend' / 'artifacts' / 'backups'


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _resolver_pg_dump() -> str:
    override = os.environ.get('PG_DUMP_PATH')
    if override:
        return override
    encontrado = shutil.which('pg_dump')
    if encontrado:
        return encontrado
    raise FileNotFoundError(
        'pg_dump nao encontrado no PATH. Defina PG_DUMP_PATH apontando para o binario '
        '(ex.: instalacoes Windows costumam ficar em '
        '"C:\\Program Files\\PostgreSQL\\<versao>\\bin\\pg_dump.exe" sem entrar no PATH automaticamente).'
    )


def _backup_postgres(database_url: str, backup_dir: Path, dry_run: bool) -> Path:
    destino = backup_dir / f'reqsys-postgres-{_timestamp()}.dump'
    pg_dump = _resolver_pg_dump()
    comando = [pg_dump, database_url.replace('postgresql+psycopg2://', 'postgresql://'), '-F', 'c', '-f', str(destino)]

    if dry_run:
        log_evento('backup_database.dry_run', engine='postgres', comando=' '.join(comando))
        return destino

    backup_dir.mkdir(parents=True, exist_ok=True)
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(f'pg_dump falhou (rc={resultado.returncode}): {resultado.stderr.strip()}')
    return destino


def _backup_sqlite(database_url: str, backup_dir: Path, dry_run: bool) -> Path:
    origem = Path(urlparse(database_url).path.lstrip('/') if database_url.startswith('sqlite:////') else database_url.replace('sqlite:///', ''))
    if not origem.is_absolute():
        origem = Path(__file__).resolve().parents[1] / 'backend' / origem
    destino = backup_dir / f'reqsys-sqlite-{_timestamp()}.db'

    if dry_run:
        log_evento('backup_database.dry_run', engine='sqlite', origem=str(origem), destino=str(destino))
        return destino

    if not origem.exists():
        raise FileNotFoundError(f'arquivo SQLite nao encontrado: {origem}')

    backup_dir.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(origem.read_bytes())
    return destino


def _rotacionar(backup_dir: Path, retention_days: int, dry_run: bool) -> list[Path]:
    if not backup_dir.exists():
        return []

    cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400
    removidos = []
    for arquivo in backup_dir.glob('reqsys-*'):
        if arquivo.stat().st_mtime < cutoff:
            removidos.append(arquivo)
            if not dry_run:
                arquivo.unlink()
    return removidos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--backup-dir', default=None, help='Override de BACKUP_DIR')
    parser.add_argument('--retention-days', type=int, default=None, help='Override de BACKUP_RETENTION_DAYS')
    parser.add_argument('--dry-run', action='store_true', help='Nao escreve nem apaga nada, so mostra o plano')
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir) if args.backup_dir else _BACKUP_DIR_DEFAULT
    retention_days = args.retention_days if args.retention_days is not None else _DEFAULT_RETENTION_DAYS
    database_url = settings.database_url

    try:
        if database_url.startswith('postgresql'):
            destino = _backup_postgres(database_url, backup_dir, args.dry_run)
        elif database_url.startswith('sqlite'):
            destino = _backup_sqlite(database_url, backup_dir, args.dry_run)
        else:
            log_erro('backup_database.unsupported_engine', f'DATABASE_URL nao suportado para backup: {database_url.split(":")[0]}')
            return 1

        removidos = _rotacionar(backup_dir, retention_days, args.dry_run)

        log_evento(
            'backup_database.completed',
            destino=str(destino),
            dry_run=args.dry_run,
            retention_days=retention_days,
            backups_removidos=len(removidos),
        )
        print(f'Backup: {destino}')
        if removidos:
            print(f'Rotacao: {len(removidos)} backup(s) com mais de {retention_days} dias removido(s)')
        return 0
    except Exception as exc:
        log_erro('backup_database.failed', exc)
        print(f'ERRO: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
