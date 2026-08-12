import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.security import require_admin
from app.services import github_client
from app.services.github_client import GitHubError

logger = logging.getLogger('reqsys.github_merge_console')

router = APIRouter(prefix='/v1/admin/github-merge', tags=['Console de Merge Governado'])


class MergeAssincronoRequest(BaseModel):
    repositorio: str = Field(pattern=r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$', max_length=160)
    pull_request: int = Field(gt=0)
    sha_esperado: str = Field(pattern=r'^[0-9a-f]{40}$')
    metodo: Literal['merge', 'squash', 'rebase'] = 'squash'
    acao: Literal['default', 'direct_merge', 'merge_queue'] = 'default'
    titulo_commit: str = Field(min_length=1, max_length=256)
    mensagem_commit: str = Field(default='', max_length=4096)


def _resumo_checks(checks: list[dict]) -> dict:
    bloqueadores = [
        {'nome': check.get('name'), 'status': check.get('status'), 'conclusao': check.get('conclusion')}
        for check in checks
        if check.get('status') != 'completed'
        or check.get('conclusion') not in {'success', 'neutral', 'skipped'}
    ]
    return {'total': len(checks), 'bloqueadores': bloqueadores, 'aprovados': len(checks) - len(bloqueadores)}


def _carregar_pr(repositorio: str, pull_request: int) -> tuple[dict, dict]:
    pr = github_client.get_pull_request(repositorio, pull_request)
    sha = ((pr.get('head') or {}).get('sha') or '').lower()
    checks = github_client.list_check_runs(repositorio, sha) if sha else []
    return pr, _resumo_checks(checks)


@router.get('/pull-requests/{pull_request}')
def consultar_pull_request(
    pull_request: int,
    repositorio: str = Query(max_length=160),
    _: dict = Depends(require_admin),
):
    try:
        pr, checks = _carregar_pr(repositorio, pull_request)
    except GitHubError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return ok(
        {
            'repositorio': repositorio,
            'pull_request': pull_request,
            'titulo': pr.get('title'),
            'estado': pr.get('state'),
            'rascunho': bool(pr.get('draft')),
            'mergeavel': pr.get('mergeable'),
            'sha': (pr.get('head') or {}).get('sha'),
            'branch_origem': (pr.get('head') or {}).get('ref'),
            'branch_destino': (pr.get('base') or {}).get('ref'),
            'url': pr.get('html_url'),
            'checks': checks,
        }
    )


@router.post('/merge-assincrono')
def solicitar_merge_assincrono(
    body: MergeAssincronoRequest,
    x_correlation_id: str | None = Header(default=None),
    usuario: dict = Depends(require_admin),
):
    try:
        pr, checks = _carregar_pr(body.repositorio, body.pull_request)
        sha_atual = ((pr.get('head') or {}).get('sha') or '').lower()
        if pr.get('state') != 'open':
            raise HTTPException(status_code=409, detail='A pull request nao esta aberta.')
        if pr.get('draft'):
            raise HTTPException(status_code=409, detail='A pull request ainda e rascunho.')
        if sha_atual != body.sha_esperado.lower():
            raise HTTPException(status_code=409, detail=f'SHA divergente. SHA atual: {sha_atual}.')
        if checks['bloqueadores']:
            raise HTTPException(status_code=409, detail={'mensagem': 'Existem checks bloqueadores.', 'checks': checks})

        resultado = github_client.request_async_merge(
            body.repositorio,
            body.pull_request,
            expected_sha=body.sha_esperado,
            merge_method=body.metodo,
            merge_action=body.acao,
            commit_title=body.titulo_commit,
            commit_message=body.mensagem_commit,
        )
    except HTTPException:
        raise
    except GitHubError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    logger.info(
        'github_merge_assincrono_solicitado ator=%s repo=%s pr=%s sha=%s correlation_id=%s',
        usuario.get('sub', 'admin'),
        body.repositorio,
        body.pull_request,
        body.sha_esperado,
        x_correlation_id or 'nao-informado',
    )
    return ok({'solicitacao': resultado, 'checks': checks, 'correlation_id': x_correlation_id})


@router.get('/pull-requests/{pull_request}/merge-assincrono/{merge_uuid}')
def consultar_merge_assincrono(
    pull_request: int,
    merge_uuid: str = Path(pattern=r'^[0-9a-fA-F-]{36}$'),
    repositorio: str = Query(max_length=160),
    _: dict = Depends(require_admin),
):
    try:
        resultado = github_client.get_async_merge(repositorio, pull_request, merge_uuid)
    except GitHubError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return ok(resultado)
