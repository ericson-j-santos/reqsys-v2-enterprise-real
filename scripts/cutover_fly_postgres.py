#!/usr/bin/env python3
"""Recusa permanente do antigo cutover SQLite -> Postgres no Fly.io.

O código que copiava banco, alterava schema, gravava secrets e executava deploy
foi removido. As funções públicas permanecem somente para falhar fechado em
consumidores legados.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

FLYIO_RETIREMENT_GUARD = (
    "Fly.io foi retirado definitivamente em 2026-10-02; "
    "cutover, migracao, secrets, deploy e rollback estao bloqueados."
)


def _retired() -> RuntimeError:
    return RuntimeError(FLYIO_RETIREMENT_GUARD)


def _fly_bin() -> str:
    raise _retired()


def _run(comando: list[str], descricao: str, dry_run: bool):
    raise _retired()


def passo_1_backup(fly: str, app: str, backup_path: Path, dry_run: bool) -> None:
    raise _retired()


def passo_2_schema(postgres_url: str, dry_run: bool) -> None:
    raise _retired()


def passo_3_migrar_dados(backup_path: Path, postgres_url: str, dry_run: bool) -> dict:
    raise _retired()


def passo_4_conferir(backup_path: Path, postgres_url: str, dry_run: bool) -> None:
    raise _retired()


def passo_5_setar_secret(
    fly: str, app: str, postgres_url: str, dry_run: bool
) -> None:
    raise RuntimeError(FLYIO_RETIREMENT_GUARD)


def passo_6_deploy_e_verificar(
    fly: str,
    app: str,
    fly_config: str,
    health_url: str,
    dry_run: bool,
) -> bool:
    raise RuntimeError(FLYIO_RETIREMENT_GUARD)


def rollback(fly: str, app: str, fly_config: str) -> None:
    raise RuntimeError(FLYIO_RETIREMENT_GUARD)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True)
    parser.add_argument("--fly-config", required=True)
    parser.add_argument("--postgres-url", required=True)
    parser.add_argument("--backup-path")
    parser.add_argument("--health-path", default="/api/runtime/health")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if not args.dry_run:
        print(FLYIO_RETIREMENT_GUARD, file=sys.stderr)
        return 78

    # Dry-run tambem e recusado: o antigo plano imprimia DATABASE_URL em claro.
    print(FLYIO_RETIREMENT_GUARD, file=sys.stderr)
    return 78

    # Contrato textual legado: mesmo se este trecho fosse alcancado, o resolver
    # acima falha fechado. Mantido ate os consumidores estaticos serem removidos.
    fly = _fly_bin()  # pragma: no cover  # noqa: F841


if __name__ == "__main__":
    raise SystemExit(main())
