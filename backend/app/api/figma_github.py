from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.envelope import ok
from app.db import get_db
from app.models.integracao_figma_github import IntegracaoFigmaGithub
from app.services import figma_github_sync

router = APIRouter(prefix='/v1/integracoes/figma-github', tags=['Integracoes Figma GitHub'])


class FigmaGithubSyncIn(BaseModel):
    file_key: str | None = None
    repo: str | None = None
    mode: Literal['figma_to_github', 'github_to_figma', 'bidirectional'] = 'bidirectional'
    node_ids: list[str] = Field(default_factory=list)
    include_comments: bool = True
    include_frames: bool = True
    include_dev_resources: bool = True


def _resolve_file_key(value: str | None) -> str:
    file_key = (value or settings.figma_default_file_key or '').strip()
    if not file_key:
        raise HTTPException(status_code=422, detail='file_key e obrigatorio quando FIGMA_DEFAULT_FILE_KEY nao esta configurado.')
    return file_key


def _resolve_repo(value: str | None) -> str:
    repo = (value or settings.figma_github_default_repo or '').strip()
    if not repo:
        raise HTTPException(status_code=422, detail='repo e obrigatorio quando FIGMA_GITHUB_DEFAULT_REPO nao esta configurado.')
    return repo


@router.get('/config')
def config_figma_github():
    return ok({
        'has_default_file_key': bool((settings.figma_default_file_key or '').strip()),
        'has_default_repo': bool((settings.figma_github_default_repo or '').strip()),
        'sync_enabled': figma_github_sync.sync_enabled(),
    })


@router.post('/sync')
def sincronizar_figma_github(payload: FigmaGithubSyncIn, db: Session = Depends(get_db)):
    if not figma_github_sync.sync_enabled():
        raise HTTPException(status_code=409, detail='Integracao Figma GitHub desabilitada por feature flag.')

    file_key = _resolve_file_key(payload.file_key)
    repo = _resolve_repo(payload.repo)

    try:
        if payload.mode == 'figma_to_github':
            result = figma_github_sync.sync_figma_to_github(
                db,
                file_key=file_key,
                repo=repo,
                node_ids=payload.node_ids,
                include_comments=payload.include_comments,
                include_frames=payload.include_frames,
                include_dev_resources=payload.include_dev_resources,
            )
        elif payload.mode == 'github_to_figma':
            result = figma_github_sync.sync_github_to_figma(db, file_key=file_key, repo=repo)
        else:
            result = figma_github_sync.sync_bidirectional(
                db,
                file_key=file_key,
                repo=repo,
                node_ids=payload.node_ids,
                include_comments=payload.include_comments,
                include_frames=payload.include_frames,
                include_dev_resources=payload.include_dev_resources,
            )
    except figma_github_sync.FigmaGithubSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ok({'file_key': file_key, 'repo': repo, 'mode': payload.mode, **result.as_dict()})


@router.get('/status')
def status_figma_github(
    file_key: str | None = Query(default=None),
    repo: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(IntegracaoFigmaGithub)
    if file_key:
        query = query.filter(IntegracaoFigmaGithub.figma_file_key == file_key)
    if repo:
        query = query.filter(IntegracaoFigmaGithub.github_repo == repo)
    if status:
        query = query.filter(IntegracaoFigmaGithub.status == status)

    items = []
    for link in query.order_by(IntegracaoFigmaGithub.id.desc()).limit(100).all():
        items.append(
            {
                'id': link.id,
                'figma_file_key': link.figma_file_key,
                'figma_node_id': link.figma_node_id,
                'figma_comment_id': link.figma_comment_id,
                'github_repo': link.github_repo,
                'github_issue_number': link.github_issue_number,
                'github_issue_url': link.github_issue_url,
                'sync_kind': link.sync_kind,
                'status': link.status,
                'conflict_reason': link.conflict_reason,
                'last_synced_at': link.last_synced_at.isoformat() if link.last_synced_at else None,
            }
        )

    return ok({'total': len(items), 'items': items})
