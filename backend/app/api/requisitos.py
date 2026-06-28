import logging
from time import time_ns

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.models.requisito import Requisito
from app.schemas.requisito import (
    RequisitoCriar,
    RequisitoOut,
    RequisitoPowerAutomateCriar,
    RequisitoPowerAutomateOut,
)
from app.services.auditoria import registrar_evento

logger = logging.getLogger('reqsys.requisitos')

router = APIRouter(prefix='/v1/requisitos', tags=['Requisitos'])
api_router = APIRouter(prefix='/api/requisitos', tags=['Requisitos Power Automate'])


def _gerar_codigo_requisito() -> str:
    return f"REQ-{str(time_ns())[-9:]}"


def _serializar_v1(requisito: Requisito) -> dict:
    return RequisitoOut.model_validate(requisito).model_dump()


def _serializar_power_automate(requisito: Requisito) -> dict:
    return RequisitoPowerAutomateOut(
        id=requisito.id,
        codigo=requisito.codigo,
        titulo=requisito.titulo,
        descricao=requisito.descricao,
        prioridade=requisito.urgencia,
        status=requisito.status,
        area=requisito.area,
        sistema=requisito.sistema,
        solicitante=requisito.solicitante,
        impacto_regulatorio=requisito.impacto_regulatorio,
    ).model_dump()


def _buscar_requisito_por_identificador(db: Session, identificador: str) -> Requisito:
    requisito = db.query(Requisito).filter(
        or_(
            Requisito.codigo == identificador,
            Requisito.id == int(identificador) if identificador.isdigit() else False,
        )
    ).first()
    if not requisito:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': 'REQUISITO_NAO_ENCONTRADO',
                'message': 'Requisito nao encontrado pelo codigo ou id informado.',
                'identificador': identificador,
            },
        )
    return requisito


@router.get('')
def listar(db: Session = Depends(get_db)):
    requisitos = db.query(Requisito).order_by(Requisito.id.desc()).all()
    return ok([_serializar_v1(requisito) for requisito in requisitos])


@router.get('/{identificador}')
def obter(identificador: str, db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    requisito = _buscar_requisito_por_identificador(db, identificador)
    logger.info('requisito_consultado codigo=%s correlation_id=%s', requisito.codigo, x_correlation_id or 'sem-correlation-id')
    return ok(_serializar_v1(requisito), x_correlation_id)


@router.post('')
def criar(payload: RequisitoCriar, db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    codigo = _gerar_codigo_requisito()
    req = Requisito(codigo=codigo, **payload.model_dump())
    db.add(req)
    db.commit()
    db.refresh(req)
    registrar_evento(db, x_correlation_id or 'sem-correlation-id', payload.solicitante, 'REQUISITO_CRIADO', 'requisito', req.id, '{"campos":"minimizados"}')
    logger.info('requisito_criado codigo=%s origem=v1 correlation_id=%s', req.codigo, x_correlation_id or 'sem-correlation-id')
    return ok(_serializar_v1(req), x_correlation_id)


@api_router.get('')
def listar_power_automate(db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    requisitos = db.query(Requisito).order_by(Requisito.id.desc()).all()
    return ok(
        {
            'schema_version': '1.0.0',
            'items': [_serializar_power_automate(requisito) for requisito in requisitos],
            'total': len(requisitos),
        },
        x_correlation_id,
        meta={'contract': 'reqsys-power-automate-requisitos'},
    )


@api_router.get('/{identificador}')
def obter_power_automate(identificador: str, db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    requisito = _buscar_requisito_por_identificador(db, identificador)
    logger.info('requisito_consultado codigo=%s origem=power_automate correlation_id=%s', requisito.codigo, x_correlation_id or 'sem-correlation-id')
    return ok(
        _serializar_power_automate(requisito),
        x_correlation_id,
        meta={'contract': 'reqsys-power-automate-requisitos'},
    )


@api_router.post('', status_code=status.HTTP_201_CREATED)
def receber_power_automate(payload: RequisitoPowerAutomateCriar, db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    codigo = _gerar_codigo_requisito()
    req = Requisito(
        codigo=codigo,
        titulo=payload.titulo,
        descricao=payload.descricao,
        urgencia=payload.prioridade,
        area=payload.area,
        sistema=payload.sistema,
        solicitante=payload.solicitante,
        impacto_regulatorio=payload.impacto_regulatorio,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    registrar_evento(
        db,
        x_correlation_id or 'sem-correlation-id',
        payload.solicitante,
        'REQUISITO_RECEBIDO_POWER_AUTOMATE',
        'requisito',
        req.id,
        '{"schema_version":"1.0.0","campos":"minimizados"}',
    )
    logger.info('requisito_criado codigo=%s origem=power_automate correlation_id=%s', req.codigo, x_correlation_id or 'sem-correlation-id')
    return ok(
        _serializar_power_automate(req),
        x_correlation_id,
        meta={'contract': 'reqsys-power-automate-requisitos'},
    )
