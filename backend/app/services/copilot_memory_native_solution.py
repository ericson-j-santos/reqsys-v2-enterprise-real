from __future__ import annotations

import json
import re
import uuid
import zipfile
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

SOLUTION_UNIQUE_NAME = 'CopilotMemoryInstaller'
SOLUTION_VERSION = '1.2.0.0'
PLANNER_CONNECTION_LOGICAL_NAME = 'reqsys_sharedplanner_copilotmemory'
EXCEL_CONNECTION_LOGICAL_NAME = 'reqsys_sharedexcel_copilotmemory'

_CONNECTIONS = {
    'shared_planner': {
        'logical_name': PLANNER_CONNECTION_LOGICAL_NAME,
        'display_name': 'Copilot Memory - Planner',
        'connector_id': '/providers/Microsoft.PowerApps/apis/shared_planner',
    },
    'shared_excelonlinebusiness': {
        'logical_name': EXCEL_CONNECTION_LOGICAL_NAME,
        'display_name': 'Copilot Memory - Excel Online Business',
        'connector_id': '/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness',
    },
}

_CONTENT_TYPES = '''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/octet-stream" />
  <Default Extension="json" ContentType="application/octet-stream" />
</Types>
'''


def _flow_guid(flow_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'copilot-memory:{flow_id}'))


def _safe_flow_name(display_name: str) -> str:
    safe = re.sub(r'[^A-Za-z0-9-]', '', display_name.replace(' ', '-'))
    return safe or 'CopilotMemoryFlow'


def _used_connections(definition: dict[str, Any]) -> dict[str, dict[str, str]]:
    serialized = json.dumps(definition, ensure_ascii=False)
    used: dict[str, dict[str, str]] = {}
    for key, meta in _CONNECTIONS.items():
        if key in serialized:
            used[key] = meta
    return used


def _flow_wrapper(flow: dict[str, Any]) -> dict[str, Any]:
    references: dict[str, Any] = {}
    for key, meta in _used_connections(flow['definition']).items():
        references[key] = {
            'runtimeSource': 'embedded',
            'connection': {
                'connectionReferenceLogicalName': meta['logical_name'],
            },
            'api': {'name': key},
        }
    return {
        'properties': {
            'connectionReferences': references,
            'definition': flow['definition'],
            'templateName': None,
        },
        'schemaVersion': '1.0.0.0',
    }


def _workflow_xml(flow: dict[str, Any], filename: str) -> str:
    guid = _flow_guid(flow['id'])
    name = escape(flow['display_name'])
    return f'''    <Workflow WorkflowId="{{{guid}}}" Name="{name}">
      <JsonFileName>/Workflows/{escape(filename)}</JsonFileName>
      <Type>1</Type>
      <Subprocess>0</Subprocess>
      <Category>5</Category>
      <Mode>0</Mode>
      <Scope>4</Scope>
      <OnDemand>0</OnDemand>
      <TriggerOnCreate>0</TriggerOnCreate>
      <TriggerOnDelete>0</TriggerOnDelete>
      <AsyncAutodelete>0</AsyncAutodelete>
      <SyncWorkflowLogOnFailure>0</SyncWorkflowLogOnFailure>
      <StateCode>0</StateCode>
      <StatusCode>1</StatusCode>
      <RunAs>1</RunAs>
      <IsTransacted>1</IsTransacted>
      <IntroducedVersion>{SOLUTION_VERSION}</IntroducedVersion>
      <IsCustomizable>1</IsCustomizable>
      <BusinessProcessType>0</BusinessProcessType>
      <IsCustomProcessingStepAllowedForOtherPublishers>1</IsCustomProcessingStepAllowedForOtherPublishers>
      <ModernFlowType>0</ModernFlowType>
      <PrimaryEntity>none</PrimaryEntity>
      <LocalizedNames>
        <LocalizedName languagecode="1046" description="{name}" />
      </LocalizedNames>
    </Workflow>'''


def _customizations_xml(flows: list[dict[str, Any]]) -> str:
    workflows: list[str] = []
    for flow in flows:
        guid = _flow_guid(flow['id']).upper()
        filename = f"{_safe_flow_name(flow['display_name'])}-{guid}.json"
        workflows.append(_workflow_xml(flow, filename))

    refs = []
    for meta in _CONNECTIONS.values():
        refs.append(
            f'''    <connectionreference connectionreferencelogicalname="{meta['logical_name']}">
      <connectionreferencedisplayname>{escape(meta['display_name'])}</connectionreferencedisplayname>
      <connectorid>{escape(meta['connector_id'])}</connectorid>
      <iscustomizable>1</iscustomizable>
      <promptingbehavior>0</promptingbehavior>
      <statecode>0</statecode>
      <statuscode>1</statuscode>
    </connectionreference>'''
        )

    return f'''<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Entities />
  <Roles />
  <Workflows>
{chr(10).join(workflows)}
  </Workflows>
  <FieldSecurityProfiles />
  <Templates />
  <EntityMaps />
  <EntityRelationships />
  <OrganizationSettings />
  <optionsets />
  <CustomControls />
  <EntityDataProviders />
  <connectionreferences>
{chr(10).join(refs)}
  </connectionreferences>
  <Languages>
    <Language>1046</Language>
  </Languages>
</ImportExportXml>
'''


def _solution_xml(flows: list[dict[str, Any]]) -> str:
    components = '\n'.join(
        f'      <RootComponent type="29" id="{{{_flow_guid(flow["id"])}}}" behavior="0" />'
        for flow in flows
    )
    return f'''<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml version="9.2.0.0" SolutionPackageVersion="9.2" languagecode="1046" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <SolutionManifest>
    <UniqueName>{SOLUTION_UNIQUE_NAME}</UniqueName>
    <LocalizedNames>
      <LocalizedName description="Copilot Memory Installer" languagecode="1046" />
    </LocalizedNames>
    <Descriptions>
      <Description description="Tres fluxos Copilot Memory para Planner e Excel, gerados pelo ReqSys" languagecode="1046" />
    </Descriptions>
    <Version>{SOLUTION_VERSION}</Version>
    <Managed>0</Managed>
    <Publisher>
      <UniqueName>reqsys</UniqueName>
      <LocalizedNames>
        <LocalizedName description="ReqSys" languagecode="1046" />
      </LocalizedNames>
      <Descriptions />
      <EMailAddress xsi:nil="true" />
      <SupportingWebsiteUrl xsi:nil="true" />
      <CustomizationPrefix>reqsys</CustomizationPrefix>
      <CustomizationOptionValuePrefix>10000</CustomizationOptionValuePrefix>
      <Addresses />
    </Publisher>
    <RootComponents>
{components}
    </RootComponents>
    <MissingDependencies />
  </SolutionManifest>
</ImportExportXml>
'''


def gerar_solution_power_platform_importavel(flows: list[dict[str, Any]]) -> bytes:
    if len(flows) != 3:
        raise ValueError(f'Esperados 3 fluxos; recebidos {len(flows)}')

    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr('[Content_Types].xml', _CONTENT_TYPES)
        archive.writestr('solution.xml', _solution_xml(flows))
        archive.writestr('customizations.xml', _customizations_xml(flows))
        for flow in flows:
            guid = _flow_guid(flow['id']).upper()
            filename = f"{_safe_flow_name(flow['display_name'])}-{guid}.json"
            archive.writestr(
                f'Workflows/{filename}',
                json.dumps(_flow_wrapper(flow), ensure_ascii=False, indent=2),
            )
    payload = output.getvalue()
    validation = validar_solution_power_platform_importavel(payload)
    if not validation['ok']:
        raise ValueError(f"Solution Power Platform invalida: {validation['errors']}")
    return payload


def validar_solution_power_platform_importavel(payload: bytes) -> dict[str, Any]:
    errors: list[str] = []
    if not zipfile.is_zipfile(BytesIO(payload)):
        return {'ok': False, 'errors': ['arquivo nao e ZIP'], 'flows': 0, 'connections': 0}

    with zipfile.ZipFile(BytesIO(payload)) as archive:
        names = set(archive.namelist())
        required = {'[Content_Types].xml', 'solution.xml', 'customizations.xml'}
        missing = sorted(required - names)
        if missing:
            errors.append(f"arquivos raiz ausentes: {', '.join(missing)}")

        workflow_files = sorted(
            name for name in names if name.startswith('Workflows/') and name.endswith('.json')
        )
        if len(workflow_files) != 3:
            errors.append(f'esperados 3 JSONs de fluxo; encontrados {len(workflow_files)}')

        if not missing:
            try:
                solution_text = archive.read('solution.xml').decode('utf-8')
                custom_text = archive.read('customizations.xml').decode('utf-8')
            except UnicodeDecodeError as exc:
                errors.append(f'XML nao esta em UTF-8 valido: {exc}')
            else:
                root_components = solution_text.count('<RootComponent type="29"')
                if root_components != 3:
                    errors.append(f'esperados 3 RootComponents de fluxo; encontrados {root_components}')
                workflows = custom_text.count('<Workflow WorkflowId=')
                if workflows != 3:
                    errors.append(f'esperados 3 Workflows no customizations; encontrados {workflows}')
                logical_names = set(
                    re.findall(
                        r'<connectionreference connectionreferencelogicalname="([A-Za-z0-9_]+)"',
                        custom_text,
                    )
                )
                expected = {PLANNER_CONNECTION_LOGICAL_NAME, EXCEL_CONNECTION_LOGICAL_NAME}
                if logical_names != expected:
                    errors.append('referencias de conexao Planner/Excel incompletas')

        for path in workflow_files:
            try:
                wrapper = json.loads(archive.read(path))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors.append(f'{path}: JSON invalido: {exc}')
                continue
            properties = wrapper.get('properties') or {}
            if not properties.get('definition'):
                errors.append(f'{path}: definition ausente')
            refs = properties.get('connectionReferences') or {}
            for key, ref in refs.items():
                logical = (ref.get('connection') or {}).get('connectionReferenceLogicalName')
                if key not in _CONNECTIONS or logical != _CONNECTIONS[key]['logical_name']:
                    errors.append(f'{path}: referencia de conexao invalida para {key}')

    return {
        'ok': not errors,
        'errors': errors,
        'flows': 3 if not errors else len(workflow_files),
        'connections': 2 if not errors else 0,
        'solution_name': SOLUTION_UNIQUE_NAME,
        'solution_version': SOLUTION_VERSION,
    }
