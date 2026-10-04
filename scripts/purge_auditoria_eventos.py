#!/usr/bin/env python3
"""
Aplica a retencao configurada sobre auditoria_eventos (ADR-043), para uso
em agendamento (cron / Windows Task Scheduler / workflow agendado), sem
depender de um token JWT admin como o endpoint POST /v1/auditoria/purgar.

Uso:
  python scripts/purge_auditoria_eventos.py                    # usa AUDITORIA_RETENTION_DAYS (default 180 dias)
  python scripts/purge_auditoria_eventos.py --retention-days 90

Ver docs/ADR/ADR-043-backup-rotacao-retencao.md para o racional e os gates.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.db import SessionLocal  # noqa: E402
from app.services.data_retention import purgar_auditoria_eventos  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--retention-days', type=int, default=None, help='Override de AUDITORIA_RETENTION_DAYS')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        resultado = purgar_auditoria_eventos(db, retention_days=args.retention_days, correlation_id='scheduler-purge-auditoria')
    finally:
        db.close()

    print(f"Retencao: {resultado['retention_days']} dias | removidos: {resultado['registros_removidos']} | cutoff: {resultado['cutoff']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
