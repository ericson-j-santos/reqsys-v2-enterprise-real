import json
import os
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError

from app.core.secrets import get_secret


class IntegracaoError(RuntimeError):
    pass


def github_redmine_import_enabled() -> bool:
    value = os.getenv("ENABLE_GITHUB_REDMINE_IMPORT", "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _request_json(method: str, url: str, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> Any:
    body = None
    req_headers = {"User-Agent": "reqsys-integracao/2.1", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = request.Request(url=url, data=body, headers=req_headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise IntegracaoError(f"HTTP {exc.code} em {url}: {detail[:400]}") from exc
    except URLError as exc:
        raise IntegracaoError(f"Falha de rede em {url}: {exc.reason}") from exc


def _parse_repo(repo: str) -> tuple[str, str]:
    clean = (repo or "").strip().strip("/")
    parts = clean.split("/")
    if len(parts) != 2 or not all(parts):
        raise IntegracaoError("Repo inválido. Use owner/repo.")
    return parts[0], parts[1]


def fetch_github_issues(repo: str, state: str = "open", limit: int = 20, labels: list[str] | None = None) -> list[dict[str, Any]]:
    owner, name = _parse_repo(repo)
    query = {
        "state": state or "open",
        "per_page": str(max(1, min(limit, 100))),
    }
    if labels:
        query["labels"] = ",".join([s.strip() for s in labels if s and s.strip()])

    token = (get_secret('GITHUB_TOKEN', '') or '').strip()
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{owner}/{name}/issues?{parse.urlencode(query)}"
    payload = _request_json("GET", url, headers=headers)
    issues: list[dict[str, Any]] = []
    for item in payload:
        if item.get("pull_request"):
            continue
        issues.append(
            {
                "id": item.get("id"),
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "html_url": item.get("html_url"),
                "labels": [l.get("name") for l in item.get("labels", []) if l.get("name")],
            }
        )
    return issues


def publish_requisito_to_redmine(
    requisito: Any,
    project_id: int | None = None,
    tracker_id: int | None = None,
    priority_id: int | None = None,
) -> dict[str, Any]:
    base_url = (get_secret('REDMINE_BASE_URL', '') or '').strip().rstrip('/')
    api_key = (get_secret('REDMINE_API_KEY', '') or '').strip()
    env_project_id = (get_secret('REDMINE_PROJECT_ID', '') or '').strip()

    effective_project_id = project_id or (int(env_project_id) if env_project_id.isdigit() else None)
    if not base_url or not api_key or not effective_project_id:
        return {
            'issue_principal_id': None,
            'subtarefas': [],
            'warnings': ['Redmine nao configurado. Defina REDMINE_BASE_URL, REDMINE_API_KEY e REDMINE_PROJECT_ID.'],
        }

    headers = {'X-Redmine-API-Key': api_key}
    urgencia_label = {'alta': 'Alta', 'media': 'Normal', 'baixa': 'Baixa'}.get(
        (requisito.urgencia or 'media').lower(), 'Normal'
    )

    descricao_formatada = (
        f"h2. {requisito.codigo} — {requisito.titulo}\n\n"
        f"*Sistema:* {requisito.sistema}\n"
        f"*Área:* {requisito.area}\n"
        f"*Solicitante:* {requisito.solicitante}\n"
        f"*Urgência:* {urgencia_label}\n"
        f"*Impacto Regulatório:* {'Sim' if requisito.impacto_regulatorio else 'Não'}\n\n"
        f"---\n\n"
        f"{requisito.descricao}"
    )

    issue_payload: dict[str, Any] = {
        'issue': {
            'project_id': effective_project_id,
            'subject': f"[{requisito.codigo}] {requisito.titulo}",
            'description': descricao_formatada,
        }
    }
    if tracker_id:
        issue_payload['issue']['tracker_id'] = tracker_id
    if priority_id:
        issue_payload['issue']['priority_id'] = priority_id

    try:
        created = _request_json('POST', f'{base_url}/issues.json', headers=headers, payload=issue_payload)
    except IntegracaoError as exc:
        return {'issue_principal_id': None, 'subtarefas': [], 'warnings': [str(exc)]}

    principal_id = (created.get('issue') or {}).get('id')
    subtarefas: list[dict[str, Any]] = []
    warnings: list[str] = []

    for componente in ('Frontend', 'Backend', 'Dados', 'QA'):
        sub_payload: dict[str, Any] = {
            'issue': {
                'project_id': effective_project_id,
                'subject': f"[{requisito.codigo}] {componente}",
                'parent_issue_id': principal_id,
            }
        }
        if tracker_id:
            sub_payload['issue']['tracker_id'] = tracker_id
        try:
            sub = _request_json('POST', f'{base_url}/issues.json', headers=headers, payload=sub_payload)
            sub_id = (sub.get('issue') or {}).get('id')
            subtarefas.append({'id': sub_id, 'subject': componente})
        except IntegracaoError as exc:
            warnings.append(f'Subtarefa {componente}: {exc}')

    return {'issue_principal_id': principal_id, 'subtarefas': subtarefas, 'warnings': warnings}


def publish_issues_to_redmine(repo: str, issues: list[dict[str, Any]], project_id: int | None = None, tracker_id: int | None = None, priority_id: int | None = None) -> dict[str, Any]:
    base_url = (get_secret('REDMINE_BASE_URL', '') or '').strip().rstrip("/")
    api_key = (get_secret('REDMINE_API_KEY', '') or '').strip()
    env_project_id = (get_secret('REDMINE_PROJECT_ID', '') or '').strip()

    effective_project_id = project_id or (int(env_project_id) if env_project_id.isdigit() else None)
    if not base_url or not api_key or not effective_project_id:
        return {
            "published_count": 0,
            "published_issues": [],
            "warnings": [
                "Publicação real no Redmine não configurada. Defina REDMINE_BASE_URL, REDMINE_API_KEY e REDMINE_PROJECT_ID.",
            ],
        }

    published: list[dict[str, Any]] = []
    warnings: list[str] = []
    headers = {"X-Redmine-API-Key": api_key}

    for issue in issues:
        number = issue.get("number")
        title = issue.get("title") or "Issue sem título"
        description = (
            f"Importado do GitHub\n"
            f"Repo: {repo}\n"
            f"Issue: #{number}\n"
            f"URL: {issue.get('html_url') or '-'}\n"
            f"Labels: {', '.join(issue.get('labels') or []) or '-'}"
        )

        payload = {
            "issue": {
                "project_id": effective_project_id,
                "subject": f"[GitHub #{number}] {title}",
                "description": description,
            }
        }
        if tracker_id:
            payload["issue"]["tracker_id"] = tracker_id
        if priority_id:
            payload["issue"]["priority_id"] = priority_id

        try:
            created = _request_json("POST", f"{base_url}/issues.json", headers=headers, payload=payload)
            redmine_issue = created.get("issue") or {}
            redmine_id = redmine_issue.get("id")
            published.append(
                {
                    "github_number": number,
                    "github_title": title,
                    "redmine_issue_id": redmine_id,
                    "redmine_url": f"{base_url}/issues/{redmine_id}" if redmine_id else None,
                }
            )
        except IntegracaoError as exc:
            warnings.append(str(exc))

    return {
        "published_count": len(published),
        "published_issues": published,
        "warnings": warnings,
    }
