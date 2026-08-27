from __future__ import annotations

from typing import Any

import httpx

from app.services.copilot_memory_install_assistant import (
    _credenciais_microsoft_configuradas,
    _token,
)

_GRAPH_BASE = 'https://graph.microsoft.com/v1.0'


async def listar_grupos_instalacao() -> dict[str, Any]:
    """Lista grupos Microsoft 365 para evitar exigir Group ID do usuário."""
    if not _credenciais_microsoft_configuradas():
        return {'configurado': False, 'grupos': [], 'erro': 'Credenciais Microsoft Entra não configuradas'}
    try:
        token = await _token('https://graph.microsoft.com/.default')
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f'{_GRAPH_BASE}/groups',
                headers={'Authorization': f'Bearer {token}'},
                params={'$select': 'id,displayName,groupTypes,mail', '$top': 100},
            )
            response.raise_for_status()
        grupos = []
        for item in response.json().get('value', []):
            if 'Unified' not in (item.get('groupTypes') or []):
                continue
            grupos.append(
                {
                    'id': item.get('id'),
                    'nome': item.get('displayName') or item.get('mail') or item.get('id'),
                    'email': item.get('mail') or '',
                }
            )
        grupos.sort(key=lambda item: str(item['nome']).lower())
        return {'configurado': True, 'grupos': grupos, 'erro': None}
    except Exception as exc:
        return {'configurado': True, 'grupos': [], 'erro': str(exc)}
