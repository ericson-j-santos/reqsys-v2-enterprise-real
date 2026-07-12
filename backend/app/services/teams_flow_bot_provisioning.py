"""Provisionamento programatico de flows do Power Automate para o canal flow_bot.

Dois mecanismos distintos, para dois problemas distintos — ver
docs/architecture/teams-messaging-gateway.md secao "Automacao":

- **Opcao A** (`clonar_flow_para_novo_dono` e afins): clona a definicao de um
  flow via Flow Management API bruta, gerando um flow IRMAO com um GUID novo.
  E o mecanismo certo para o caso real deste projeto — multiplos donos de
  backup coexistindo no MESMO ambiente (redundancia). Usa uma API que a
  Microsoft nao documenta publicamente como estavel para terceiros.
- **Opcao B** (`promover_flow_para_ambiente` e afins): usa Power Platform
  Solutions (`ExportSolution`/`ImportSolution`, 100% documentado no Dataverse
  Web API). Solutions casam componentes por "unique name" — importar a MESMA
  solution duas vezes no MESMO ambiente atualiza o flow existente, nao cria um
  irmao novo. Por isso a Opcao B NAO serve para o caso de multiplos donos; ela
  serve para **promover** um flow entre ambientes (dev → test → prod), que e
  um problema diferente.

Diferente de `power_automate_provisioning.py` (que so gera manifesto e despacha
um pipeline ALM externo — decisao deliberada do P0 para flows sem dependencia
de conexao de usuario, ver docs/integrations/power-automate/flow-provisioning-p0.md),
este modulo existe especificamente para o caso onde essa premissa nao se aplica:
o canal flow_bot depende do conector Teams, que exige uma conexao autorizada
interativamente por um humano — Microsoft nao oferece client-credentials para
esse conector (ver docs/architecture/teams-messaging-gateway.md). Em AMBAS as
opcoes, a conexao em si nunca pode ser criada via API — so vinculada depois de
o dono ja te-la autorizado interativamente.

Nao foi validado ao vivo: exige consentimento admin de escrita na Flow/Dataverse
API (hoje o app "ReqSys Enterprise" so tem uso comprovado de leitura, via
`listar_ambientes_power_automate` em hub_lowcode.py) e um flow/solution real ja
criado manualmente para servir de origem. Testado apenas com httpx mockado.
"""

from __future__ import annotations

import base64
import copy
import logging
import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.services.hub_lowcode import token_power_automate

logger = logging.getLogger('reqsys.teams_flow_bot_provisioning')

_PA_BASE = 'https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple'
_PA_API_VERSION = '2016-11-01'

_DATAVERSE_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
_DATAVERSE_API_VERSION = 'v9.2'


async def capturar_definicao_flow(environment: str, flow_id: str) -> dict[str, Any]:
    """Busca a definicao real (trigger + acoes + connectionReferences) de um flow existente.

    O flow de origem deve ter sido criado manualmente uma vez no Power Automate
    (ver docs/architecture/teams-messaging-gateway.md) — esta funcao so captura
    o JSON que a Microsoft realmente gerou, evitando que o ReqSys precise
    adivinhar o schema exato da acao "Post a message in a chat or channel".
    """
    token = await token_power_automate()
    url = f'{_PA_BASE}/environments/{environment}/flows/{flow_id}?api-version={_PA_API_VERSION}'
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers={'Authorization': f'Bearer {token}'})
        resp.raise_for_status()
        return resp.json()


def clonar_definicao_para_novo_dono(
    definicao_origem: dict[str, Any],
    nova_connection_id: str,
    novo_display_name: str,
    connection_reference_key: str | None = None,
) -> dict[str, Any]:
    """Clona a definicao de um flow trocando a connectionReference para um novo dono.

    `connection_reference_key` e a chave dentro de `properties.connectionReferences`
    que aponta pro conector Teams (tipicamente algo como 'shared_teams'); quando
    omitida, usa a unica/primeira chave encontrada — funciona para o flow_bot,
    que tem um unico conector.
    """
    clone = copy.deepcopy(definicao_origem)
    properties = clone.setdefault('properties', {})
    properties['displayName'] = novo_display_name

    connection_refs = properties.get('connectionReferences') or {}
    if not connection_refs:
        raise ValueError('definicao de origem nao tem connectionReferences; nao e um flow valido para clonar')

    chave = connection_reference_key or next(iter(connection_refs))
    if chave not in connection_refs:
        raise ValueError(f'connection_reference_key "{chave}" nao encontrada na definicao de origem')

    connection_refs[chave].setdefault('connection', {})['id'] = nova_connection_id
    properties['connectionReferences'] = connection_refs

    # campos somente-leitura que a API de criacao rejeita se reenviados
    clone.pop('id', None)
    clone.pop('name', None)
    properties.pop('createdTime', None)
    properties.pop('lastModifiedTime', None)
    properties.pop('flowSuspensionReason', None)
    properties['state'] = 'Started'

    return clone


async def criar_flow_a_partir_definicao(environment: str, flow_id: str, definicao: dict[str, Any]) -> dict[str, Any]:
    """Cria (ou atualiza, se `flow_id` ja existir) um flow via PUT na Flow API."""
    token = await token_power_automate()
    url = f'{_PA_BASE}/environments/{environment}/flows/{flow_id}?api-version={_PA_API_VERSION}'
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.put(url, json=definicao, headers={'Authorization': f'Bearer {token}'})
        resp.raise_for_status()
        return resp.json()


async def clonar_flow_para_novo_dono(
    environment: str,
    flow_id_origem: str,
    nova_connection_id: str,
    novo_display_name: str,
    connection_reference_key: str | None = None,
    novo_flow_id: str | None = None,
) -> dict[str, Any]:
    """Fluxo completo: captura a definicao de origem, clona para o novo dono e cria o flow.

    Pre-requisito manual e inevitavel: o novo dono precisa ter autorizado a
    propria conexao Teams uma vez no Power Automate (Microsoft nao permite
    client-credentials nesse conector) e voce informar o `connection_id` dela.
    """
    definicao_origem = await capturar_definicao_flow(environment, flow_id_origem)
    definicao_clonada = clonar_definicao_para_novo_dono(
        definicao_origem, nova_connection_id, novo_display_name, connection_reference_key
    )
    flow_id = novo_flow_id or str(uuid.uuid4())
    return await criar_flow_a_partir_definicao(environment, flow_id, definicao_clonada)


# ---------------------------------------------------------------------------
# Opcao B: promocao entre ambientes via Power Platform Solutions
# (Dataverse Web API — ExportSolution/ImportSolution/connectionreferences/workflows,
# 100% documentado; NAO serve para clonar donos de backup no mesmo ambiente,
# ver docstring do modulo)
# ---------------------------------------------------------------------------

def _normalizar_env_url(environment_url: str) -> str:
    return environment_url.rstrip('/') + '/'


async def _token_dataverse(environment_url: str) -> str:
    env_url = _normalizar_env_url(environment_url)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            _DATAVERSE_TOKEN_URL.format(tenant=settings.azure_tenant_id),
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.azure_client_id,
                'client_secret': settings.azure_client_secret,
                'scope': env_url + '.default',
            },
        )
        resp.raise_for_status()
        return resp.json()['access_token']


def _headers_dataverse(token: str) -> dict[str, str]:
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'OData-MaxVersion': '4.0',
        'OData-Version': '4.0',
        'Accept': 'application/json',
    }


async def exportar_solution(environment_url: str, solution_name: str, managed: bool = False) -> str:
    """Exporta uma Solution via Dataverse ExportSolution.

    `solution_name` e o nome interno/unico da solution (nao o display name).
    Retorna o ZIP em base64 — o mesmo formato do export manual pelo portal.
    """
    env_url = _normalizar_env_url(environment_url)
    token = await _token_dataverse(env_url)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/ExportSolution',
            json={'SolutionName': solution_name, 'Managed': managed},
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()
        return resp.json()['ExportSolutionFile']


async def importar_solution(
    environment_url: str,
    solution_zip_base64: str,
    overwrite_unmanaged_customizations: bool = False,
    publish_workflows: bool = True,
) -> dict[str, Any]:
    """Importa uma Solution no ambiente-alvo via Dataverse ImportSolution.

    A connectionReference dos conectores dependentes de usuario (Teams, etc.)
    chega SEM VINCULO apos o import — Microsoft confirma isso oficialmente
    ("connection references arrive unbound"). Use `vincular_connection_reference`
    em seguida.
    """
    base64.b64decode(solution_zip_base64, validate=True)
    env_url = _normalizar_env_url(environment_url)
    token = await _token_dataverse(env_url)
    import_job_id = str(uuid.uuid4())
    payload = {
        'CustomizationFile': solution_zip_base64,
        'OverwriteUnmanagedCustomizations': overwrite_unmanaged_customizations,
        'PublishWorkflows': publish_workflows,
        'ImportJobId': import_job_id,
    }
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/ImportSolution',
            json=payload,
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()
    return {'import_job_id': import_job_id, 'status_code': resp.status_code}


async def obter_connection_reference_id(environment_url: str, connection_reference_logical_name: str) -> str:
    """Busca o GUID (`connectionreferenceid`) de uma connectionReference pelo logical name."""
    env_url = _normalizar_env_url(environment_url)
    token = await _token_dataverse(env_url)
    filtro = f"connectionreferencelogicalname eq '{connection_reference_logical_name}'"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/connectionreferences',
            params={'$filter': filtro, '$select': 'connectionreferenceid'},
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()
        registros = resp.json().get('value') or []
    if not registros:
        raise ValueError(f'connectionreference nao encontrada: {connection_reference_logical_name}')
    return registros[0]['connectionreferenceid']


async def vincular_connection_reference(
    environment_url: str, connection_reference_logical_name: str, connection_id: str
) -> None:
    """Vincula uma conexao ja autorizada a uma connectionReference recem-importada.

    Pre-requisito manual e inevitavel: `connection_id` precisa ser de uma
    conexao Teams que o dono do ambiente-alvo ja autorizou interativamente —
    Microsoft nao permite criar isso via API.
    """
    env_url = _normalizar_env_url(environment_url)
    connection_reference_id = await obter_connection_reference_id(env_url, connection_reference_logical_name)
    token = await _token_dataverse(env_url)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/connectionreferences({connection_reference_id})',
            json={'connectionid': connection_id},
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()


async def obter_workflow_id_por_nome(environment_url: str, display_name: str) -> str:
    """Busca o GUID (`workflowid`) de um cloud flow (`category eq 5`) pelo nome."""
    env_url = _normalizar_env_url(environment_url)
    token = await _token_dataverse(env_url)
    filtro = f"name eq '{display_name}' and category eq 5"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/workflows',
            params={'$filter': filtro, '$select': 'workflowid'},
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()
        registros = resp.json().get('value') or []
    if not registros:
        raise ValueError(f'workflow (cloud flow) nao encontrado: {display_name}')
    return registros[0]['workflowid']


async def buscar_flows_por_nome(environment_url: str, contem: str) -> list[dict[str, Any]]:
    """Lista cloud flows (`category eq 5`) cujo nome contem `contem` (case-sensitive
    no Dataverse; ajuste o texto se nao encontrar nada).

    Existe especificamente para resolver ambiguidade quando ha varios flows com
    nomes parecidos (ex.: versoes/snapshots historicos no portal) — retorna
    `workflowid`, `name`, `statecode` (0=Draft/Off, 1=Activated/On) e
    `modifiedon` de cada um, pra decidir qual e o ativo/mais recente sem
    precisar adivinhar no portal.
    """
    env_url = _normalizar_env_url(environment_url)
    token = await _token_dataverse(env_url)
    filtro = f"contains(name, '{contem}') and category eq 5"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/workflows',
            params={
                '$filter': filtro,
                '$select': 'workflowid,name,statecode,statuscode,modifiedon',
                '$orderby': 'modifiedon desc',
            },
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()
        return resp.json().get('value') or []


async def obter_solution_id(environment_url: str, solution_name: str) -> str:
    """Busca o GUID (`solutionid`) de uma Solution pelo nome unico (nao o display name)."""
    env_url = _normalizar_env_url(environment_url)
    token = await _token_dataverse(env_url)
    filtro = f"uniquename eq '{solution_name}'"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/solutions',
            params={'$filter': filtro, '$select': 'solutionid'},
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()
        registros = resp.json().get('value') or []
    if not registros:
        raise ValueError(f'solution nao encontrada: {solution_name}')
    return registros[0]['solutionid']


async def listar_workflows_da_solution(environment_url: str, solution_name: str) -> list[dict[str, Any]]:
    """Lista os cloud flows (workflows) que estao DE FATO dentro de uma Solution.

    Responde com certeza a pergunta "qual desses flows parecidos e o que esta
    empacotado nesta solution", em vez de adivinhar pelo nome no portal —
    consulta `solutioncomponents` (componenttype 29 = Workflow) e resolve cada
    `objectid` na tabela `workflows`.
    """
    env_url = _normalizar_env_url(environment_url)
    solution_id = await obter_solution_id(env_url, solution_name)
    token = await _token_dataverse(env_url)
    filtro_componentes = f"_solutionid_value eq {solution_id} and componenttype eq 29"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/solutioncomponents',
            params={'$filter': filtro_componentes, '$select': 'objectid'},
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()
        component_ids = [r['objectid'] for r in (resp.json().get('value') or [])]

        if not component_ids:
            return []

        filtro_workflows = ' or '.join(f"workflowid eq {oid}" for oid in component_ids)
        resp = await client.get(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/workflows',
            params={'$filter': filtro_workflows, '$select': 'workflowid,name,statecode,statuscode,modifiedon'},
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()
        return resp.json().get('value') or []


async def ativar_flow(environment_url: str, workflow_id: str) -> None:
    """Ativa (liga) um cloud flow importado.

    `statecode=1`/`statuscode=2` seguem o padrao documentado da tabela
    `workflows` do Dataverse para "Activated" — nao validado ao vivo neste
    ambiente ainda.
    """
    env_url = _normalizar_env_url(environment_url)
    token = await _token_dataverse(env_url)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f'{env_url}api/data/{_DATAVERSE_API_VERSION}/workflows({workflow_id})',
            json={'statecode': 1, 'statuscode': 2},
            headers=_headers_dataverse(token),
        )
        resp.raise_for_status()


async def promover_flow_para_ambiente(
    environment_url_origem: str,
    environment_url_destino: str,
    solution_name: str,
    connection_reference_logical_name: str,
    connection_id_destino: str,
    novo_flow_display_name: str,
    managed: bool = False,
) -> dict[str, Any]:
    """Fluxo completo (Opcao B): exporta a Solution do ambiente de origem,
    importa no ambiente de destino, vincula a conexao ja autorizada la e
    ativa o flow.

    Nao cria donos irmaos no MESMO ambiente — para isso use
    `clonar_flow_para_novo_dono` (Opcao A). Esta funcao serve para promover
    (dev → test → prod), onde cada ambiente tem seu proprio dono/conexao.
    """
    solution_zip_base64 = await exportar_solution(environment_url_origem, solution_name, managed=managed)
    resultado_import = await importar_solution(environment_url_destino, solution_zip_base64)
    await vincular_connection_reference(
        environment_url_destino, connection_reference_logical_name, connection_id_destino
    )
    workflow_id = await obter_workflow_id_por_nome(environment_url_destino, novo_flow_display_name)
    await ativar_flow(environment_url_destino, workflow_id)
    return {**resultado_import, 'workflow_id': workflow_id, 'connection_vinculada': True, 'ativado': True}
