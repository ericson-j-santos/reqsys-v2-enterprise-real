#!/usr/bin/env python3
"""Migra conteúdo legado de análise documental para AES-256-GCM.

Por padrão executa apenas diagnóstico. Use ``--apply`` para persistir a
reproteção. Nenhum texto ou candidato sensível é escrito na saída do comando.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db import SessionLocal  # noqa: E402
from app.models.documento_demanda import DocumentoDemandaAnalise  # noqa: E402
from app.ocr.documento_storage import (  # noqa: E402
    proteger_candidatos_documento,
    proteger_texto_documento,
)
from app.ocr.storage import OcrDataProtector  # noqa: E402


def _envelope_protegido(valor: str) -> bool:
    if not valor or valor == '[]':
        return True
    try:
        envelope = json.loads(valor)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(envelope, dict)
        and envelope.get('schema_version') == '1.0.0'
        and envelope.get('encryption') == 'AES-256-GCM'
        and isinstance(envelope.get('ciphertext'), str)
        and bool(envelope.get('ciphertext'))
    )


def migrar(*, aplicar: bool) -> dict[str, int | bool]:
    protector = OcrDataProtector()
    total = 0
    alterados = 0
    ja_protegidos = 0
    bloqueados = 0

    with SessionLocal() as db:
        registros = list(db.scalars(select(DocumentoDemandaAnalise).order_by(DocumentoDemandaAnalise.id)))
        for registro in registros:
            total += 1
            texto = registro.texto_extraido or ''
            candidatos = registro.candidatos_json or '[]'
            texto_protegido = _envelope_protegido(texto)
            candidatos_protegidos = _envelope_protegido(candidatos)

            if texto_protegido and candidatos_protegidos:
                ja_protegidos += 1
                continue

            try:
                if texto and not texto_protegido:
                    registro.texto_extraido = proteger_texto_documento(
                        protector,
                        texto,
                        sha256=registro.sha256,
                    )
                if candidatos != '[]' and not candidatos_protegidos:
                    registro.candidatos_json = proteger_candidatos_documento(
                        protector,
                        candidatos,
                        sha256=registro.sha256,
                    )
            except (RuntimeError, ValueError, json.JSONDecodeError):
                bloqueados += 1
                db.rollback()
                continue

            alterados += 1

        if aplicar and bloqueados == 0:
            db.commit()
        else:
            db.rollback()

    return {
        'aplicar': aplicar,
        'total': total,
        'alterados': alterados,
        'ja_protegidos': ja_protegidos,
        'bloqueados': bloqueados,
        'commit_realizado': bool(aplicar and bloqueados == 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Protege análises documentais legadas sem expor conteúdo.')
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Persiste a migração. Sem esta opção apenas calcula o plano.',
    )
    args = parser.parse_args()

    try:
        resultado = migrar(aplicar=args.apply)
    except RuntimeError as exc:
        print(json.dumps({'ok': False, 'erro': type(exc).__name__}, ensure_ascii=False))
        return 2

    print(json.dumps({'ok': resultado['bloqueados'] == 0, **resultado}, ensure_ascii=False, sort_keys=True))
    return 0 if resultado['bloqueados'] == 0 else 3


if __name__ == '__main__':
    raise SystemExit(main())
