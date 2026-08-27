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
<p><strong>Você não precisa desenhar os fluxos no Power Automate.</strong> O ZIP contém as três definições completas.</p>
<h2>O que você faz no ambiente corporativo</h2><ol>
<li>Envie <code>CopilotMemory.xlsx</code> ao SharePoint/OneDrive.</li>
<li>Autorize as conexões <strong>Planner</strong> e <strong>Excel Online (Business)</strong>.</li>
<li>Informe Group ID, Plan ID, biblioteca e arquivo nos parâmetros de implantação.</li>
<li>Implante as três definições de <code>powerautomate/definitions/</code> usando o índice de implantação.</li>
<li>Ative os fluxos somente após o teste com uma tarefa em DEV.</li></ol>
<p>Dataverse, Power Apps, API personalizada e SQL Server não são necessários.</p>
<h2>Proteções já incluídas</h2><ul><li>releitura do Planner antes de gravar;</li><li>comando pendente congela a memória operacional;</li><li>conflito bloqueia a escrita;</li><li>histórico sem sobrescrita;</li><li>falha de atualização vira ERRO e mantém o comando para nova tentativa.</li></ul>
</body></html>'''


def gerar_copilot_memory_simple_solution(request: Any) -> dict[str, Any]:
    """Gera um ZIP com planilha e três definições completas do Power Automate."""
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

    complete_files: dict[str, bytes | str] = {
        'FLUXOS_COMPLETOS.html': _guia_fluxos_completos(),
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
        'mode': 'one_zip_with_complete_power_automate_definitions',
        'entrypoint': 'FLUXOS_COMPLETOS.html',
        'ready_workbook': 'CopilotMemory.xlsx',
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
