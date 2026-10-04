import json

from sqlalchemy.orm import Session

from app.models.agile_runtime import AgileEvidence, AgileWorkItem
from app.services.auditoria import registrar_evento

_AMBIENTE_AGILE: dict[str | None, str] = {
    'dev': 'dev',
    'staging': 'homolog',
    'prod': 'prod',
    None: 'none',
}


def _mapear_ambiente_deploy(ambiente: str | None) -> str:
    return _AMBIENTE_AGILE.get(ambiente, 'none')


def sincronizar_work_items_git(db: Session, eventos: list[dict]) -> list[int]:
    """Atualiza AgileWorkItem a partir de eventos Git com codigo AGI-*."""
    ids_atualizados: list[int] = []

    for evento in eventos:
        codigo = (evento.get('work_item_codigo') or '').upper()
        if not codigo:
            continue

        item = db.query(AgileWorkItem).filter(AgileWorkItem.codigo == codigo).first()
        if not item:
            continue

        if evento.get('repo'):
            item.repositorio = evento['repo']
        if evento.get('branch'):
            item.branch = evento['branch']

        if evento.get('tipo') in {'pr', 'merge_request'}:
            provedor = evento.get('provedor', 'github')
            item.change_provider = 'gitlab' if provedor == 'gitlab' else 'github'
            item.change_id = evento.get('referencia')
            item.change_url = evento.get('url')

        ambiente = _mapear_ambiente_deploy(evento.get('ambiente'))
        if ambiente != 'none':
            item.ambiente_deploy = ambiente

        if evento.get('pr_merged') or evento.get('mr_merged'):
            if item.status in {'em_execucao', 'em_revisao'}:
                item.status = 'em_ci'
            item.ci_status = 'pending'

        db.add(item)
        db.flush()
        ids_atualizados.append(item.id)

        evidencia = AgileEvidence(
            work_item_id=item.id,
            tipo='pr' if evento.get('tipo') in {'pr', 'merge_request'} else 'auditoria',
            titulo=f"Git {evento.get('tipo', 'evento')} detectado via webhook",
            url=evento.get('url'),
            status='sincronizado',
            observacao=json.dumps(
                {
                    'provedor': evento.get('provedor'),
                    'repo': evento.get('repo'),
                    'referencia': evento.get('referencia'),
                    'branch': evento.get('branch'),
                },
                ensure_ascii=False,
            )[:500],
            correlation_id='webhook',
            criado_por=evento.get('autor') or 'git-webhook',
        )
        db.add(evidencia)

        registrar_evento(
            db,
            'webhook',
            evento.get('autor') or 'git',
            'AGILE_WORK_ITEM_SINCRONIZADO_VIA_GIT',
            'agile_work_item',
            item.id,
            json.dumps(
                {
                    'work_item_codigo': codigo,
                    'tipo': evento.get('tipo'),
                    'referencia': evento.get('referencia'),
                    'url': evento.get('url'),
                },
                ensure_ascii=False,
            ),
        )

    if ids_atualizados:
        db.commit()
    return ids_atualizados
