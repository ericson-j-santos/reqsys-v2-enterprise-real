from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.models.auditoria import AuditoriaEvento

router = APIRouter(prefix='/v1/auditoria', tags=['Auditoria'])

@router.get('/eventos')
def listar_eventos(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    entidade: str | None = Query(default=None),
    acao: str | None = Query(default=None),
    db: Session = Depends(get_db)
):
    """
    Lista eventos de auditoria com filtros opcionais.

    - limit: quantidade de registros (1-500)
    - offset: deslocamento para paginacao
    - entidade: filtrar por entidade (ex.: 'infra', 'requisito')
    - acao: filtrar por acao (ex.: 'CONFIG_DOMINIO_ATUALIZADA', 'REQUISITO_CRIADO')
    """
    query = db.query(AuditoriaEvento).order_by(desc(AuditoriaEvento.criado_em))

    if entidade:
        query = query.filter(AuditoriaEvento.entidade == entidade)
    if acao:
        query = query.filter(AuditoriaEvento.acao == acao)

    total = query.count()
    eventos = query.limit(limit).offset(offset).all()

    resultado = [
        {
            'id': e.id,
            'correlation_id': e.correlation_id,
            'usuario': e.usuario,
            'acao': e.acao,
            'entidade': e.entidade,
            'entidade_id': e.entidade_id,
            'payload_minimo': e.payload_minimo,
            'criado_em': e.criado_em.isoformat() if hasattr(e.criado_em, 'isoformat') else str(e.criado_em)
        }
        for e in eventos
    ]

    return ok({
        'dados': resultado,
        'paginacao': {'total': total, 'limit': limit, 'offset': offset}
    })

@router.get('/eventos/config-infra')
def listar_eventos_config_infra(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Lista especificamente mudancas de configuracao de infraestrutura.
    Util para rastrear historico de dominios, CORS, variaveis de ambiente, etc.
    """
    eventos = db.query(AuditoriaEvento).filter(
        AuditoriaEvento.entidade == 'infra',
        AuditoriaEvento.acao.in_(['CONFIG_DOMINIO_ATUALIZADA', 'CONFIG_CORS_ATUALIZADA', 'ENV_ALTERADA'])
    ).order_by(desc(AuditoriaEvento.criado_em)).limit(limit).all()

    resultado = [
        {
            'id': e.id,
            'correlation_id': e.correlation_id,
            'usuario': e.usuario,
            'acao': e.acao,
            'entidade_id': e.entidade_id,
            'payload_minimo': e.payload_minimo,
            'criado_em': e.criado_em.isoformat() if hasattr(e.criado_em, 'isoformat') else str(e.criado_em)
        }
        for e in eventos
    ]

    return ok({'config_historico': resultado, 'total': len(resultado)})
