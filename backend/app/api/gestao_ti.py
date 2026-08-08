import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.core.operational_queue import operational_queue
from app.core.security import require_admin
from app.db import get_db
from app.models.gestao_ti import RequisitoServico, ServicoTI
from app.models.requisito import Requisito
from app.schemas.gestao_ti import (
    RequisitoServicoOut,
    RequisitoServicoVincular,
    ServicoTICriar,
    ServicoTIOut,
)
from app.services.auditoria import registrar_evento

logger = logging.getLogger('reqsys.gestao_ti')
router = APIRouter(prefix='/gestao-ti', tags=['Gestão de TI'])


def _correlation_id(valor: str | None) -> str:
    return (valor or '').strip() or 'sem-correlation-id'


@router.get('/servicos')
def listar_servicos(db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    servicos = db.query(ServicoTI).order_by(ServicoTI.codigo).all()
    logger.info(
        'catalogo_servicos_consultado quantidade=%s correlation_id=%s',
        len(servicos),
        _correlation_id(x_correlation_id),
    )
    return ok(
        [ServicoTIOut.model_validate(item).model_dump() for item in servicos],
        x_correlation_id,
        meta={'contract': 'reqsys-gestao-ti-servicos-v1'},
    )


@router.post('/servicos', status_code=status.HTTP_201_CREATED)
def criar_servico(
    payload: ServicoTICriar,
    db: Session = Depends(get_db),
    usuario: dict = Depends(require_admin),
    x_correlation_id: str | None = Header(default=None),
):
    codigo = payload.codigo.strip().upper()
    if db.query(ServicoTI).filter(ServicoTI.codigo == codigo).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={'code': 'SERVICO_JA_EXISTE', 'message': 'Código de serviço já cadastrado.'},
        )

    servico = ServicoTI(**payload.model_dump(), codigo=codigo)
    db.add(servico)
    db.commit()
    db.refresh(servico)
    correlation_id = _correlation_id(x_correlation_id)
    registrar_evento(
        db,
        correlation_id,
        usuario.get('sub', 'admin'),
        'SERVICO_TI_CRIADO',
        'servico_ti',
        servico.servico_id,
        '{"campos":"minimizados"}',
    )
    logger.info(
        'servico_ti_criado servico_id=%s codigo=%s correlation_id=%s',
        servico.servico_id,
        servico.codigo,
        correlation_id,
    )
    return ok(ServicoTIOut.model_validate(servico).model_dump(), x_correlation_id)


@router.post('/vinculos', status_code=status.HTTP_201_CREATED)
def vincular_requisito(
    payload: RequisitoServicoVincular,
    db: Session = Depends(get_db),
    usuario: dict = Depends(require_admin),
    x_correlation_id: str | None = Header(default=None),
):
    requisito = db.query(Requisito).filter(Requisito.id == payload.requisito_id).first()
    if requisito is None:
        raise HTTPException(status_code=404, detail={'code': 'REQUISITO_NAO_ENCONTRADO'})
    servico = db.query(ServicoTI).filter(ServicoTI.servico_id == payload.servico_id, ServicoTI.ativo.is_(True)).first()
    if servico is None:
        raise HTTPException(status_code=404, detail={'code': 'SERVICO_NAO_ENCONTRADO'})

    existente = db.query(RequisitoServico).filter(RequisitoServico.requisito_id == requisito.id).first()
    if existente is not None:
        if existente.servico_id == servico.servico_id:
            return ok({'vinculo_id': existente.vinculo_id, 'idempotente': True}, x_correlation_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={'code': 'REQUISITO_JA_VINCULADO', 'servico_id_atual': existente.servico_id},
        )

    correlation_id = _correlation_id(x_correlation_id)
    vinculo = RequisitoServico(
        requisito_id=requisito.id,
        servico_id=servico.servico_id,
        criado_por=usuario.get('sub', 'admin'),
        correlation_id=correlation_id,
    )
    db.add(vinculo)
    db.commit()
    db.refresh(vinculo)
    registrar_evento(
        db,
        correlation_id,
        usuario.get('sub', 'admin'),
        'REQUISITO_VINCULADO_SERVICO',
        'requisito',
        requisito.id,
        '{"campos":"minimizados"}',
    )
    return ok({'vinculo_id': vinculo.vinculo_id, 'idempotente': False}, x_correlation_id)


@router.get('/consulta/requisitos-servicos')
def consultar_requisitos_servicos(
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    linhas = (
        db.query(RequisitoServico, Requisito, ServicoTI)
        .join(Requisito, Requisito.id == RequisitoServico.requisito_id)
        .join(ServicoTI, ServicoTI.servico_id == RequisitoServico.servico_id)
        .order_by(Requisito.id.desc())
        .all()
    )
    dados = [
        RequisitoServicoOut(
            requisito_id=requisito.id,
            requisito_codigo=requisito.codigo,
            requisito_titulo=requisito.titulo,
            servico_id=servico.servico_id,
            servico_codigo=servico.codigo,
            servico_nome=servico.nome,
            correlation_id=vinculo.correlation_id,
        ).model_dump()
        for vinculo, requisito, servico in linhas
    ]
    return ok(
        dados,
        x_correlation_id,
        meta={'contract': 'reqsys-gestao-ti-consulta-power-bi-v1', 'read_only': True},
    )


@router.get('/painel')
async def painel_gestao_ti(db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    total_requisitos = db.query(func.count(Requisito.id)).scalar() or 0
    total_vinculados = db.query(func.count(RequisitoServico.vinculo_id)).scalar() or 0
    total_servicos = db.query(func.count(ServicoTI.servico_id)).filter(ServicoTI.ativo.is_(True)).scalar() or 0
    fila = await operational_queue.snapshot()
    cobertura = round((total_vinculados / total_requisitos) * 100, 2) if total_requisitos else 100.0

    payload = {
        'schema_version': '1.0.0',
        'status': 'saudavel' if fila.get('connected', True) and cobertura >= 80 else 'atencao',
        'catalogo': {
            'servicos_ativos': total_servicos,
            'requisitos_total': total_requisitos,
            'requisitos_vinculados': total_vinculados,
            'requisitos_sem_servico': max(0, total_requisitos - total_vinculados),
            'cobertura_percentual': cobertura,
        },
        'fila': {
            'provedor': fila.get('provider'),
            'conectada': fila.get('connected'),
            'duravel': fila.get('durable'),
            'aguardando': fila.get('queued_items', 0),
            'processando': fila.get('processing_items', 0),
            'erros_definitivos': fila.get('dlq_items', 0),
            'idade_mais_antiga_segundos': fila.get('oldest_message_age_seconds'),
        },
        'links': {
            'workspace_requisitos': '/api/requisitos/workspace',
            'catalogo_servicos': '/api/requisitos/gestao-ti/servicos',
            'consulta_power_bi': '/api/requisitos/gestao-ti/consulta/requisitos-servicos',
            'saude_fila': '/api/operational-autonomy/health',
        },
    }
    logger.info(
        'painel_gestao_ti_consultado servicos=%s cobertura=%s correlation_id=%s',
        total_servicos,
        cobertura,
        _correlation_id(x_correlation_id),
    )
    return ok(payload, x_correlation_id, meta={'contract': 'reqsys-gestao-ti-painel-v1'})
