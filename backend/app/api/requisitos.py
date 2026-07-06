import logging
from collections import Counter
from time import time_ns

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
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

_STATUS_PENDENTES = {'recebido', 'pendente', 'em_analise', 'analise', 'bloqueado', 'devolvido'}
_STATUS_APROVACAO = {'aguardando_aprovacao', 'aguardando-aprovacao', 'aprovacao', 'em_aprovacao'}
_STATUS_PRONTOS = {'aprovado', 'pronto', 'concluido', 'concluído', 'done', 'aceito'}


def _gerar_codigo_requisito() -> str:
    return f"REQ-{str(time_ns())[-9:]}"


def _normalizar_texto(valor: str | None) -> str:
    return (valor or '').strip()


def _normalizar_chave(valor: str | None) -> str:
    return _normalizar_texto(valor).lower().replace(' ', '_')


def _percentual(parte: int, total: int) -> int:
    if total <= 0:
        return 0
    return round((parte / total) * 100)


def _calcular_score_prontidao(requisito: Requisito) -> int:
    campos_minimos = [
        requisito.titulo,
        requisito.descricao,
        requisito.area,
        requisito.sistema,
        requisito.solicitante,
        requisito.urgencia,
    ]
    pontos = sum(12 for valor in campos_minimos if _normalizar_texto(valor))
    descricao = _normalizar_texto(requisito.descricao)
    status_normalizado = _normalizar_chave(requisito.status)

    if len(descricao) >= 80:
        pontos += 12
    elif len(descricao) >= 40:
        pontos += 6

    if any(termo in descricao.lower() for termo in ('criterio', 'critério', 'bdd', 'dado que', 'quando', 'entao', 'então')):
        pontos += 10

    if status_normalizado in _STATUS_PRONTOS:
        pontos += 6

    return max(0, min(100, pontos))


def _classificar_requisito(requisito: Requisito) -> dict:
    score = _calcular_score_prontidao(requisito)
    status_normalizado = _normalizar_chave(requisito.status)
    descricao = _normalizar_texto(requisito.descricao)

    return {
        'id': requisito.id,
        'codigo': requisito.codigo,
        'titulo': requisito.titulo,
        'status': requisito.status,
        'area': requisito.area,
        'sistema': requisito.sistema,
        'solicitante': requisito.solicitante,
        'score_prontidao': score,
        'sem_criterio_aceite': not any(termo in descricao.lower() for termo in ('criterio', 'critério', 'bdd', 'dado que', 'quando', 'entao', 'então')),
        'baixa_qualidade': score < 70,
        'sem_rastreabilidade': not all(_normalizar_texto(valor) for valor in (requisito.codigo, requisito.solicitante, requisito.area, requisito.sistema)),
        'aguardando_aprovacao': status_normalizado in _STATUS_APROVACAO,
        'pendente': status_normalizado in _STATUS_PENDENTES or score < 70,
    }


def _filtrar_requisitos(
    requisitos: list[Requisito],
    status_filtro: str | None,
    area: str | None,
    responsavel: str | None,
) -> list[Requisito]:
    status_filtro_normalizado = _normalizar_chave(status_filtro)
    area_normalizada = _normalizar_chave(area)
    responsavel_normalizado = _normalizar_chave(responsavel)

    resultado = requisitos
    if status_filtro_normalizado:
        resultado = [requisito for requisito in resultado if _normalizar_chave(requisito.status) == status_filtro_normalizado]
    if area_normalizada:
        resultado = [requisito for requisito in resultado if _normalizar_chave(requisito.area) == area_normalizada]
    if responsavel_normalizado:
        resultado = [requisito for requisito in resultado if _normalizar_chave(requisito.solicitante) == responsavel_normalizado]
    return resultado


def _montar_workspace_operacional(requisitos: list[Requisito]) -> dict:
    classificados = [_classificar_requisito(requisito) for requisito in requisitos]
    total = len(classificados)
    scores = [item['score_prontidao'] for item in classificados]
    score_medio = round(sum(scores) / total) if total else 0

    sem_aceite = sum(1 for item in classificados if item['sem_criterio_aceite'])
    baixa_qualidade = sum(1 for item in classificados if item['baixa_qualidade'])
    sem_rastro = sum(1 for item in classificados if item['sem_rastreabilidade'])
    aguardando_aprovacao = sum(1 for item in classificados if item['aguardando_aprovacao'])
    pendentes = sum(1 for item in classificados if item['pendente'])
    prontos = sum(1 for item in classificados if item['score_prontidao'] >= 80)
    status_counter = Counter(_normalizar_chave(item['status']) or 'sem_status' for item in classificados)

    return {
        'schema_version': '1.0.0',
        'source': 'api.requisitos.workspace',
        'metrics': [
            {
                'id': 'prontas',
                'value': f'{_percentual(prontos, total)}%',
                'label': 'prontidão funcional',
                'description': 'Percentual de requisitos com score de prontidão igual ou superior a 80.',
                'icon': 'mdi-account-check-outline',
                'color': 'green' if score_medio >= 80 else 'amber',
                'status': 'verde' if score_medio >= 80 else 'atenção',
            },
            {
                'id': 'dados',
                'value': f'{score_medio}%',
                'label': 'qualidade dos dados',
                'description': 'Score médio calculado por completude, descrição, aceite e status.',
                'icon': 'mdi-database-check-outline',
                'color': 'green' if score_medio >= 80 else 'amber',
                'status': 'real',
            },
            {
                'id': 'fluxo',
                'value': '6 etapas',
                'label': 'workflow de requisito',
                'description': 'Entrada, refinamento, aceite, aprovação, rastreabilidade e exportação.',
                'icon': 'mdi-source-branch-sync',
                'color': 'blue',
                'status': 'guiado',
            },
            {
                'id': 'pendencias',
                'value': str(pendentes),
                'label': 'pendências operacionais',
                'description': 'Itens pendentes por status ou baixa prontidão objetiva.',
                'icon': 'mdi-clipboard-alert-outline',
                'color': 'amber' if pendentes else 'green',
                'status': 'real',
            },
        ],
        'action_queue': [
            {
                'id': 'sem-aceite',
                'title': 'Histórias sem critério de aceite',
                'description': 'Requisitos sem evidência textual de aceite, BDD ou cenário verificável.',
                'count': str(sem_aceite),
                'icon': 'mdi-format-list-checks',
                'color': 'red' if sem_aceite else 'green',
            },
            {
                'id': 'baixa-qualidade',
                'title': 'Requisitos com baixa qualidade',
                'description': 'Itens com score de prontidão inferior a 70.',
                'count': str(baixa_qualidade),
                'icon': 'mdi-auto-fix',
                'color': 'amber' if baixa_qualidade else 'green',
            },
            {
                'id': 'sem-rastro',
                'title': 'Itens sem rastreabilidade',
                'description': 'Demandas sem código, solicitante, área ou sistema informados.',
                'count': str(sem_rastro),
                'icon': 'mdi-link-variant-off',
                'color': 'amber' if sem_rastro else 'green',
            },
            {
                'id': 'aprovacao',
                'title': 'Aguardando aprovação',
                'description': 'Itens cujo status indica etapa de aceite/aprovação.',
                'count': str(aguardando_aprovacao),
                'icon': 'mdi-account-clock-outline',
                'color': 'blue' if aguardando_aprovacao else 'green',
            },
        ],
        'summary': {
            'total_requisitos': total,
            'score_medio_prontidao': score_medio,
            'pendencias_operacionais': pendentes,
            'status': dict(status_counter),
        },
        'top_items': sorted(classificados, key=lambda item: item['score_prontidao'])[:5],
        'workflow': ['entrada', 'refinamento', 'aceite', 'aprovacao', 'rastreabilidade', 'exportacao'],
    }


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


@api_router.get('/workspace')
def obter_workspace_operacional(
    status_filtro: str | None = Query(default=None, alias='status'),
    area: str | None = Query(default=None),
    responsavel: str | None = Query(default=None),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    requisitos = db.query(Requisito).order_by(Requisito.id.desc()).all()
    requisitos_filtrados = _filtrar_requisitos(requisitos, status_filtro, area, responsavel)
    payload = _montar_workspace_operacional(requisitos_filtrados)
    payload['filters'] = {
        'status': status_filtro,
        'area': area,
        'responsavel': responsavel,
    }
    logger.info(
        'workspace_operacional_consultado total=%s filtrados=%s correlation_id=%s',
        len(requisitos),
        len(requisitos_filtrados),
        x_correlation_id or 'sem-correlation-id',
    )
    return ok(
        payload,
        x_correlation_id,
        meta={'contract': 'reqsys-workspace-operacional-v1'},
    )


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
