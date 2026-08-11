"""Adapter Dataverse (Web API OData) genérico para tabelas/filas customizadas.

Mesmo padrão de token client-credentials já usado em hub_lowcode.py
(`_token_dataverse`) e teams_flow_bot_provisioning.py, extraído aqui para uso
por qualquer feature que precise ler/escrever tabelas custom do Dataverse
(prefixo `cr85a_*`) sem repetir boilerplate de token/retry/circuit breaker
(ADR-001: adapters substituíveis; ADR-010: timeout + retry + circuit breaker
em toda chamada externa).

Não hardcoda nomes de "entity set" (a forma plural usada na URL OData) —
`resolver_entity_set_name` consulta a Metadata API real do Dataverse, porque
a pluralização de uma tabela custom pode ter sido customizada pelo maker e
adivinhar errado quebra silenciosamente em produção.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.resilience import CircuitBreaker, CircuitBreakerOpenError, call_with_retry_async

logger = logging.getLogger('reqsys.dataverse_queue_client')

_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
_API_VERSION = 'v9.2'
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 0.5
_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_COOLDOWN_SECONDS = 60

_circuits: dict[str, CircuitBreaker] = {}
_entity_set_cache: dict[str, str] = {}


class DataverseError(RuntimeError):
    pass


def dataverse_configurado() -> bool:
    return bool(settings.azure_tenant_id and settings.azure_client_id and settings.azure_client_secret)


def _circuit_for(environment_url: str) -> CircuitBreaker:
    if environment_url not in _circuits:
        _circuits[environment_url] = CircuitBreaker(
            name=f'dataverse_{environment_url}',
            failure_threshold=_CIRCUIT_FAILURE_THRESHOLD,
            cooldown_seconds=_CIRCUIT_COOLDOWN_SECONDS,
        )
    return _circuits[environment_url]


def reset_circuit_breakers() -> None:
    """Reseta todos os circuit breakers desta integração (uso em testes)."""
    for circuit in _circuits.values():
        circuit.reset()
    _entity_set_cache.clear()


async def _token(environment_url: str) -> str:
    scope = environment_url.rstrip('/') + '/.default'
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            _TOKEN_URL.format(tenant=settings.azure_tenant_id),
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.azure_client_id,
                'client_secret': settings.azure_client_secret,
                'scope': scope,
            },
        )
        resp.raise_for_status()
        return resp.json()['access_token']


async def _request(
    environment_url: str,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> httpx.Response:
    if not dataverse_configurado():
        raise DataverseError('Azure AD (AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET) não configurado')

    async def _do() -> httpx.Response:
        token = await _token(environment_url)
        headers = {
            'Authorization': f'Bearer {token}',
            'OData-MaxVersion': '4.0',
            'OData-Version': '4.0',
            'Accept': 'application/json',
        }
        if extra_headers:
            headers.update(extra_headers)
        url = f"{environment_url.rstrip('/')}/api/data/{_API_VERSION}/{path}"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.request(method, url, headers=headers, json=json_payload)
            if resp.status_code >= 400:
                detalhe = resp.text[:500]
                raise DataverseError(f'HTTP {resp.status_code} em {path}: {detalhe}')
            return resp

    try:
        return await call_with_retry_async(
            _do,
            max_retries=_MAX_RETRIES,
            backoff_seconds=_RETRY_BACKOFF_SECONDS,
            retry_on=(httpx.TransportError,),
            circuit=_circuit_for(environment_url),
        )
    except CircuitBreakerOpenError as exc:
        raise DataverseError(str(exc)) from exc
    except httpx.TransportError as exc:
        raise DataverseError(f'Falha de rede no Dataverse: {exc}') from exc


async def resolver_entity_set_name(environment_url: str, logical_name: str) -> str:
    """Resolve o nome real do entity set (forma plural na URL OData) de uma
    tabela pelo LogicalName — nunca adivinha (ex.: 's' vs 'es' vs plural custom)."""
    cache_key = f'{environment_url}:{logical_name}'
    if cache_key in _entity_set_cache:
        return _entity_set_cache[cache_key]
    resp = await _request(environment_url, 'GET', f"EntityDefinitions(LogicalName='{logical_name}')?$select=EntitySetName")
    entity_set = resp.json().get('EntitySetName')
    if not entity_set:
        raise DataverseError(f"Não foi possível resolver EntitySetName para '{logical_name}'")
    _entity_set_cache[cache_key] = entity_set
    return entity_set


async def list_rows(
    environment_url: str,
    entity_set: str,
    *,
    filtro: str | None = None,
    select: list[str] | None = None,
    top: int = 50,
    orderby: str | None = None,
) -> list[dict[str, Any]]:
    params = []
    if filtro:
        params.append(f'$filter={filtro}')
    if select:
        params.append(f'$select={",".join(select)}')
    if orderby:
        params.append(f'$orderby={orderby}')
    params.append(f'$top={max(1, min(top, 500))}')
    path = f'{entity_set}?{"&".join(params)}'
    resp = await _request(environment_url, 'GET', path)
    return resp.json().get('value', [])


async def update_row(environment_url: str, entity_set: str, row_id: str, campos: dict[str, Any]) -> None:
    await _request(environment_url, 'PATCH', f'{entity_set}({row_id})', json_payload=campos)


async def create_row(environment_url: str, entity_set: str, campos: dict[str, Any]) -> dict[str, Any]:
    """Cria uma linha e devolve o corpo completo criado (inclui a coluna
    `<logicalname>id` — convenção fixa da plataforma Dataverse, não
    customizável, então o chamador que conhece o schema da tabela lê o campo
    exato que precisa em vez de este módulo tentar adivinhar)."""
    resp = await _request(
        environment_url, 'POST', entity_set, json_payload=campos,
        extra_headers={'Prefer': 'return=representation'},
    )
    return resp.json()


async def testar_autenticacao(environment_url: str) -> str:
    """Testa a aquisição de token client-credentials contra este ambiente —
    usado por scripts de diagnóstico para confirmar AZURE_TENANT_ID/
    AZURE_CLIENT_ID/AZURE_CLIENT_SECRET antes de qualquer chamada real."""
    return await _token(environment_url)


async def verificar_application_user(environment_url: str, client_id: str) -> dict[str, Any]:
    """Confirma se o app (`client_id`) tem um Dataverse Application User neste
    ambiente — pré-requisito documentado para qualquer chamada Web API (ver
    docs/architecture/teams-messaging-gateway.md, seção de permissões)."""
    path = f"systemusers?$filter=applicationid eq '{client_id}'&$select=systemuserid,fullname"
    resp = await _request(environment_url, 'GET', path)
    itens = resp.json().get('value', [])
    return {'existe': bool(itens), 'systemuserid': itens[0]['systemuserid'] if itens else None}


async def listar_colunas(environment_url: str, tabela_logical_name: str) -> list[dict[str, Any]]:
    """Lista todas as colunas (`LogicalName` + `AttributeType`) de uma tabela —
    permite comparar o schema assumido no código contra o real de uma vez,
    em vez de checar coluna por coluna via `metadados_coluna`."""
    path = f"EntityDefinitions(LogicalName='{tabela_logical_name}')/Attributes?$select=LogicalName,AttributeType"
    resp = await _request(environment_url, 'GET', path)
    return resp.json().get('value', [])


async def metadados_coluna(environment_url: str, tabela_logical_name: str, coluna_logical_name: str) -> dict[str, Any]:
    """Consulta a definição real da coluna (tipo + tamanho máximo) via
    Dataverse Metadata API — automatiza o diagnóstico de erros como
    'String or binary data would be truncated' sem abrir o Maker Portal
    manualmente (ver docs/architecture/redmine-sync-queue.md)."""
    path = (
        f"EntityDefinitions(LogicalName='{tabela_logical_name}')/Attributes(LogicalName='{coluna_logical_name}')"
        f"?$select=AttributeType,LogicalName"
    )
    resp = await _request(environment_url, 'GET', path)
    base = resp.json()
    tipo = base.get('AttributeType')
    max_length = None
    if tipo in ('String', 'Memo'):
        cast = 'StringAttributeMetadata' if tipo == 'String' else 'MemoAttributeMetadata'
        path_detalhe = (
            f"EntityDefinitions(LogicalName='{tabela_logical_name}')/Attributes(LogicalName='{coluna_logical_name}')"
            f"/Microsoft.Dynamics.CRM.{cast}?$select=MaxLength"
        )
        resp2 = await _request(environment_url, 'GET', path_detalhe)
        max_length = resp2.json().get('MaxLength')
    return {'logical_name': coluna_logical_name, 'attribute_type': tipo, 'max_length': max_length}
