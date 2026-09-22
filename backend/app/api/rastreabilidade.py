from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.models.agile_runtime import AgileWorkItem
from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit

router = APIRouter(prefix='/v1/rastreabilidade', tags=['Rastreabilidade Git'])


class VinculoManualIn(BaseModel):
    tipo: str = 'commit'        # commit | branch | pr | merge_request | issue | tag
    provedor: str = 'github'    # github | gitlab
    repo: str
    referencia: str             # SHA, número do PR, nome da branch…
    url: str | None = None
    titulo: str | None = None
    autor: str | None = None
    ambiente: str | None = None  # dev | staging | prod


def _serializar(v: VinculoGit) -> dict:
    return {
        'id': v.id,
        'requisito_codigo': v.requisito_codigo,
        'requisito_id': v.requisito_id,
        'tipo': v.tipo,
        'provedor': v.provedor,
        'repo': v.repo,
        'referencia': v.referencia,
        'url': v.url,
        'titulo': v.titulo,
        'autor': v.autor,
        'ambiente': v.ambiente,
        'criado_em': v.criado_em.isoformat() if hasattr(v.criado_em, 'isoformat') else str(v.criado_em),
    }


@router.get('/requisitos/{requisito_id}')
def vinculos_por_requisito(requisito_id: int, db: Session = Depends(get_db)):
    """Lista todos os vínculos Git de um requisito pelo seu ID."""
    vinculos = (
        db.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito_id)
        .order_by(desc(VinculoGit.criado_em))
        .all()
    )
    return ok({'requisito_id': requisito_id, 'total': len(vinculos), 'vinculos': [_serializar(v) for v in vinculos]})


@router.get('/buscar')
def buscar_por_codigo(
    codigo: str = Query(description='Código do requisito, ex.: REQ-123456789'),
    db: Session = Depends(get_db),
):
    """Busca vínculos Git pelo código do requisito (funciona mesmo se o requisito não existir no banco)."""
    vinculos = (
        db.query(VinculoGit)
        .filter(VinculoGit.requisito_codigo == codigo.upper())
        .order_by(desc(VinculoGit.criado_em))
        .all()
    )
    return ok({'codigo': codigo.upper(), 'total': len(vinculos), 'vinculos': [_serializar(v) for v in vinculos]})


@router.get('/recentes')
def vinculos_recentes(
    limit: int = Query(default=50, ge=1, le=200),
    provedor: str | None = Query(default=None, description='github | gitlab'),
    tipo: str | None = Query(default=None, description='commit | pr | merge_request | branch'),
    db: Session = Depends(get_db),
):
    """Lista os vínculos mais recentes com filtros opcionais."""
    q = db.query(VinculoGit).order_by(desc(VinculoGit.criado_em))
    if provedor:
        q = q.filter(VinculoGit.provedor == provedor)
    if tipo:
        q = q.filter(VinculoGit.tipo == tipo)
    vinculos = q.limit(limit).all()
    return ok({'total': len(vinculos), 'vinculos': [_serializar(v) for v in vinculos]})


@router.get('/matriz')
def matriz_rastreabilidade(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Matriz consolidada requisito → work item → entrega Git para a UI."""
    vinculos = (
        db.query(VinculoGit)
        .order_by(desc(VinculoGit.criado_em))
        .limit(limit)
        .all()
    )

    requisito_ids = {v.requisito_id for v in vinculos if v.requisito_id}
    work_items_por_requisito: dict[int, list] = {}
    if requisito_ids:
        itens = db.query(AgileWorkItem).filter(AgileWorkItem.requisito_id.in_(requisito_ids)).all()
        for item in itens:
            work_items_por_requisito.setdefault(item.requisito_id, []).append(item)

    linhas = []
    for vinculo in vinculos:
        work_item = None
        if vinculo.requisito_id:
            candidatos = work_items_por_requisito.get(vinculo.requisito_id, [])
            work_item = candidatos[0] if candidatos else None

        entrega = vinculo.referencia
        redmine = '—'
        if vinculo.tipo == 'pr':
            entrega = f"PR #{vinculo.referencia}"
        elif vinculo.tipo == 'merge_request':
            entrega = f"MR #{vinculo.referencia}"
        elif vinculo.provedor == 'redmine' and vinculo.tipo == 'issue':
            entrega = f"Redmine #{vinculo.referencia}"
            redmine = f"#{vinculo.referencia}"

        linhas.append(
            {
                'requisito': vinculo.requisito_codigo,
                'historia': work_item.codigo if work_item else '—',
                'redmine': redmine,
                'planner': '—',
                'entrega': entrega,
                'entrega_tipo': vinculo.tipo,
                'entrega_url': vinculo.url,
                'ambiente': vinculo.ambiente or '—',
                'status': 'rastreado' if vinculo.url else 'parcial',
                'work_item_id': work_item.id if work_item else None,
                'change_url': work_item.change_url if work_item else None,
                'repositorio': vinculo.repo,
                'criado_em': vinculo.criado_em.isoformat() if hasattr(vinculo.criado_em, 'isoformat') else str(vinculo.criado_em),
            }
        )

    return ok({'total': len(linhas), 'linhas': linhas})


@router.post('/requisitos/{requisito_id}/vinculos')
def adicionar_vinculo_manual(
    requisito_id: int,
    payload: VinculoManualIn,
    db: Session = Depends(get_db),
):
    """Registra vínculo Git manualmente (sem webhook), útil para repositórios sem acesso externo."""
    req = db.query(Requisito).filter(Requisito.id == requisito_id).first()
    if not req:
        raise HTTPException(status_code=404, detail='Requisito não encontrado.')

    vinculo = VinculoGit(
        requisito_codigo=req.codigo,
        requisito_id=requisito_id,
        tipo=payload.tipo,
        provedor=payload.provedor,
        repo=payload.repo,
        referencia=payload.referencia,
        url=payload.url,
        titulo=payload.titulo,
        autor=payload.autor,
        ambiente=payload.ambiente,
    )
    db.add(vinculo)
    db.commit()
    db.refresh(vinculo)
    return ok(_serializar(vinculo))
