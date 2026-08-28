from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from io import BytesIO
from typing import Any

from app.services.copilot_memory_lowcode_factory import (
    PACKAGE_NAME,
    PROFILE_RESTRITO,
    gerar_copilot_memory_lowcode_solution,
)
from app.services.copilot_memory_native_solution import (
    SOLUTION_UNIQUE_NAME,
    SOLUTION_VERSION,
    gerar_solution_power_platform_importavel,
    validar_solution_power_platform_importavel,
)
from copilot_memory_powerautomate_complete import (
    connection_references_template,
    deployment_index,
    gerar_fluxos_completos,
    validar_definicao,
)
from copilot_memory_simple_package import gerar_pacote_pronto


def _conteudo_bytes(content: bytes | str) -> bytes:
    return content if isinstance(content, bytes) else content.encode('utf-8')


def _guia_fluxos_completos() -> str:
    return '''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Copilot Memory — implantação</title><style>body{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;line-height:1.55}code{background:#eee;padding:2px 5px}li{margin:10px 0}</style></head>
<body><h1>Copilot Memory — fluxo completo gerado pelo ReqSys</h1>
<p><strong>Você não precisa desenhar os fluxos no Power Automate.</strong> O ZIP contém as três definições completas e uma solução importável.</p>
<h2>Caminho 1 — importação direta</h2><ol>
<li>Abra <code>IMPORTAR_DIRETO_NO_POWER_AUTOMATE.html</code>.</li>
<li>Importe <code>CopilotMemoryInstaller.zip</code> em Power Automate &gt; Soluções.</li>
<li>Vincule as conexões Planner e Excel Online (Business).</li>
<li>Configure os parâmetros do Planner e do arquivo Excel.</li>
<li>Ative os fluxos somente após o teste em DEV.</li></ol>
<h2>Caminho 2 — implantação assistida</h2><ol>
<li>Envie <code>CopilotMemory.xlsx</code> ao SharePoint/OneDrive.</li>
<li>Autorize as conexões <strong>Planner</strong> e <strong>Excel Online (Business)</strong>.</li>
<li>Informe Group ID, Plan ID, biblioteca e arquivo no assistente do ReqSys.</li>
<li>Use o botão <strong>Instalar 3 fluxos</strong>.</li></ol>
<p>Dataverse, Power Apps, API personalizada e SQL Server não são necessários para o perfil restrito.</p>
<h2>Proteções já incluídas</h2><ul><li>releitura do Planner antes de gravar;</li><li>comando pendente congela a memória operacional;</li><li>conflito bloqueia a escrita;</li><li>histórico sem sobrescrita;</li><li>falha de atualização vira ERRO e mantém o comando para nova tentativa.</li></ul>
</body></html>'''


def _guia_importacao_direta() -> str:
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Copilot Memory — importar solução</title><style>body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;line-height:1.55}}code{{background:#eee;padding:2px 5px}}li{{margin:10px 0}}.ok{{border-left:4px solid #26890c;padding:10px 14px;background:#f4fbf1}}</style></head>
<body><h1>Importação direta no Power Automate</h1>
<p class="ok"><strong>Arquivo:</strong> <code>CopilotMemoryInstaller.zip</code><br><strong>Solução:</strong> {SOLUTION_UNIQUE_NAME}<br><strong>Versão:</strong> {SOLUTION_VERSION}</p>
<ol>
<li>Coloque <code>CopilotMemory.xlsx</code> no SharePoint ou OneDrive corporativo.</li>
<li>Abra <strong>Power Automate &gt; Soluções &gt; Importar solução</strong>.</li>
<li>Selecione <code>CopilotMemoryInstaller.zip</code>.</li>
<li>Quando solicitado, vincule uma conexão <strong>Planner</strong> e uma conexão <strong>Excel Online (Business)</strong>.</li>
<li>Após a importação, abra os três fluxos e configure os parâmetros <code>PLANNER_GROUP_ID</code>, <code>PLANNER_PLAN_ID</code>, <code>EXCEL_SOURCE</code>, <code>EXCEL_DRIVE</code> e <code>EXCEL_FILE</code>.</li>
<li>Salve e teste uma tarefa em DEV antes de ativar os fluxos.</li>
</ol>
<p><strong>Importante:</strong> a solução cria os três fluxos em estado desligado. A ativação é deliberadamente manual para impedir execução contra o Planner ou arquivo errado.</p>
</body></html>'''


def gerar_copilot_memory_simple_solution(request: Any) -> dict[str, Any]:
    """Gera um ZIP com planilha, definicoes e solution Power Platform importavel."""
    if request.profile != PROFILE_RESTRITO:
        return gerar_copilot_memory_lowcode_solution(request)

    solution = gerar_copilot_memory_lowcode_solution(request)
    ready = gerar_pacote_pronto()
    complete_flows = gerar_fluxos_completos()
    validation = {
        flow['id']: validar_definicao(flow['definition']) for flow in complete_flows
    }
    if any(validation.values()):
        raise ValueError(f'Definicoes Power Automate invalidas: {validation}')

    native_solution = gerar_solution_power_platform_importavel(complete_flows)
    native_validation = validar_solution_power_platform_importavel(native_solution)
    if not native_validation['ok']:
        raise ValueError(f'Solution Power Platform invalida: {native_validation}')

    complete_files: dict[str, bytes | str] = {
        'FLUXOS_COMPLETOS.html': _guia_fluxos_completos(),
        'IMPORTAR_DIRETO_NO_POWER_AUTOMATE.html': _guia_importacao_direta(),
        'CopilotMemoryInstaller.zip': native_solution,
        'powerautomate/connection-references.json': json.dumps(
            connection_references_template(), ensure_ascii=False, indent=2
        ),
        'powerautomate/deployment-index.json': json.dumps(
            deployment_index(), ensure_ascii=False, indent=2
        ),
        'powerautomate/create-flow-requests.json': json.dumps(
            [
                {
                    'displayName': flow['display_name'],
                    'state': flow['state'],
                    'definition': flow['definition'],
                    'connectionReferences': connection_references_template(),
                }
                for flow in complete_flows
            ],
            ensure_ascii=False,
            indent=2,
        ),
    }
    for flow in complete_flows:
        complete_files[f"powerautomate/definitions/{flow['id']}.json"] = json.dumps(
            flow['definition'], ensure_ascii=False, indent=2
        )

    old_zip = base64.b64decode(solution['package']['zip_base64'])
    output = BytesIO()
    root = f'{PACKAGE_NAME}/'
    all_hashes = list(ready['hashes'])

    with zipfile.ZipFile(BytesIO(old_zip), 'r') as source, zipfile.ZipFile(
        output,
        'w',
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        for path, content in ready['files'].items():
            target.writestr(root + path, _conteudo_bytes(content))
        for path, content in complete_files.items():
            raw = _conteudo_bytes(content)
            target.writestr(root + path, raw)
            all_hashes.append(
                {
                    'path': path,
                    'sha256': hashlib.sha256(raw).hexdigest(),
                    'size': len(raw),
                }
            )
        checksum_text = '\n'.join(
            f"{item['sha256']}  {item['path']}" for item in all_hashes
        ) + '\n'
        target.writestr(root + 'checksums.sha256', checksum_text)

    payload = output.getvalue()
    solution['simple_installation'] = {
        'enabled': True,
        'mode': 'one_zip_with_direct_import_solution_and_complete_definitions',
        'entrypoint': 'FLUXOS_COMPLETOS.html',
        'manual_import_entrypoint': 'IMPORTAR_DIRETO_NO_POWER_AUTOMATE.html',
        'ready_workbook': 'CopilotMemory.xlsx',
        'native_solution': 'CopilotMemoryInstaller.zip',
        'native_solution_name': SOLUTION_UNIQUE_NAME,
        'native_solution_version': SOLUTION_VERSION,
        'native_solution_validation': native_validation,
        'direct_import_supported': True,
        'complete_flow_definitions': [
            f"powerautomate/definitions/{flow['id']}.json" for flow in complete_flows
        ],
        'create_flow_requests': 'powerautomate/create-flow-requests.json',
        'deployment_index': 'powerautomate/deployment-index.json',
        'connection_references': 'powerautomate/connection-references.json',
        'flow_validation': validation,
        'requires_manual_flow_design': False,
        'requires_connection_authentication': True,
        'required_connections': ['Planner', 'Excel Online (Business)'],
        'post_import_configuration': [
            'PLANNER_GROUP_ID',
            'PLANNER_PLAN_ID',
            'EXCEL_SOURCE',
            'EXCEL_DRIVE',
            'EXCEL_FILE',
        ],
        'flows_imported_disabled': True,
        'requires_local_installer': False,
        'requires_python_on_corporate_machine': False,
        'requires_dataverse': False,
        'requires_powerapps': False,
        'requires_custom_api': False,
        'autoteste': ready['autoteste'],
    }
    solution['package']['zip_filename'] = 'CopilotMemoryCorporativo-Pronto.zip'
    solution['package']['zip_base64'] = base64.b64encode(payload).decode('ascii')
    solution['package']['sha256'] = hashlib.sha256(payload).hexdigest()
    solution['package']['size'] = len(payload)
    solution['package']['simple_files'] = all_hashes + [
        {
            'path': 'checksums.sha256',
            'sha256': hashlib.sha256(checksum_text.encode('utf-8')).hexdigest(),
            'size': len(checksum_text.encode('utf-8')),
        }
    ]
    return solution
