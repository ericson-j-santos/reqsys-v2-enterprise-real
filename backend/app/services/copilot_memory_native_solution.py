from __future__ import annotations

import base64
import hashlib
import json
import re
import uuid
import zipfile
from html import escape
from io import BytesIO
from typing import Any

from copilot_memory_powerautomate_complete import gerar_fluxos_completos, validar_definicao

SOLUTION_NAME = 'CopilotMemoryInstaller'
SOLUTION_FILENAME = f'{SOLUTION_NAME}.zip'
PLANNER_REFERENCE = 'reqsys_sharedplanner_copilotmemory'
EXCEL_REFERENCE = 'reqsys_sharedexcel_copilotmemory'


def _safe_filename(value: str) -> str:
    normalized = re.sub(r'[^A-Za-z0-9-]+', '', value)
    return normalized or 'CopilotMemoryFlow'


def _flow_guid(flow_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'copilot-memory:{flow_id}'))


def _wrapper(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        'properties': {
            'connectionReferences': {
                'shared_planner': {
                    'runtimeSource': 'invoker',
                    'connection': {'connectionReferenceLogicalName': PLANNER_REFERENCE},
                    'api': {'name': 'shared_planner'},
                },
                'shared_excelonlinebusiness': {
                    'runtimeSource': 'invoker',
                    'connection': {'connectionReferenceLogicalName': EXCEL_REFERENCE},
                    'api': {'name': 'shared_excelonlinebusiness'},
                },
            },
            'definition': definition,
            'templateName': None,
        },
        'schemaVersion': '1.0.0.0',
    }


def _workflow_xml(flow_guid: str, display_name: str, json_filename: str) -> str:
    guid = flow_guid.lower()
    name = escape(display_name, quote=True)
    json_name = escape(json_filename)
    return f'''  <Workflow WorkflowId="{{{guid}}}" Name="{name}">
    <JsonFileName>/Workflows/{json_name}</JsonFileName>
    <Type>1</Type><Subprocess>0</Subprocess><Category>5</Category><Mode>0</Mode><Scope>4</Scope>
    <OnDemand>0</OnDemand><TriggerOnCreate>0</TriggerOnCreate><TriggerOnDelete>0</TriggerOnDelete>
    <AsyncAutodelete>0</AsyncAutodelete><SyncWorkflowLogOnFailure>0</SyncWorkflowLogOnFailure>
    <StateCode>1</StateCode><StatusCode>2</StatusCode><RunAs>1</RunAs><IsTransacted>1</IsTransacted>
    <IntroducedVersion>1.0.0.0</IntroducedVersion><IsCustomizable>1</IsCustomizable>
    <BusinessProcessType>0</BusinessProcessType>
    <IsCustomProcessingStepAllowedForOtherPublishers>1</IsCustomProcessingStepAllowedForOtherPublishers>
    <PrimaryEntity>none</PrimaryEntity>
    <LocalizedNames><LocalizedName languagecode="1046" description="{name}" /></LocalizedNames>
  </Workflow>'''


def _connection_reference_xml(logical_name: str, display_name: str, connector: str) -> str:
    return f'''  <connectionreference connectionreferencelogicalname="{escape(logical_name, quote=True)}">
    <connectionreferencedisplayname>{escape(display_name)}</connectionreferencedisplayname>
    <connectorid>/providers/Microsoft.PowerApps/apis/{escape(connector)}</connectorid>
    <iscustomizable>1</iscustomizable><statecode>0</statecode><statuscode>1</statuscode>
  </connectionreference>'''


def _solution_xml(flows: list[dict[str, Any]]) -> str:
    roots = '\n'.join(
        f'      <RootComponent type="29" id="{{{item["guid"].lower()}}}" behavior="0" />'
        for item in flows
    )
    return f'''<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml version="9.2.0.0" SolutionPackageVersion="9.2" languagecode="1046" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <SolutionManifest>
    <UniqueName>{SOLUTION_NAME}</UniqueName>
    <LocalizedNames><LocalizedName description="Copilot Memory Installer" languagecode="1046" /></LocalizedNames>
    <Descriptions><Description description="Copilot Memory: 3 fluxos portáteis gerados pelo ReqSys" languagecode="1046" /></Descriptions>
    <Version>1.1.0.0</Version><Managed>0</Managed>
    <Publisher>
      <UniqueName>reqsys</UniqueName>
      <LocalizedNames><LocalizedName description="ReqSys" languagecode="1046" /></LocalizedNames>
      <Descriptions /><EMailAddress xsi:nil="true" /><SupportingWebsiteUrl xsi:nil="true" />
      <CustomizationPrefix>reqsys</CustomizationPrefix><CustomizationOptionValuePrefix>10000</CustomizationOptionValuePrefix><Addresses />
    </Publisher>
    <RootComponents>
{roots}
    </RootComponents>
    <MissingDependencies />
  </SolutionManifest>
</ImportExportXml>
'''


def _customizations_xml(flows: list[dict[str, Any]]) -> str:
    workflows = '\n'.join(
        _workflow_xml(item['guid'], item['display_name'], item['json_filename']) for item in flows
    )
    refs = '\n'.join(
        [
            _connection_reference_xml(PLANNER_REFERENCE, 'Copilot Memory - Planner', 'shared_planner'),
            _connection_reference_xml(EXCEL_REFERENCE, 'Copilot Memory - Excel Online Business', 'shared_excelonlinebusiness'),
        ]
    )
    return f'''<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" OrganizationSchemaType="Standard">
  <Entities /><Roles />
  <Workflows>
{workflows}
  </Workflows>
  <FieldSecurityProfiles /><Templates /><EntityMaps /><EntityRelationships /><OrganizationSettings />
  <optionsets /><CustomControls /><EntityDataProviders />
  <Languages><Language>1046</Language></Languages>
  <connectionreferences>
{refs}
  </connectionreferences>
</ImportExportXml>
'''


def gerar_solucao_nativa_power_platform() -> dict[str, Any]:
    """Gera uma solução não gerenciada importável em Power Automate > Soluções."""
    materialized: list[dict[str, Any]] = []
    for flow in gerar_fluxos_completos():
        definition = flow['definition']
        errors = validar_definicao(definition)
        if errors:
            raise ValueError(f'Definicao invalida em {flow["id"]}: {errors}')
        guid = _flow_guid(flow['id'])
        filename = f'{_safe_filename(flow["display_name"])}-{guid.upper()}.json'
        materialized.append(
            {
                'id': flow['id'],
                'guid': guid,
                'display_name': flow['display_name'],
                'json_filename': filename,
                'wrapper': _wrapper(definition),
            }
        )

    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr('solution.xml', _solution_xml(materialized).encode('utf-8'))
        archive.writestr('customizations.xml', _customizations_xml(materialized).encode('utf-8'))
        for item in materialized:
            archive.writestr(
                f'Workflows/{item["json_filename"]}',
                json.dumps(item['wrapper'], ensure_ascii=False, separators=(',', ':')).encode('utf-8'),
            )

    raw = output.getvalue()
    return {
        'filename': SOLUTION_FILENAME,
        'base64': base64.b64encode(raw).decode('ascii'),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'size': len(raw),
        'flow_count': len(materialized),
        'solution_name': SOLUTION_NAME,
        'managed': False,
        'connection_references': [PLANNER_REFERENCE, EXCEL_REFERENCE],
        'post_import_configuration_required': True,
        'post_import_steps': [
            'Vincular as referencias de conexao Planner e Excel Online (Business) durante a importacao.',
            'Abrir os fluxos importados e preencher Group ID, Plan ID e identificacao do arquivo CopilotMemory.xlsx.',
            'Salvar os fluxos e executar um teste em DEV antes de ativar recorrencia.',
        ],
    }
