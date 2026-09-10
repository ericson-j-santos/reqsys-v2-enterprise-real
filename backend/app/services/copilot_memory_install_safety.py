from __future__ import annotations

from typing import Any

import httpx

from app.services.copilot_memory_install_assistant import listar_ambientes_instalacao

_PRODUCAO = {'production', 'prod', 'producao', 'produção'}
_POWER_PLATFORM_BASE = 'https://api.powerplatform.com'


def _parece_producao(ambiente: dict[str, Any]) -> bool:
    valores = {
        str(ambiente.get('tipo') or '').strip().lower(),
        str(ambiente.get('nome') or '').strip().lower(),
    }
    if valores.intersection(_PRODUCAO):
        return True
    nome = str(ambiente.get('nome') or '').strip().lower()
    return nome.startswith('prod-') or nome.endswith('-prod') or ' produção' in nome or ' production' in nome


async def _listar_ambientes_delegado(user_token: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f'{_POWER_PLATFORM_BASE}/environmentmanagement/environments?api-version=2024-10-01',
                headers={'Authorization': f'Bearer {user_token}'},
            )
            response.raise_for_status()
        ambientes = []
        for item in response.json().get('value', []):
            props = item.get('properties') or {}
            linked = props.get('linkedEnvironmentMetadata') or {}
            ambientes.append(
                {
                    'id': item.get('id') or item.get('name') or props.get('environmentId'),
                    'nome': item.get('displayName') or props.get('displayName') or linked.get('instanceName') or item.get('name'),
                    'url': item.get('url') or props.get('environmentUrl') or linked.get('instanceUrl') or linked.get('instanceApiUrl') or '',
                    'estado': item.get('state') or props.get('provisioningState') or '',
                    'tipo': item.get('type') or props.get('environmentSku') or props.get('environmentType') or '',
                    'regiao': item.get('geo') or item.get('azureRegion') or props.get('azureRegion') or '',
                }
            )
        return {'configurado': True, 'ambientes': ambientes, 'erro': None}
    except Exception as exc:
        return {'configurado': True, 'ambientes': [], 'erro': str(exc)}


async def validar_destino_assistente(
    environment_id: str,
    environment_url: str,
    user_token: str | None = None,
) -> dict[str, Any]:
    """Relê o ambiente na Microsoft e bloqueia produção antes de qualquer implantação.

    Quando há token delegado, a confirmação usa a identidade do próprio usuário,
    evitando depender de permissões app-only que não enxergam todos os ambientes.
    Sem token delegado, preserva o comportamento anterior.
    """
    resultado = (
        await _listar_ambientes_delegado(user_token)
        if user_token
        else await listar_ambientes_instalacao()
    )
    if resultado.get('erro'):
        raise ValueError(f"Nao foi possivel confirmar o ambiente Microsoft: {resultado['erro']}")

    ambiente = next(
        (item for item in resultado.get('ambientes', []) if str(item.get('id')) == str(environment_id)),
        None,
    )
    if ambiente is None:
        raise ValueError('Ambiente selecionado nao foi encontrado novamente na Microsoft')

    url_oficial = str(ambiente.get('url') or '').rstrip('/').lower()
    url_recebida = str(environment_url or '').rstrip('/').lower()
    if not url_oficial or url_oficial != url_recebida:
        raise ValueError('URL do ambiente diverge da fonte oficial Microsoft')
    if _parece_producao(ambiente):
        raise ValueError('O assistente Copilot Memory nao permite implantacao direta em producao')

    return ambiente
