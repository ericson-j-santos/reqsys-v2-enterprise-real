"""Orquestrador do caminho único requisito -> execução -> deploy.

Incremento 1:
ReqSys -> Redmine -> GitHub -> evidências de PR/commit/deploy -> ReqSys.

A persistência usa ``VinculoGit`` para evitar nova migração de banco neste
incremento. Cada integração externa possui um dono claro; o ReqSys consolida a
rastreabilidade e não replica indiscriminadamente todos os campos.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit
from app.services.auditoria import registrar_evento
from app.services.github_lifecycle import find_or_create_requirement_issue
from app.services.github_redmine import IntegracaoError, publish_requisito_to_redmine

ALLOWED_EVIDENCE_TYPES = {'issue', 'branch', 'pr', 'commit', 'deploy'}
ALLOWED_ENVIRONMENTS = {'dev', 'staging', 'prod'}
TERMINAL_REQUIREMENT_STATUSES = {'concluido', 'cancelado'}


class LifecycleError(RuntimeError):
    pass


def _find_link(
    db: Session,
    *,
    requisito_id: int,
    provedor: str,
    tipo: str,
    referencia: str | None = None,
    ambiente: str | None = None,
) -> VinculoGit | None:
    query = (
        db.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito_id)
        .filter(VinculoGit.provedor == provedor)
        .filter(VinculoGit.tipo == tipo)
    )
    if referencia is not None:
        query = query.filter(VinculoGit.referencia == referencia)
    if ambiente is not None:
        query = query.filter(VinculoGit.ambiente == ambiente)
    return query.order_by(VinculoGit.id.desc()).first()


def _upsert_link(
    db: Session,
    *,
    requisito: Requisito,
    provedor: str,
    tipo: str,
    repo: str,
    referencia: str,
    url: str | None = None,
    titulo: str | None = None,
    autor: str | None = None,
    ambiente: str | None = None,
) -> tuple[VinculoGit, bool]:
    existente = _find_link(
        db,
        requisito_id=requisito.id,
        provedor=provedor,
        tipo=tipo,
        referencia=referencia,
        ambiente=ambiente,
    )
    if existente:
        if url:
            existente.url = url
        if titulo:
            existente.titulo = titulo
        if autor:
            existente.autor = autor
        if ambiente:
            existente.ambiente = ambiente
        db.add(existente)
        return existente, False

    link = VinculoGit(
        requisito_codigo=requisito.codigo,
        requisito_id=requisito.id,
        tipo=tipo,
        provedor=provedor,
        repo=repo,
        referencia=referencia,
        url=url,
        titulo=titulo,
        autor=autor,
        ambiente=ambiente,
    )
    db.add(link)
    db.flush()
    return link, True


def _link_payload(link: VinculoGit | None) -> dict[str, Any] | None:
    if link is None:
        return None
    return {
        'id': link.id,
        'provedor': link.provedor,
        'tipo': link.tipo,
        'repo': link.repo,
        'referencia': link.referencia,
        'url': link.url,
        'titulo': link.titulo,
        'autor': link.autor,
        'ambiente': link.ambiente,
        'criado_em': link.criado_em.isoformat() if getattr(link.criado_em, 'isoformat', None) else link.criado_em,
    }


def lifecycle_snapshot(db: Session, requisito: Requisito) -> dict[str, Any]:
    links = (
        db.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito.id)
        .order_by(VinculoGit.id.asc())
        .all()
    )

    def first(provedor: str, tipo: str, ambiente: str | None = None) -> VinculoGit | None:
        for link in reversed(links):
            if link.provedor != provedor or link.tipo != tipo:
                continue
            if ambiente is not None and link.ambiente != ambiente:
                continue
            return link
        return None

    redmine = first('redmine', 'issue')
    github_issue = first('github', 'issue')
    github_pr = first('github', 'pr')
    github_commit = first('github', 'commit')
    deploy_dev = first('deployment', 'deploy', 'dev')
    deploy_staging = first('deployment', 'deploy', 'staging')
    deploy_prod = first('deployment', 'deploy', 'prod')

    stages = {
        'requisito': True,
        'redmine': redmine is not None,
        'github_issue': github_issue is not None,
        'pull_request': github_pr is not None,
        'commit': github_commit is not None,
        'deploy_dev': deploy_dev is not None,
        'deploy_staging': deploy_staging is not None,
        'deploy_prod': deploy_prod is not None,
    }
    completed = sum(1 for value in stages.values() if value)
    total = len(stages)

    return {
        'requisito_id': requisito.id,
        'codigo': requisito.codigo,
        'status_requisito': requisito.status,
        'stages': stages,
        'progresso_percentual': round(completed / total * 100, 2),
        'redmine': _link_payload(redmine),
        'github_issue': _link_payload(github_issue),
        'github_pr': _link_payload(github_pr),
        'github_commit': _link_payload(github_commit),
        'deploys': {
            'dev': _link_payload(deploy_dev),
            'staging': _link_payload(deploy_staging),
            'prod': _link_payload(deploy_prod),
        },
        'links': [_link_payload(link) for link in links],
        'ready_for_explicit_completion': deploy_prod is not None,
    }


def start_lifecycle(
    db: Session,
    *,
    requisito: Requisito,
    github_repo: str,
    correlation_id: str,
    actor: str,
    redmine_project_id: int | None = None,
    tracker_id: int | None = None,
    priority_id: int | None = None,
) -> dict[str, Any]:
    if requisito.status in TERMINAL_REQUIREMENT_STATUSES:
        raise LifecycleError(
            f"Requisito {requisito.codigo} está em estado terminal '{requisito.status}' e não pode iniciar novo ciclo."
        )

    warnings: list[str] = []
    redmine_link = _find_link(db, requisito_id=requisito.id, provedor='redmine', tipo='issue')

    if redmine_link is None:
        redmine_result = publish_requisito_to_redmine(
            requisito=requisito,
            project_id=redmine_project_id,
            tracker_id=tracker_id,
            priority_id=priority_id,
        )
        warnings.extend(redmine_result.get('warnings') or [])
        issue_id = redmine_result.get('issue_principal_id')
        if not issue_id:
            raise LifecycleError(
                'Não foi possível criar/reutilizar a Issue Redmine. ' + ('; '.join(warnings) if warnings else 'Sem detalhe adicional.')
            )
        redmine_link, _ = _upsert_link(
            db,
            requisito=requisito,
            provedor='redmine',
            tipo='issue',
            repo='redmine',
            referencia=str(issue_id),
            url=redmine_result.get('redmine_url'),
            titulo=f'Redmine issue #{issue_id}',
            autor=actor,
        )
        if requisito.status not in TERMINAL_REQUIREMENT_STATUSES:
            requisito.status = 'backlog'
        db.add(requisito)
        db.commit()
        db.refresh(redmine_link)

    github_link = _find_link(db, requisito_id=requisito.id, provedor='github', tipo='issue')
    if github_link is None:
        github_result = find_or_create_requirement_issue(
            repo=github_repo,
            requirement_code=requisito.codigo,
            title=requisito.titulo,
            description=requisito.descricao,
            redmine_url=redmine_link.url if redmine_link else None,
            correlation_id=correlation_id,
        )
        issue_number = github_result.get('issue_number')
        if not issue_number:
            raise LifecycleError('GitHub não retornou o número da Issue criada/localizada.')
        github_link, _ = _upsert_link(
            db,
            requisito=requisito,
            provedor='github',
            tipo='issue',
            repo=github_repo,
            referencia=str(issue_number),
            url=github_result.get('github_url'),
            titulo=github_result.get('title'),
            autor=actor,
        )
        db.commit()
        db.refresh(github_link)

    registrar_evento(
        db,
        correlation_id,
        actor,
        'LIFECYCLE_INICIADO',
        'requisito',
        requisito.id,
        json.dumps(
            {
                'codigo': requisito.codigo,
                'github_repo': github_repo,
                'redmine_issue': redmine_link.referencia if redmine_link else None,
                'github_issue': github_link.referencia if github_link else None,
            },
            ensure_ascii=False,
        ),
    )

    snapshot = lifecycle_snapshot(db, requisito)
    snapshot['warnings'] = warnings
    return snapshot


def register_lifecycle_evidence(
    db: Session,
    *,
    requisito: Requisito,
    provedor: str,
    tipo: str,
    repo: str,
    referencia: str,
    correlation_id: str,
    actor: str,
    url: str | None = None,
    titulo: str | None = None,
    ambiente: str | None = None,
) -> dict[str, Any]:
    provedor = (provedor or '').strip().lower()
    tipo = (tipo or '').strip().lower()
    ambiente = (ambiente or '').strip().lower() or None
    referencia = (referencia or '').strip()

    if tipo not in ALLOWED_EVIDENCE_TYPES:
        raise LifecycleError(f"Tipo de evidência inválido: '{tipo}'.")
    if not referencia:
        raise LifecycleError('referencia é obrigatória.')
    if tipo == 'deploy':
        provedor = 'deployment'
        if ambiente not in ALLOWED_ENVIRONMENTS:
            raise LifecycleError('Deploy exige ambiente dev, staging ou prod.')
    elif ambiente is not None:
        raise LifecycleError('ambiente só pode ser informado para evidência de deploy.')

    link, created = _upsert_link(
        db,
        requisito=requisito,
        provedor=provedor,
        tipo=tipo,
        repo=repo,
        referencia=referencia,
        url=url,
        titulo=titulo,
        autor=actor,
        ambiente=ambiente,
    )
    db.commit()
    db.refresh(link)

    registrar_evento(
        db,
        correlation_id,
        actor,
        'LIFECYCLE_EVIDENCIA_REGISTRADA',
        'requisito',
        requisito.id,
        json.dumps(
            {
                'codigo': requisito.codigo,
                'provedor': link.provedor,
                'tipo': link.tipo,
                'referencia': link.referencia,
                'ambiente': link.ambiente,
                'created': created,
            },
            ensure_ascii=False,
        ),
    )

    snapshot = lifecycle_snapshot(db, requisito)
    snapshot['evidence_created'] = created
    snapshot['evidence'] = _link_payload(link)
    return snapshot
