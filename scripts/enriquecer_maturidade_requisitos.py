#!/usr/bin/env python3
"""Enriquece requisitos para maturidade operacional (BDD + avanço no pipeline)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from app.db import SessionLocal  # noqa: E402
from app.services.requisitos_maturidade import enriquecer_maturidade_requisitos  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Enriquecer maturidade dos requisitos no banco operacional.')
    parser.add_argument('--dry-run', action='store_true', help='Calcula impacto sem persistir alterações.')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        resultado = enriquecer_maturidade_requisitos(db, aplicar=not args.dry_run)
        payload = {
            'dry_run': args.dry_run,
            'total': resultado.total,
            'atualizados_status': resultado.atualizados_status,
            'atualizados_bdd': resultado.atualizados_bdd,
            'cobertura_bdd_percentual': resultado.cobertura_bdd_percentual,
            'conclusao_percentual': resultado.conclusao_percentual,
            'distribuicao_status': resultado.distribuicao_status,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
