from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.core.envelope import ok
from app.core.security import require_admin
from app.services import repository_admin
from app.services.github_client import GitHubError

router = APIRouter(
    prefix='/v1/admin/repositories',
    tags=['Repository Admin Control Plane'],
)


def _repo(owner: str, repository: str) -> str:
    return f'{owner}/{repository}'


@router.get('')
def listar_repositorios(_: dict = Depends(require_admin)):
    try:
        repositories = repository_admin.list_repositories()
    except repository_admin.RepositoryAdminError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ok({'repositories': repositories})


@router.get('/{owner}/{repository}/snapshot')
def consultar_snapshot(
    owner: str = Path(pattern=r'^[A-Za-z0-9_.-]+$'),
    repository: str = Path(pattern=r'^[A-Za-z0-9_.-]+$'),
    _: dict = Depends(require_admin),
):
    target = _repo(owner, repository)
    try:
        snapshot = repository_admin.build_snapshot(target)
    except repository_admin.RepositoryAdminError as exc:
        code = 404 if 'nao administrado' in str(exc) else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except GitHubError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ok(snapshot)


@router.get('/{owner}/{repository}/pull-requests/{pull_request}/decision')
def consultar_decisao_pr(
    pull_request: int = Path(gt=0),
    owner: str = Path(pattern=r'^[A-Za-z0-9_.-]+$'),
    repository: str = Path(pattern=r'^[A-Za-z0-9_.-]+$'),
    _: dict = Depends(require_admin),
):
    target = _repo(owner, repository)
    try:
        decision = repository_admin.decide_pull_request(target, pull_request)
    except repository_admin.RepositoryAdminError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GitHubError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ok(decision)
