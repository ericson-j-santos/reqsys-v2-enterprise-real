from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import SessionLocal
from app.services.ai_quality import registrar_snapshot_qualidade_ia


def main():
    db = SessionLocal()
    try:
        snapshot = registrar_snapshot_qualidade_ia(db)
        print(
            f"Snapshot gerado com sucesso. id={snapshot['id']} score={snapshot['score_geral']} criado_em={snapshot['criado_em']}"
        )
    finally:
        db.close()


if __name__ == '__main__':
    main()
