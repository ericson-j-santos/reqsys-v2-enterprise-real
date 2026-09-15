"""Adapter Redmine para o lifecycle.

Reusa o transporte resiliente já existente em ``github_redmine`` (retry e
circuit breaker) e restringe as escritas deste incremento aos campos cuja
fonte canônica é o ReqSys.
"""

from __future__ import annotations

from typing import Any

from app.core.secrets import get_secret
from app.services.github_redmine import IntegracaoError, _request_json

_REQSYS_OWNED_FIELDS = {'subject', 'description'}


def _redmine_config() -> tuple[str, str]:
    base_url = (get_secret('REDMINE_BASE_URL', '') or '').strip().rstrip('/')
    api_key = (get_secret('REDMINE_API_KEY', '') or '').strip()
    if not base_url or not api_key:
        raise IntegracaoError(
            'Redmine não configurado. Defina REDMINE_BASE_URL e REDMINE_API_KEY.'
        )
    return base_url, api_key


def _normalizar_quebras_linha(value: str) -> str:
    """Converte CRLF/CR do Redmine para LF antes de comparar/fingerprintar.

    Algumas instalações do Redmine persistem texto enviado com ``\n`` como
    ``\r\n``. Essa normalização é equivalente semanticamente e evita loop de
    reconciliação sem mascarar perda ou alteração de conteúdo.
    """
    return value.replace('\r\n', '\n').replace('\r', '\n')


def montar_campos_requisito_redmine(requisito: Any) -> dict[str, str]:
    urgencia_label = {'alta': 'Alta', 'media': 'Normal', 'baixa': 'Baixa'}.get(
        (getattr(requisito, 'urgencia', None) or 'media').lower(),
        'Normal',
    )
    descricao = (
        f"h2. {requisito.codigo} — {requisito.titulo}\n\n"
        f"*Sistema:* {requisito.sistema}\n"
        f"*Área:* {requisito.area}\n"
        f"*Solicitante:* {requisito.solicitante}\n"
        f"*Urgência:* {urgencia_label}\n"
        f"*Impacto Regulatório:* {'Sim' if requisito.impacto_regulatorio else 'Não'}\n\n"
        f"---\n\n"
        f"{requisito.descricao}"
    )
    return {
        'subject': f'[{requisito.codigo}] {requisito.titulo}',
        'description': descricao,
    }


def obter_issue_redmine(issue_id: int, *, incluir_journals: bool = True) -> dict[str, Any]:
    if issue_id <= 0:
        raise IntegracaoError('issue_id do Redmine deve ser maior que zero.')

    base_url, api_key = _redmine_config()
    suffix = '?include=journals' if incluir_journals else ''
    payload = _request_json(
        'GET',
        f'{base_url}/issues/{issue_id}.json{suffix}',
        headers={'X-Redmine-API-Key': api_key},
    )
    issue = payload.get('issue') if isinstance(payload, dict) else None
    if not isinstance(issue, dict):
        raise IntegracaoError(f'Redmine não retornou a issue {issue_id} no formato esperado.')

    description = issue.get('description')
    if isinstance(description, str):
        issue = dict(issue)
        issue['description'] = _normalizar_quebras_linha(description)
    return issue


def atualizar_issue_redmine(issue_id: int, campos: dict[str, Any]) -> dict[str, Any]:
    if issue_id <= 0:
        raise IntegracaoError('issue_id do Redmine deve ser maior que zero.')

    desconhecidos = sorted(set(campos) - _REQSYS_OWNED_FIELDS)
    if desconhecidos:
        raise IntegracaoError(
            'Escrita Redmine recusada para campos sem propriedade ReqSys: '
            + ', '.join(desconhecidos)
        )

    payload_campos = {
        chave: valor
        for chave, valor in campos.items()
        if chave in _REQSYS_OWNED_FIELDS and valor is not None
    }
    if not payload_campos:
        return {}

    base_url, api_key = _redmine_config()
    _request_json(
        'PUT',
        f'{base_url}/issues/{issue_id}.json',
        headers={'X-Redmine-API-Key': api_key},
        payload={'issue': payload_campos},
    )
    return payload_campos
