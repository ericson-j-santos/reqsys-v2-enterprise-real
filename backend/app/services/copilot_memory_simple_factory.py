from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from io import BytesIO
from typing import Any

from app.services.copilot_memory_lowcode_factory import (
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


def gerar_copilot_memory_simple_solution(request: Any) -> dict[str, Any]:
    """Gera um único ZIP com planilha e os três fluxos completos.

    O ReqSys entrega a lógica executável e separa somente as referências de
    conexão/identificadores específicos do tenant. Nenhuma credencial é
    embutida e nenhuma escrita é feita no tenant durante a geração.
    """
    if request.profile != PROFILE_RESTRITO:
        return gerar_copilot_memory_lowcode_solution(request)

    solution = gerar_copilot_memory_lowcode_solution(request)
    ready = gerar_pacote_pronto()
    complete_flows = gerar_fluxos_completos()
    flow_validation = {
        flow['id']: validar_definicao(flow['definition']) for flow in complete_flows
    }
    if any(flow_validation.values()):
        raise ValueError(f'Definicoes Power Automate invalidas: {flow_validation}')

    complete_files: dict[str, bytes | str] = {
        'powerautomate/connection-references.json': json.dumps(
            connection_references_template(), ensure_ascii=False, indent=2
        ),
        'powerautomate/deployment-index.json': json.dumps(
            deployment_index(), ensure_ascii=False, indent=2
        ),
    }
    for flow in complete_flows:
        complete_files[f"powerautomate/definitions/{flow['id']}.json"] = json.dumps(
            flow['definition'], ensure_ascii=False, indent=2
        )

    old_zip = base64.b64decode(solution['package']['zip_base64'])
    output = BytesIO()
    root = 'copilot-memory-lowcode/'

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
            target.writestr(root + path, _conteudo_bytes(content))

        all_hashes = list(ready['hashes'])
        for path, content in sorted(complete_files.items()):
            raw = _conteudo_bytes(content)
            all_hashes.append(
                {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
            )
        checksum_text = '\n'.join(
            f"{item['sha256']}  {item['path']}" for item in all_hashes
        ) + '\n'
        target.writestr(root + 'checksums.sha256', checksum_text)

    payload = output.getvalue()
    solution['simple_installation'] = {
        'enabled': True,
        'mode': 'one_zip_with_complete_power_automate_definitions',
        'entrypoint': 'INICIAR_AQUI.html',
        'ready_workbook': 'CopilotMemory.xlsx',
        'complete_flow_definitions': [
            f"powerautomate/definitions/{flow['id']}.json" for flow in complete_flows
        ],
        'deployment_index': 'powerautomate/deployment-index.json',
        'connection_references': 'powerautomate/connection-references.json',
        'flow_validation': flow_validation,
        'requires_manual_flow_design': False,
        'requires_connection_authentication': True,
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
