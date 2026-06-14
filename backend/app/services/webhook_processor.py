import json

from sqlalchemy.orm import Session

from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit
from app.services.auditoria import registrar_evento


def _resolver_requisito_id(db: Session, codigo: str) -> int | None:
    req = db.query(Requisito).filter(Requisito.codigo == codigo).first()
    return req.id if req else None


def salvar_vinculos(db: Session, vinculos: list[dict]) -> list[int]:
    """
    Persiste cada vínculo Git, registra evento de auditoria e,
    quando PR/MR é mergeado, avança o status do requisito para 'implementado'.
    """
    ids: list[int] = []

    for v in vinculos:
        req_id = _resolver_requisito_id(db, v['requisito_codigo'])

        vinculo = VinculoGit(
            requisito_codigo=v['requisito_codigo'],
            requisito_id=req_id,
            tipo=v['tipo'],
            provedor=v['provedor'],
            repo=v['repo'],
            referencia=v['referencia'],
            url=v.get('url'),
            titulo=v.get('titulo'),
            autor=v.get('autor'),
            ambiente=v.get('ambiente'),
        )
        db.add(vinculo)
        db.flush()
        ids.append(vinculo.id)

        if req_id:
            registrar_evento(
                db,
                'webhook',
                v.get('autor') or 'git',
                f"GIT_{v['tipo'].upper()}_DETECTADO",
                'requisito',
                req_id,
                json.dumps({
                    'provedor': v['provedor'],
                    'repo': v['repo'],
                    'referencia': v['referencia'],
                    'url': v.get('url'),
                }),
            )

        # PR/MR mergeado → marca requisito como implementado se ainda não estava encerrado
        if v.get('pr_merged') or v.get('mr_merged'):
            if req_id:
                req = db.query(Requisito).filter(Requisito.id == req_id).first()
                if req and req.status not in ('encerrado', 'implementado'):
                    status_anterior = req.status
                    req.status = 'implementado'
                    registrar_evento(
                        db,
                        'webhook',
                        v.get('autor') or 'git',
                        'STATUS_ATUALIZADO_VIA_GIT',
                        'requisito',
                        req_id,
                        json.dumps({
                            'de': status_anterior,
                            'para': 'implementado',
                            'trigger': f"{v['provedor']}_{v['tipo']}",
                            'referencia': v['referencia'],
                        }),
                    )

    db.commit()
    return ids
