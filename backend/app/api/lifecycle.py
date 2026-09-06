"""API do caminho único requisito -> execução -> deploy.

As rotas são anexadas ao router canônico de requisitos em ``app.api.__init__``.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.core.service_tokens import ServiceAuthContext, require_admin_or_service_token
from app.db import get_db
from app.models.requisito import Requisito
from app.services.github_redmine import IntegracaoError
from app.services.lifecycle_orchestrator import (
    LifecycleError,
    lifecycle_snapshot,
    register_lifecycle_evidence,
    start_lifecycle,
)

router = APIRouter(prefix='/lifecycle', tags=['Requisitos Lifecycle'])


class LifecycleStartIn(BaseModel):
    github_repo: str = Field(default='ericson-j-santos/reqsys-v2-enterprise-real', min_length=3, max_length=200)
    redmine_project_id: int | None = Field(default=None, gt=0)
    tracker_id: int | None = Field(default=None, gt=0)
    priority_id: int | None = Field(default=None, gt=0)


class LifecycleEvidenceIn(BaseModel):
    provedor: str = Field(default='github', min_length=2, max_length=20)
    tipo: str = Field(min_length=2, max_length=30)
    repo: str = Field(default='ericson-j-santos/reqsys-v2-enterprise-real', min_length=2, max_length=200)
    referencia: str = Field(min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    titulo: str | None = Field(default=None, max_length=1000)
    ambiente: str | None = Field(default=None, max_length=30)


def _correlation_id(value: str | None) -> str:
    return (value or '').strip() or f'lifecycle-{uuid4().hex}'


def _get_requirement(db: Session, requisito_id: int) -> Requisito:
    requisito = db.get(Requisito, requisito_id)
    if not requisito:
        raise HTTPException(status_code=404, detail=f'Requisito {requisito_id} não encontrado.')
    return requisito


def _get_requirement_by_code(db: Session, codigo: str) -> Requisito:
    requisito = db.query(Requisito).filter(Requisito.codigo == codigo.strip()).first()
    if not requisito:
        raise HTTPException(status_code=404, detail=f"Requisito '{codigo}' não encontrado.")
    return requisito


@router.post('/{requisito_id}/iniciar')
def iniciar_lifecycle(
    requisito_id: int,
    payload: LifecycleStartIn | None = None,
    db: Session = Depends(get_db),
    auth: ServiceAuthContext = Depends(require_admin_or_service_token('lifecycle:write')),
    x_correlation_id: str | None = Header(default=None),
):
    requisito = _get_requirement(db, requisito_id)
    payload = payload or LifecycleStartIn()
    correlation_id = _correlation_id(x_correlation_id)

    try:
        result = start_lifecycle(
            db,
            requisito=requisito,
            github_repo=payload.github_repo,
            correlation_id=correlation_id,
            actor=auth.ator,
            redmine_project_id=payload.redmine_project_id,
            tracker_id=payload.tracker_id,
            priority_id=payload.priority_id,
        )
    except (LifecycleError, IntegracaoError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ok(result, correlation_id)


@router.get('/{requisito_id}')
def consultar_lifecycle(
    requisito_id: int,
    db: Session = Depends(get_db),
    _auth: ServiceAuthContext = Depends(require_admin_or_service_token('lifecycle:read')),
    x_correlation_id: str | None = Header(default=None),
):
    requisito = _get_requirement(db, requisito_id)
    return ok(lifecycle_snapshot(db, requisito), _correlation_id(x_correlation_id))


@router.get('/codigo/{codigo}')
def consultar_lifecycle_por_codigo(
    codigo: str,
    db: Session = Depends(get_db),
    _auth: ServiceAuthContext = Depends(require_admin_or_service_token('lifecycle:read')),
    x_correlation_id: str | None = Header(default=None),
):
    requisito = _get_requirement_by_code(db, codigo)
    return ok(lifecycle_snapshot(db, requisito), _correlation_id(x_correlation_id))


@router.post('/{requisito_id}/evidencias')
def registrar_evidencia_lifecycle(
    requisito_id: int,
    payload: LifecycleEvidenceIn,
    db: Session = Depends(get_db),
    auth: ServiceAuthContext = Depends(require_admin_or_service_token('lifecycle:write')),
    x_correlation_id: str | None = Header(default=None),
):
    requisito = _get_requirement(db, requisito_id)
    correlation_id = _correlation_id(x_correlation_id)
    try:
        result = register_lifecycle_evidence(
            db,
            requisito=requisito,
            provedor=payload.provedor,
            tipo=payload.tipo,
            repo=payload.repo,
            referencia=payload.referencia,
            url=payload.url,
            titulo=payload.titulo,
            ambiente=payload.ambiente,
            correlation_id=correlation_id,
            actor=auth.ator,
        )
    except LifecycleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(result, correlation_id)


@router.post('/codigo/{codigo}/evidencias')
def registrar_evidencia_lifecycle_por_codigo(
    codigo: str,
    payload: LifecycleEvidenceIn,
    db: Session = Depends(get_db),
    auth: ServiceAuthContext = Depends(require_admin_or_service_token('lifecycle:write')),
    x_correlation_id: str | None = Header(default=None),
):
    requisito = _get_requirement_by_code(db, codigo)
    correlation_id = _correlation_id(x_correlation_id)
    try:
        result = register_lifecycle_evidence(
            db,
            requisito=requisito,
            provedor=payload.provedor,
            tipo=payload.tipo,
            repo=payload.repo,
            referencia=payload.referencia,
            url=payload.url,
            titulo=payload.titulo,
            ambiente=payload.ambiente,
            correlation_id=correlation_id,
            actor=auth.ator,
        )
    except LifecycleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(result, correlation_id)
