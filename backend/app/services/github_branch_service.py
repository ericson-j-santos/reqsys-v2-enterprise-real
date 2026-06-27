from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.agile_runtime import AgileWorkItem
from app.services import github_client
from app.services.auditoria import registrar_evento
from app.services.github_launchpad import (
    montar_github_launchpad,
    normalizar_ambiente_launchpad,
)
from app.services.increment_gate_service import verificar_increment_gate


class GithubBranchError(RuntimeError):
    pass


def criar_branch_work_item(
    db: Session,
    item: AgileWorkItem,
    ambiente: str,
    *,
    correlation_id: str,
    criar_se_ausente: bool = True,
    aplicar_branch_no_item: bool = True,
) -> dict:
    amb = normalizar_ambiente_launchpad(ambiente)
    if amb == 'prod':
        raise GithubBranchError('Criacao de branch bloqueada para ambiente produtivo.')

    gate = verificar_increment_gate('new_front', reference=item.codigo)
    if not gate['permitido']:
        raise GithubBranchError(gate['detalhe'])

    if not github_client.github_token_configurado():
        raise GithubBranchError('GITHUB_TOKEN nao configurado para criar branch via API.')

    launchpad = montar_github_launchpad(item, ambiente, db)
    repo = launchpad['repositorio']
    branch = launchpad['branch_trabalho']
    branch_base = launchpad['branch_base']

    branch_existe = github_client.get_branch_sha(repo, branch) is not None
    if branch_existe and not criar_se_ausente:
        raise GithubBranchError(f'Branch {branch} ja existe no repositorio {repo}.')

    if branch_existe:
        if aplicar_branch_no_item and not item.branch:
            item.branch = branch
            item.repositorio = repo
            db.add(item)
            db.commit()
            db.refresh(item)
        return {
            'criada': False,
            'branch': branch,
            'repositorio': repo,
            'branch_base': branch_base,
            'branch_existe': True,
            'increment_gate': gate,
            'links': launchpad['links'],
            'motivo': 'branch_ja_existe',
        }

    base_sha = github_client.get_branch_sha(repo, branch_base)
    if not base_sha:
        raise GithubBranchError(f'Branch base {branch_base} nao encontrada em {repo}.')

    github_client.create_branch(repo, branch, base_sha)

    if aplicar_branch_no_item:
        item.branch = branch
        item.repositorio = repo
        db.add(item)
        db.commit()
        db.refresh(item)

    registrar_evento(
        db,
        correlation_id,
        'github-launchpad',
        'AGILE_GITHUB_BRANCH_CRIADA',
        'agile_work_item',
        item.id,
        f'{{"branch":"{branch}","repo":"{repo}","base":"{branch_base}"}}',
    )

    launchpad_atualizado = montar_github_launchpad(item, ambiente, db)
    launchpad_atualizado['branch_existe'] = True
    launchpad_atualizado['increment_gate'] = gate

    return {
        'criada': True,
        'branch': branch,
        'repositorio': repo,
        'branch_base': branch_base,
        'branch_existe': True,
        'increment_gate': gate,
        'links': launchpad_atualizado['links'],
        'motivo': 'branch_criada',
    }
