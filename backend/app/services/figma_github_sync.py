import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.integracao_figma_github import IntegracaoFigmaGithub
from app.services import figma_client, github_client

DEMO_FILE_KEY = 'reqsys-demo-design'
DEMO_REPO = 'reqsys-enterprise/design-sync'


class FigmaGithubSyncError(RuntimeError):
    pass


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    conflicts: int = 0
    warnings: list[str] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            'created': self.created,
            'updated': self.updated,
            'skipped': self.skipped,
            'conflicts': self.conflicts,
            'warnings': self.warnings,
            'links': self.links,
        }


def sync_enabled() -> bool:
    return bool(settings.enable_figma_github_sync)


def tokens_configurados() -> bool:
    figma_ok = bool((settings.figma_access_token or '').strip())
    from app.services.github_client import github_token_configurado

    return figma_ok and github_token_configurado()


def pode_usar_modo_degradado() -> bool:
    return not settings.is_production


def _demo_issue(number: int) -> dict[str, Any]:
    return {
        'number': number,
        'html_url': f'https://github.com/{DEMO_REPO}/issues/{number}',
        'title': f'[Figma Demo] Item sincronizado #{number}',
        'body': build_marker(DEMO_FILE_KEY, '12:34', f'demo-comment-{number}'),
        'state': 'open',
    }


def garantir_vinculos_demo(db: Session, file_key: str, repo: str) -> SyncResult:
    """Cria vínculos demonstrativos locais sem chamar APIs externas."""
    result = SyncResult()
    if not pode_usar_modo_degradado():
        result.warnings.append('Modo degradado indisponível em produção.')
        return result

    demos = [
        {
            'node_id': '12:34',
            'comment_id': 'demo-comment-1',
            'sync_kind': 'comment',
            'summary': 'Ajustar contraste do botão principal (demo local)',
            'issue_number': 101,
        },
        {
            'node_id': '56:78',
            'comment_id': None,
            'sync_kind': 'frame',
            'summary': 'FRAME: Dashboard Header (demo local)',
            'issue_number': 102,
        },
    ]

    for demo in demos:
        existing = _find_link(db, file_key, repo, demo['node_id'], demo['comment_id'])
        if existing:
            result.skipped += 1
            result.links.append({'id': existing.id, 'figma_file_key': file_key, 'github_issue_number': existing.github_issue_number})
            continue

        issue = _demo_issue(demo['issue_number'])
        figma_hash = _hash_payload(demo)
        github_hash = _hash_payload(issue)
        link = _create_or_update_link(
            db,
            file_key,
            repo,
            demo['node_id'],
            demo['comment_id'],
            demo['sync_kind'],
            issue,
            figma_hash,
            github_hash,
            status='synced',
            conflict_reason=None,
        )
        link.last_synced_at = datetime.now(UTC)
        result.created += 1
        result.links.append({'id': link.id, 'figma_file_key': file_key, 'github_issue_number': issue['number']})

    result.warnings.append('MODO_DEGRADADO: tokens Figma/GitHub ausentes — vínculos demonstrativos locais.')
    db.commit()
    return result


def sync_modo_degradado(
    db: Session,
    file_key: str,
    repo: str,
    node_ids: list[str] | None = None,
    include_comments: bool = True,
    include_frames: bool = True,
    include_dev_resources: bool = True,
) -> SyncResult:
    del node_ids, include_comments, include_frames, include_dev_resources
    return garantir_vinculos_demo(db, file_key, repo)


def build_marker(file_key: str, node_id: str | None = None, comment_id: str | None = None) -> str:
    return f'<!-- reqsys-figma-sync:file={file_key};node={node_id or ""};comment={comment_id or ""} -->'


def _hash_payload(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _direct_figma_url(file_key: str, node_id: str | None = None) -> str:
    url = f'https://www.figma.com/file/{file_key}'
    if node_id:
        url += f'?node-id={node_id}'
    return url


def _extract_node_id_from_comment(comment: dict[str, Any]) -> str | None:
    meta = comment.get('client_meta') or {}
    if isinstance(meta, dict):
        if meta.get('node_id'):
            return str(meta['node_id'])
        if isinstance(meta.get('node_offset'), dict) and meta['node_offset'].get('node_id'):
            return str(meta['node_offset']['node_id'])
    return None


def _short_text(text: str, fallback: str) -> str:
    clean = ' '.join((text or '').split())
    if not clean:
        return fallback
    return clean[:80]


def _find_link(
    db: Session,
    file_key: str,
    repo: str,
    node_id: str | None,
    comment_id: str | None,
) -> IntegracaoFigmaGithub | None:
    return (
        db.query(IntegracaoFigmaGithub)
        .filter(
            IntegracaoFigmaGithub.figma_file_key == file_key,
            IntegracaoFigmaGithub.github_repo == repo,
            IntegracaoFigmaGithub.figma_node_id == node_id,
            IntegracaoFigmaGithub.figma_comment_id == comment_id,
        )
        .first()
    )


def _create_or_update_link(
    db: Session,
    file_key: str,
    repo: str,
    node_id: str | None,
    comment_id: str | None,
    sync_kind: str,
    issue: dict[str, Any],
    figma_hash: str,
    github_hash: str,
    status: str = 'synced',
    conflict_reason: str | None = None,
) -> IntegracaoFigmaGithub:
    link = _find_link(db, file_key, repo, node_id, comment_id)
    if not link:
        link = IntegracaoFigmaGithub(
            figma_file_key=file_key,
            figma_node_id=node_id,
            figma_comment_id=comment_id,
            github_repo=repo,
            sync_kind=sync_kind,
        )
        db.add(link)
    link.github_issue_number = issue.get('number')
    link.github_issue_url = issue.get('html_url')
    link.last_figma_hash = figma_hash
    link.last_github_hash = github_hash
    link.status = status
    link.conflict_reason = conflict_reason
    db.flush()
    return link


def _issue_body(file_key: str, node_id: str | None, comment_id: str | None, summary: str, source: dict[str, Any]) -> str:
    marker = build_marker(file_key=file_key, node_id=node_id, comment_id=comment_id)
    lines = [
        marker,
        '',
        'Sincronizado automaticamente pelo ReqSys.',
        '',
        f'Figma: {_direct_figma_url(file_key, node_id)}',
        f'Tipo: {source.get("sync_kind") or "comment"}',
        '',
        summary,
    ]
    dev_resources = source.get('dev_resources') or []
    if dev_resources:
        lines.extend(['', 'Dev resources:'])
        for resource in dev_resources:
            name = resource.get('name') or resource.get('url') or 'resource'
            url = resource.get('url') or '-'
            lines.append(f'- {name}: {url}')
    return '\n'.join(lines)


def _sync_one_to_github(db: Session, file_key: str, repo: str, source: dict[str, Any], result: SyncResult) -> None:
    node_id = source.get('node_id')
    comment_id = source.get('comment_id')
    marker = build_marker(file_key=file_key, node_id=node_id, comment_id=comment_id)
    figma_hash = _hash_payload(source)
    link = _find_link(db, file_key, repo, node_id, comment_id)

    issue = None
    if link and link.github_issue_number:
        issue = {'number': link.github_issue_number, 'html_url': link.github_issue_url, 'body': '', 'title': ''}
    else:
        try:
            issue = github_client.find_issue_by_marker(repo, marker)
        except Exception as exc:
            result.warnings.append(str(exc))

    summary = source.get('summary') or 'Item Figma sem descricao.'
    body = _issue_body(file_key, node_id, comment_id, summary, source)
    title = f'[Figma] {_short_text(summary, source.get("name") or "Item de design")}'

    if issue:
        github_hash = _hash_payload({'title': issue.get('title'), 'body': issue.get('body'), 'state': issue.get('state')})
        if link and link.last_figma_hash and link.last_figma_hash != figma_hash:
            result.conflicts += 1
            _create_or_update_link(
                db,
                file_key,
                repo,
                node_id,
                comment_id,
                source.get('sync_kind') or 'comment',
                issue,
                figma_hash,
                github_hash,
                status='conflict_resolved_github',
                conflict_reason='GitHub venceu divergencia entre Figma e issue vinculada.',
            )
        else:
            _create_or_update_link(db, file_key, repo, node_id, comment_id, source.get('sync_kind') or 'comment', issue, figma_hash, github_hash)
            result.skipped += 1
        result.links.append({'figma_file_key': file_key, 'figma_node_id': node_id, 'figma_comment_id': comment_id, 'github_issue_number': issue.get('number')})
        return

    try:
        created = github_client.create_issue(repo, title=title, body=body, labels=['figma', 'reqsys-sync'])
    except Exception as exc:
        result.warnings.append(str(exc))
        return

    github_hash = _hash_payload({'title': created.get('title'), 'body': created.get('body'), 'state': created.get('state')})
    link = _create_or_update_link(db, file_key, repo, node_id, comment_id, source.get('sync_kind') or 'comment', created, figma_hash, github_hash)
    result.created += 1
    result.links.append({'id': link.id, 'figma_file_key': file_key, 'figma_node_id': node_id, 'figma_comment_id': comment_id, 'github_issue_number': created.get('number')})


def _collect_comment_sources(file_key: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    try:
        comments = figma_client.get_comments(file_key)
    except figma_client.FigmaError as exc:
        raise FigmaGithubSyncError(str(exc)) from exc
    for comment in comments:
        if comment.get('resolved_at'):
            continue
        message = comment.get('message') or comment.get('text') or ''
        comment_id = str(comment.get('id') or '')
        if not comment_id:
            continue
        node_id = _extract_node_id_from_comment(comment)
        sources.append(
            {
                'sync_kind': 'comment',
                'comment_id': comment_id,
                'node_id': node_id,
                'summary': message,
                'author': ((comment.get('user') or {}).get('handle') or (comment.get('user') or {}).get('email')),
                'created_at': comment.get('created_at'),
            }
        )
    return sources


def _collect_frame_sources(file_key: str, node_ids: list[str]) -> list[dict[str, Any]]:
    if not node_ids:
        return []
    payload = figma_client.get_nodes(file_key, node_ids)
    sources: list[dict[str, Any]] = []
    for node_id, wrapper in (payload.get('nodes') or {}).items():
        document = (wrapper or {}).get('document') or {}
        name = document.get('name') or f'Frame {node_id}'
        node_type = document.get('type') or 'NODE'
        sources.append(
            {
                'sync_kind': 'frame',
                'node_id': str(node_id),
                'comment_id': None,
                'name': name,
                'summary': f'{node_type}: {name}',
                'dev_resources': document.get('devResources') or document.get('dev_resources') or [],
            }
        )
    return sources


def sync_figma_to_github(
    db: Session,
    file_key: str,
    repo: str,
    node_ids: list[str] | None = None,
    include_comments: bool = True,
    include_frames: bool = True,
    include_dev_resources: bool = True,
) -> SyncResult:
    result = SyncResult()
    sources: list[dict[str, Any]] = []
    if include_comments:
        sources.extend(_collect_comment_sources(file_key))
    if include_frames:
        sources.extend(_collect_frame_sources(file_key, node_ids or []))
    if not include_dev_resources:
        for source in sources:
            source.pop('dev_resources', None)

    for source in sources:
        _sync_one_to_github(db, file_key, repo, source, result)

    db.commit()
    return result


def sync_github_to_figma(db: Session, file_key: str | None = None, repo: str | None = None) -> SyncResult:
    result = SyncResult()
    query = db.query(IntegracaoFigmaGithub)
    if file_key:
        query = query.filter(IntegracaoFigmaGithub.figma_file_key == file_key)
    if repo:
        query = query.filter(IntegracaoFigmaGithub.github_repo == repo)

    for link in query.all():
        if not link.github_issue_number:
            result.skipped += 1
            continue
        message = f'GitHub #{link.github_issue_number} atualizado: {link.github_issue_url or ""}'.strip()
        try:
            figma_client.create_comment(link.figma_file_key, message, node_id=link.figma_node_id)
        except Exception as exc:
            result.warnings.append(str(exc))
            continue
        link.status = 'synced'
        link.conflict_reason = None
        result.updated += 1
        result.links.append({'id': link.id, 'github_issue_number': link.github_issue_number, 'figma_file_key': link.figma_file_key})
    db.commit()
    return result


def sync_bidirectional(
    db: Session,
    file_key: str,
    repo: str,
    node_ids: list[str] | None = None,
    include_comments: bool = True,
    include_frames: bool = True,
    include_dev_resources: bool = True,
) -> SyncResult:
    first = sync_figma_to_github(db, file_key, repo, node_ids, include_comments, include_frames, include_dev_resources)
    second = sync_github_to_figma(db, file_key, repo)
    first.created += second.created
    first.updated += second.updated
    first.skipped += second.skipped
    first.conflicts += second.conflicts
    first.warnings.extend(second.warnings)
    first.links.extend(second.links)
    return first


def handle_github_issue_event(db: Session, payload: dict[str, Any]) -> SyncResult:
    issue = payload.get('issue') or {}
    repo_info = payload.get('repository') or {}
    repo = repo_info.get('full_name')
    number = issue.get('number')
    result = SyncResult()
    if not repo or not number:
        result.skipped += 1
        return result
    link = (
        db.query(IntegracaoFigmaGithub)
        .filter(IntegracaoFigmaGithub.github_repo == repo, IntegracaoFigmaGithub.github_issue_number == number)
        .first()
    )
    if not link:
        result.skipped += 1
        return result
    action = payload.get('action') or 'updated'
    message = f'GitHub #{number} {action}: {issue.get("html_url") or link.github_issue_url or ""}'.strip()
    try:
        figma_client.create_comment(link.figma_file_key, message, node_id=link.figma_node_id)
    except Exception as exc:
        result.warnings.append(str(exc))
        return result
    link.status = 'synced'
    link.last_github_hash = _hash_payload(issue)
    result.updated += 1
    db.commit()
    return result
