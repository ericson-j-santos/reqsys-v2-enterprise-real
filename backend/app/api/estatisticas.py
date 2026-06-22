from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.services.estatisticas import gerar_snapshot_estatisticas

router = APIRouter(prefix='/v1/estatisticas', tags=['Estatísticas'])


@router.get('')
def obter_estatisticas(
    x_correlation_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    correlation_id = x_correlation_id or str(uuid4())
    snapshot = gerar_snapshot_estatisticas(db, correlation_id)
    return ok(snapshot, correlation_id)
