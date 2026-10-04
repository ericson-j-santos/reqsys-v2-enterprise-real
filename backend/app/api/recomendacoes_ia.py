from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.services.recomendacoes_ia import (
    criar_recomendacao,
    listar_recomendacoes,
    obter_recomendacao,
    registrar_decisao,
    registrar_outcome,
)

router = APIRouter(prefix='/v1/recomendacoes', tags=['Recomendações IA'])


class RecomendacaoCriar(BaseModel):
    id_incidente: int
    titulo: str
    contexto_incidente: str | None = None
    tipo_recomendacao: str
    confianca_ia: float = Field(default=0.8, ge=0.0, le=1.0)
    recomendacao: str
    modelo: str | None = None
    score_inicial: float | None = Field(default=None, ge=0.0, le=1.0)


class DecisaoCriar(BaseModel):
    aceita: bool
    motivo_decisao: str | None = None
    decidido_por: str | None = None


class OutcomeCriar(BaseModel):
    foi_aplicada: bool
    versao_aplicada: str | None = None
    outcome_positivo: bool | None = None
    score_pos_correcao: float | None = Field(default=None, ge=0.0, le=1.0)
    observacao: str | None = None


@router.get('')
def listar(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    return ok(listar_recomendacoes(db, limit=limit))


@router.get('/{recomendacao_id}')
def obter(recomendacao_id: int, db: Session = Depends(get_db)):
    recomendacao = obter_recomendacao(db, recomendacao_id)
    if not recomendacao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Recomendação não encontrada.')
    return ok(recomendacao)


@router.post('', status_code=status.HTTP_201_CREATED)
def criar(body: RecomendacaoCriar, db: Session = Depends(get_db)):
    try:
        return ok(criar_recomendacao(db, body.model_dump()), meta={'created': True})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post('/{recomendacao_id}/decisao')
def salvar_decisao(recomendacao_id: int, body: DecisaoCriar, db: Session = Depends(get_db)):
    try:
        return ok(registrar_decisao(db, recomendacao_id, body.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/{recomendacao_id}/outcome')
def salvar_outcome(recomendacao_id: int, body: OutcomeCriar, db: Session = Depends(get_db)):
    try:
        return ok(registrar_outcome(db, recomendacao_id, body.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
