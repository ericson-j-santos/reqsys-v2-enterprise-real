"""Adapter GitHub do ciclo de vida de requisitos.

Incremento 1: cria ou reutiliza uma Issue GitHub a partir do código canônico do
requisito. O vínculo persistente continua sendo responsabilidade do
orquestrador, em ``VinculoGit``.
"""

from __future__ import annotations

from typing import Any
from urllib import parse

from app.core.secrets import get_secret
from app.services.github_redmine import IntegracaoError, _parse_repo, _request_json


def find_or_create_requirement_issue(
    *,
    repo: str,
    requirement_code: str,
    title: str,
    description: str,
    redmine_url: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Localiza por código ou cria a Issue técnica do requisito.

    A busca antes do POST reduz duplicidades em reexecuções. A idempotência
    primária é garantida pelo vínculo local do ReqSys; esta busca também cobre
    o cenário em que a Issue foi criada e a persistência local falhou depois.
    """

    owner, name = _parse_repo(repo)
    token = (get_secret('GITHUB_TOKEN', '') or '').strip()
    if not token:
        raise IntegracaoError('GITHUB_TOKEN não configurado para o ciclo de vida do requisito.')

    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }

    query = f'repo:{owner}/{name} is:issue in:title "{requirement_code}"'
    search_url = f'https://api.github.com/search/issues?{parse.urlencode({"q": query, "per_page": "20"})}'
    found = _request_json('GET', search_url, headers=headers)

    for item in found.get('items', []):
        item_title = str(item.get('title') or '')
        if requirement_code.lower() in item_title.lower():
            return {
                'issue_number': item.get('number'),
                'github_url': item.get('html_url'),
                'title': item_title,
                'created': False,
            }

    body_lines = [
        f'## Requisito canônico\n`{requirement_code}`',
        '',
        '## Descrição',
        description.strip(),
        '',
        '## Rastreabilidade',
        f'- ReqSys: `{requirement_code}`',
        f'- Redmine: {redmine_url or "ainda não vinculado"}',
        f'- Correlation ID: `{correlation_id or "não informado"}`',
        '',
        'Esta Issue é gerenciada pelo ciclo de vida do ReqSys. Não remova o código do requisito do título.',
    ]

    created = _request_json(
        'POST',
        f'https://api.github.com/repos/{owner}/{name}/issues',
        headers=headers,
        payload={
            'title': f'[{requirement_code}] {title}',
            'body': '\n'.join(body_lines),
        },
    )
    return {
        'issue_number': created.get('number'),
        'github_url': created.get('html_url'),
        'title': created.get('title'),
        'created': True,
    }
