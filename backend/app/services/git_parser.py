import re
from typing import Any

_REQ_PATTERN = re.compile(r'\bREQ-\d{6,9}\b', re.IGNORECASE)
_AGI_PATTERN = re.compile(r'\bAGI-\d{6,12}\b', re.IGNORECASE)

# branches mapeadas para ambiente de deploy
_BRANCH_AMBIENTES: dict[str, str] = {
    'main': 'prod', 'master': 'prod', 'prod': 'prod', 'production': 'prod',
    'staging': 'staging', 'stg': 'staging', 'homolog': 'staging', 'hml': 'staging',
    'develop': 'dev', 'dev': 'dev', 'development': 'dev',
}


def extrair_codigos_requisito(texto: str) -> list[str]:
    """Extrai códigos REQ-XXXXXX únicos de qualquer texto, normalizados para maiúsculo."""
    return list({m.upper() for m in _REQ_PATTERN.findall(texto or '')})


def extrair_codigos_agile(texto: str) -> list[str]:
    """Extrai códigos AGI-XXXXXX de work items em commits, PRs ou MRs."""
    return list({m.upper() for m in _AGI_PATTERN.findall(texto or '')})


def inferir_ambiente_branch(branch: str) -> str | None:
    """Infere ambiente de deploy a partir do nome da branch (dev/staging/prod)."""
    return _BRANCH_AMBIENTES.get((branch or '').lower())


def _inferir_ambiente(branch: str) -> str | None:
    return inferir_ambiente_branch(branch)


def processar_push_github(payload: dict[str, Any]) -> list[dict[str, Any]]:
    repo = (payload.get('repository') or {}).get('full_name', '')
    branch = (payload.get('ref') or '').removeprefix('refs/heads/')
    resultados: list[dict[str, Any]] = []

    for commit in payload.get('commits') or []:
        mensagem = commit.get('message') or ''
        codigos = extrair_codigos_requisito(mensagem)
        if not codigos:
            continue
        author_info = commit.get('author') or {}
        autor = author_info.get('username') or author_info.get('name') or ''
        for codigo in codigos:
            resultados.append({
                'requisito_codigo': codigo,
                'tipo': 'commit',
                'provedor': 'github',
                'repo': repo,
                'referencia': (commit.get('id') or '')[:40],
                'url': commit.get('url'),
                'titulo': mensagem.splitlines()[0][:200],
                'autor': autor,
                'ambiente': _inferir_ambiente(branch),
            })
    return resultados


def processar_push_github_agile(payload: dict[str, Any]) -> list[dict[str, Any]]:
    repo = (payload.get('repository') or {}).get('full_name', '')
    branch = (payload.get('ref') or '').removeprefix('refs/heads/')
    resultados: list[dict[str, Any]] = []

    for commit in payload.get('commits') or []:
        mensagem = commit.get('message') or ''
        codigos = extrair_codigos_agile(mensagem)
        if not codigos:
            continue
        author_info = commit.get('author') or {}
        autor = author_info.get('username') or author_info.get('name') or ''
        for codigo in codigos:
            resultados.append({
                'work_item_codigo': codigo,
                'tipo': 'commit',
                'provedor': 'github',
                'repo': repo,
                'branch': branch,
                'referencia': (commit.get('id') or '')[:40],
                'url': commit.get('url'),
                'titulo': mensagem.splitlines()[0][:200],
                'autor': autor,
                'ambiente': _inferir_ambiente(branch),
            })
    return resultados


def processar_pr_github(payload: dict[str, Any]) -> list[dict[str, Any]]:
    pr = payload.get('pull_request') or {}
    repo = (payload.get('repository') or {}).get('full_name', '')
    texto = f"{pr.get('title') or ''} {pr.get('body') or ''}"
    codigos = extrair_codigos_requisito(texto)
    if not codigos:
        return []

    autor = (pr.get('user') or {}).get('login', '')
    branch = (pr.get('head') or {}).get('ref', '')
    action = payload.get('action', '')
    pr_merged = action == 'closed' and bool(pr.get('merged'))

    return [
        {
            'requisito_codigo': codigo,
            'tipo': 'pr',
            'provedor': 'github',
            'repo': repo,
            'referencia': str(pr.get('number', '')),
            'url': pr.get('html_url'),
            'titulo': (pr.get('title') or '')[:200],
            'autor': autor,
            'ambiente': _inferir_ambiente(branch),
            'pr_merged': pr_merged,
        }
        for codigo in codigos
    ]


def processar_pr_github_agile(payload: dict[str, Any]) -> list[dict[str, Any]]:
    pr = payload.get('pull_request') or {}
    repo = (payload.get('repository') or {}).get('full_name', '')
    texto = f"{pr.get('title') or ''} {pr.get('body') or ''}"
    codigos = extrair_codigos_agile(texto)
    if not codigos:
        return []

    autor = (pr.get('user') or {}).get('login', '')
    branch = (pr.get('head') or {}).get('ref', '')
    action = payload.get('action', '')
    pr_merged = action == 'closed' and bool(pr.get('merged'))

    return [
        {
            'work_item_codigo': codigo,
            'tipo': 'pr',
            'provedor': 'github',
            'repo': repo,
            'branch': branch,
            'referencia': str(pr.get('number', '')),
            'url': pr.get('html_url'),
            'titulo': (pr.get('title') or '')[:200],
            'autor': autor,
            'ambiente': _inferir_ambiente(branch),
            'pr_merged': pr_merged,
        }
        for codigo in codigos
    ]


def processar_push_gitlab(payload: dict[str, Any]) -> list[dict[str, Any]]:
    repo = (payload.get('project') or {}).get('path_with_namespace', '')
    branch = (payload.get('ref') or '').removeprefix('refs/heads/')
    resultados: list[dict[str, Any]] = []

    for commit in payload.get('commits') or []:
        mensagem = commit.get('message') or ''
        codigos = extrair_codigos_requisito(mensagem)
        if not codigos:
            continue
        autor = (commit.get('author') or {}).get('name', '')
        for codigo in codigos:
            resultados.append({
                'requisito_codigo': codigo,
                'tipo': 'commit',
                'provedor': 'gitlab',
                'repo': repo,
                'referencia': (commit.get('id') or '')[:40],
                'url': commit.get('url'),
                'titulo': mensagem.splitlines()[0][:200],
                'autor': autor,
                'ambiente': _inferir_ambiente(branch),
            })
    return resultados


def processar_push_gitlab_agile(payload: dict[str, Any]) -> list[dict[str, Any]]:
    repo = (payload.get('project') or {}).get('path_with_namespace', '')
    branch = (payload.get('ref') or '').removeprefix('refs/heads/')
    resultados: list[dict[str, Any]] = []

    for commit in payload.get('commits') or []:
        mensagem = commit.get('message') or ''
        codigos = extrair_codigos_agile(mensagem)
        if not codigos:
            continue
        autor = (commit.get('author') or {}).get('name', '')
        for codigo in codigos:
            resultados.append({
                'work_item_codigo': codigo,
                'tipo': 'commit',
                'provedor': 'gitlab',
                'repo': repo,
                'branch': branch,
                'referencia': (commit.get('id') or '')[:40],
                'url': commit.get('url'),
                'titulo': mensagem.splitlines()[0][:200],
                'autor': autor,
                'ambiente': _inferir_ambiente(branch),
            })
    return resultados


def processar_mr_gitlab(payload: dict[str, Any]) -> list[dict[str, Any]]:
    attrs = payload.get('object_attributes') or {}
    repo = (payload.get('project') or {}).get('path_with_namespace', '')
    texto = f"{attrs.get('title') or ''} {attrs.get('description') or ''}"
    codigos = extrair_codigos_requisito(texto)
    if not codigos:
        return []

    autor = (payload.get('user') or {}).get('username', '')
    branch = attrs.get('source_branch', '')
    mr_merged = attrs.get('state') == 'merged'

    return [
        {
            'requisito_codigo': codigo,
            'tipo': 'merge_request',
            'provedor': 'gitlab',
            'repo': repo,
            'referencia': str(attrs.get('iid', '')),
            'url': attrs.get('url'),
            'titulo': (attrs.get('title') or '')[:200],
            'autor': autor,
            'ambiente': _inferir_ambiente(branch),
            'mr_merged': mr_merged,
        }
        for codigo in codigos
    ]


def processar_mr_gitlab_agile(payload: dict[str, Any]) -> list[dict[str, Any]]:
    attrs = payload.get('object_attributes') or {}
    repo = (payload.get('project') or {}).get('path_with_namespace', '')
    texto = f"{attrs.get('title') or ''} {attrs.get('description') or ''}"
    codigos = extrair_codigos_agile(texto)
    if not codigos:
        return []

    autor = (payload.get('user') or {}).get('username', '')
    branch = attrs.get('source_branch', '')
    mr_merged = attrs.get('state') == 'merged'

    return [
        {
            'work_item_codigo': codigo,
            'tipo': 'merge_request',
            'provedor': 'gitlab',
            'repo': repo,
            'branch': branch,
            'referencia': str(attrs.get('iid', '')),
            'url': attrs.get('url'),
            'titulo': (attrs.get('title') or '')[:200],
            'autor': autor,
            'ambiente': _inferir_ambiente(branch),
            'mr_merged': mr_merged,
        }
        for codigo in codigos
    ]
