from time import time_ns
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from app.core.envelope import ok
from app.db import get_db
from app.models.requisito import Requisito
from app.schemas.requisito import RequisitoCriar, RequisitoOut
from app.services.auditoria import registrar_evento

router = APIRouter(prefix='/v1/requisitos', tags=['Requisitos'])

@router.get('')
def listar(db: Session = Depends(get_db)):
    return ok([RequisitoOut.model_validate(r).model_dump() for r in db.query(Requisito).order_by(Requisito.id.desc()).all()])

@router.post('')
def criar(payload: RequisitoCriar, db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    codigo = f"REQ-{str(time_ns())[-9:]}"
    req = Requisito(codigo=codigo, **payload.model_dump())
    db.add(req); db.commit(); db.refresh(req)
    registrar_evento(db, x_correlation_id or 'sem-correlation-id', payload.solicitante, 'REQUISITO_CRIADO', 'requisito', req.id, '{"campos":"minimizados"}')
    return ok(RequisitoOut.model_validate(req).model_dump(), x_correlation_id)
