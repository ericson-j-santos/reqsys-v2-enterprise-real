import json
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError

from app.core.secrets import get_secret


class GitHubError(RuntimeError):
    pass


def _parse_repo(repo: str) -> tuple[str, str]:
    clean = (repo or '').strip().strip('/')
    parts = clean.split('/')
    if len(parts) != 2 or not all(parts):
        raise GitHubError('Repo invalido. Use owner/repo.')
    return parts[0], parts[1]


def _request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    token = (get_secret('GITHUB_TOKEN', '') or '').strip()
    if not token:
        raise GitHubError('GITHUB_TOKEN nao configurado.')

    body = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'reqsys-figma-github-sync/1.0',
    }
    if body is not None:
        headers['Content-Type'] = 'application/json'

    req = request.Request(url=f'https://api.github.com{path}', data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as resp:  # nosec B310
            raw = resp.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise GitHubError(f'HTTP {exc.code} no GitHub: {detail[:400]}') from exc
    except URLError as exc:
        raise GitHubError(f'Falha de rede no GitHub: {exc.reason}') from exc


def list_issues(repo: str, state: str = 'all', limit: int = 100) -> list[dict[str, Any]]:
    owner, name = _parse_repo(repo)
    query = parse.urlencode({'state': state, 'per_page': str(max(1, min(limit, 100)))})
    payload = _request_json('GET', f'/repos/{owner}/{name}/issues?{query}')
    return [item for item in payload if not item.get('pull_request')]


def create_issue(repo: str, title: str, body: str, labels: list[str] | None = None) -> dict[str, Any]:
    owner, name = _parse_repo(repo)
    payload: dict[str, Any] = {'title': title, 'body': body}
    if labels:
        payload['labels'] = labels
    return _request_json('POST', f'/repos/{owner}/{name}/issues', payload)


def update_issue(repo: str, number: int, title: str | None = None, body: str | None = None, state: str | None = None) -> dict[str, Any]:
    owner, name = _parse_repo(repo)
    payload = {k: v for k, v in {'title': title, 'body': body, 'state': state}.items() if v is not None}
    return _request_json('PATCH', f'/repos/{owner}/{name}/issues/{number}', payload)


def create_issue_comment(repo: str, number: int, body: str) -> dict[str, Any]:
    owner, name = _parse_repo(repo)
    return _request_json('POST', f'/repos/{owner}/{name}/issues/{number}/comments', {'body': body})


def find_issue_by_marker(repo: str, marker: str) -> dict[str, Any] | None:
    for issue in list_issues(repo=repo, state='all', limit=100):
        if marker in (issue.get('body') or ''):
            return issue
    return None
