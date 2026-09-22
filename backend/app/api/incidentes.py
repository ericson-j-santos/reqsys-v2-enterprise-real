from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.services.recomendacoes_ia import listar_incidentes, obter_incidente

router = APIRouter(prefix='/v1/incidentes', tags=['Incidentes IA'])


@router.get('')
def listar(
    limit: int = Query(default=30, ge=1, le=100),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return ok(listar_incidentes(db, limit=limit, search=search))


@router.get('/{incidente_id}')
def obter(incidente_id: int, db: Session = Depends(get_db)):
    incidente = obter_incidente(db, incidente_id)
    if not incidente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Incidente/requisito não encontrado.')
    return ok(incidente)
