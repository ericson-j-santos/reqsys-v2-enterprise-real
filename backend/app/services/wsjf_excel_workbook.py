"""Diagnostico e reparo do WSJF.xlsx que ja esta no tenant.

O gerador de planilha do ReqSys foi corrigido, mas isso nao conserta o arquivo
que ja existe no SharePoint do grupo: enquanto ele continuar recusado pelo motor
Excel do Microsoft Graph, o fluxo Planner -> Excel falha em execucao com
unsupportedWorkbook / FileCorruptTryRepair. Estas funcoes deixam esse estado
visivel no instalador e permitem substituir o arquivo preservando os dados.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.copilot_memory_install_assistant import _GRAPH_BASE, _token
from wsjf_workbook_package import (
    TABELA,
    erro_graph_indica_workbook_incompativel,
    reparar_workbook_wsjf,
    validar_workbook_wsjf,
)

# Sem '%': um id com escape percentual poderia virar '../' depois de decodificado
# pelo Graph. Ids reais de drive e item usam apenas base64url mais '!'.
_CARACTERES_PERMITIDOS = set(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!()+,-.@^_~'
)


def _identificador_graph_seguro(value: str, label: str) -> str:
    """Impede que um id vindo do cliente vire travessia de caminho no Graph.

    Ids de drive e de item nao sao GUIDs (`b!...`, `01ABC...`), entao o
    validador de GUID usado no resto do modulo nao serve aqui.

    Exigir inicio alfanumerico nao e cosmetico: `.` esta na lista de
    caracteres permitidos (ids reais o usam), e um id igual a `..` seria
    normalizado pelo httpx como segmento de caminho —
    `/v1.0/drives/../items/{id}` vira `/v1.0/items/{id}`, ou seja, outro
    endpoint do Graph. Todo id real comeca por letra ou digito.
    """
    normalized = (value or '').strip()
    if not normalized:
        raise ValueError(f'{label} obrigatorio')
    if not normalized[0].isalnum() or not set(normalized).issubset(_CARACTERES_PERMITIDOS):
        raise ValueError(f'{label} invalido')
    return normalized


async def _metadados(client: httpx.AsyncClient, headers: dict[str, str], drive: str, item: str) -> dict[str, Any]:
    response = await client.get(
        f'{_GRAPH_BASE}/drives/{drive}/items/{item}',
        headers=headers,
        params={'$select': 'id,name,size,webUrl,lastModifiedDateTime,parentReference'},
    )
    response.raise_for_status()
    return response.json()


async def _workbook_legivel(
    client: httpx.AsyncClient, headers: dict[str, str], drive: str, item: str
) -> dict[str, Any]:
    """Consulta o motor Excel do Graph — o mesmo que o conector usa no fluxo."""
    response = await client.get(
        f'{_GRAPH_BASE}/drives/{drive}/items/{item}/workbook/worksheets', headers=headers
    )
    if response.status_code < 400:
        return {'graph_ok': True, 'graph_recusou_arquivo': False, 'graph_erro': None}
    try:
        payload: Any = response.json()
    except ValueError:
        payload = response.text
    return {
        'graph_ok': False,
        'graph_recusou_arquivo': erro_graph_indica_workbook_incompativel(payload),
        'graph_erro': f'HTTP {response.status_code}: {str(payload)[:300]}',
    }


async def diagnosticar_workbook(drive_id: str, file_id: str) -> dict[str, Any]:
    """Diz se o WSJF.xlsx do tenant seria aceito pelo fluxo, e por que nao."""
    drive = _identificador_graph_seguro(drive_id, 'Drive')
    item = _identificador_graph_seguro(file_id, 'Arquivo')
    token = await _token('https://graph.microsoft.com/.default')
    headers = {'Authorization': f'Bearer {token}'}
    async with httpx.AsyncClient(timeout=60) as client:
        metadados = await _metadados(client, headers, drive, item)
        conteudo = await client.get(f'{_GRAPH_BASE}/drives/{drive}/items/{item}/content', headers=headers)
        conteudo.raise_for_status()
        pacote = validar_workbook_wsjf(conteudo.content)
        graph = await _workbook_legivel(client, headers, drive, item)
    compativel = bool(pacote['ok'] and graph['graph_ok'])
    return {
        'compativel': compativel,
        'precisa_reparo': not compativel and (not pacote['ok'] or graph['graph_recusou_arquivo']),
        'pacote_ok': pacote['ok'],
        'erros_pacote': pacote['erros'],
        'tabela_esperada': TABELA,
        'tabelas': pacote['tabelas'],
        'arquivo': {
            'id': metadados.get('id'),
            'nome': metadados.get('name'),
            'web_url': metadados.get('webUrl'),
            'alterado_em': metadados.get('lastModifiedDateTime'),
        },
        **graph,
    }


async def reparar_workbook_do_tenant(drive_id: str, file_id: str) -> dict[str, Any]:
    """Substitui o WSJF.xlsx recusado pelo Graph, preservando o que for legivel.

    O arquivo recusado e guardado ao lado antes da troca e o conteudo novo e
    gravado no mesmo item, preservando o id — o fluxo ja instalado continua
    apontando para o arquivo certo.
    """
    drive = _identificador_graph_seguro(drive_id, 'Drive')
    item = _identificador_graph_seguro(file_id, 'Arquivo')
    token = await _token('https://graph.microsoft.com/.default')
    headers = {'Authorization': f'Bearer {token}'}
    binario = {**headers, 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    carimbo = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = f'WSJF.incompativel-{carimbo}.xlsx'

    async with httpx.AsyncClient(timeout=120) as client:
        metadados = await _metadados(client, headers, drive, item)
        pasta = str((metadados.get('parentReference') or {}).get('id') or '')
        if not pasta:
            raise ValueError('Nao foi possivel identificar a pasta do WSJF.xlsx para guardar a copia de seguranca')
        atual = await client.get(f'{_GRAPH_BASE}/drives/{drive}/items/{item}/content', headers=headers)
        atual.raise_for_status()

        reparo = reparar_workbook_wsjf(atual.content)
        validacao = validar_workbook_wsjf(reparo['conteudo'])
        if not validacao['ok']:
            raise ValueError(f"Conteudo de substituicao invalido: {validacao['erros']}")

        copia = await client.put(
            f'{_GRAPH_BASE}/drives/{drive}/items/{pasta}:/{backup}:/content',
            headers=binario,
            content=atual.content,
        )
        copia.raise_for_status()
        enviado = await client.put(
            f'{_GRAPH_BASE}/drives/{drive}/items/{item}/content',
            headers=binario,
            content=reparo['conteudo'],
        )
        enviado.raise_for_status()
        graph = await _workbook_legivel(client, headers, drive, item)

    return {
        'reparado': bool(graph['graph_ok']),
        'estrategia': reparo['estrategia'],
        'linhas_preservadas': reparo['linhas_preservadas'],
        'avisos': reparo['avisos'],
        'copia_de_seguranca': backup,
        'arquivo': {'id': metadados.get('id'), 'nome': metadados.get('name'), 'web_url': metadados.get('webUrl')},
        **graph,
    }
