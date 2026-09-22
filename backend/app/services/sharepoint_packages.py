from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.identity_governance import IdentityGovernanceError
from app.services.sharepoint_graph_identity import acquire_sharepoint_graph_token

logger = logging.getLogger('reqsys.sharepoint_packages')

_GRAPH_BASE = 'https://graph.microsoft.com/v1.0'


async def listar_pacotes_ia_governado(limit: int = 20) -> dict[str, Any]:
    if not settings.sharepoint_site_id:
        return {
            'configurado': False,
            'itens': [],
            'erro': 'SHAREPOINT_SITE_ID não configurado',
            'identidade': None,
        }

    try:
        token, identity = await acquire_sharepoint_graph_token()
        url = (
            f'{_GRAPH_BASE}/sites/{settings.sharepoint_site_id}'
            f'/lists/{settings.sharepoint_list_ia}/items'
            f'?$expand=fields'
            f'&$orderby=lastModifiedDateTime desc'
            f'&$top={limit}'
        )
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, headers={'Authorization': f'Bearer {token}'})
            response.raise_for_status()
            raw = response.json().get('value', [])

        itens = []
        for item in raw:
            fields = item.get('fields', {})
            itens.append({
                'id': item.get('id'),
                'projeto': fields.get('Projeto', ''),
                'branch': fields.get('Branch', ''),
                'commit': (fields.get('CommitHash') or '')[:12],
                'tech_stack': fields.get('TechStack', ''),
                'total_arquivos': fields.get('TotalArquivos', 0),
                'tamanho_mb': fields.get('TamanhoPacoteMb', 0),
                'status': fields.get('Status', ''),
                'chave': fields.get('ChaveIdempotencia', ''),
                'gerado_em': fields.get('DataGeracaoUtc', ''),
                'processado_em': fields.get('ProcessadoEmUtc', ''),
            })

        return {
            'configurado': True,
            'itens': itens,
            'erro': None,
            'identidade': identity.evidence(),
        }

    except IdentityGovernanceError as exc:
        logger.warning('sharepoint_packages: identidade governada bloqueou leitura: %s', exc)
        return {
            'configurado': False,
            'itens': [],
            'erro': str(exc),
            'identidade': None,
        }
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning('sharepoint_packages: falha ao ler catálogo SharePoint: %s', exc)
        return {
            'configurado': True,
            'itens': [],
            'erro': str(exc),
            'identidade': None,
        }
