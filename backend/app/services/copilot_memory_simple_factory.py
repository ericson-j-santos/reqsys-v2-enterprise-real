from __future__ import annotations

import base64
import hashlib
import zipfile
from io import BytesIO
from typing import Any

from app.services.copilot_memory_lowcode_factory import (
    PROFILE_RESTRITO,
    gerar_copilot_memory_lowcode_solution,
)
from copilot_memory_simple_package import gerar_pacote_pronto


def _conteudo_bytes(content: bytes | str) -> bytes:
    return content if isinstance(content, bytes) else content.encode('utf-8')


def gerar_copilot_memory_simple_solution(request: Any) -> dict[str, Any]:
    """Gera um único ZIP pronto para o perfil corporativo restrito.

    Mantém o contrato do gerador low-code existente, mas acrescenta a planilha
    XLSX já estruturada, três fluxos individualizados, guia de início e
    autoteste. Nenhuma ação é executada no tenant Microsoft.
    """
    if request.profile != PROFILE_RESTRITO:
        return gerar_copilot_memory_lowcode_solution(request)

    solution = gerar_copilot_memory_lowcode_solution(request)
    ready = gerar_pacote_pronto()

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
        checksum_text = '\n'.join(
            f"{item['sha256']}  {item['path']}" for item in ready['hashes']
        ) + '\n'
        target.writestr(root + 'checksums.sha256', checksum_text)

    payload = output.getvalue()
    solution['simple_installation'] = {
        'enabled': True,
        'mode': 'one_zip_extract_and_follow',
        'entrypoint': 'INICIAR_AQUI.html',
        'ready_workbook': 'CopilotMemory.xlsx',
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
    solution['package']['simple_files'] = ready['hashes'] + [
        {
            'path': 'checksums.sha256',
            'sha256': hashlib.sha256(checksum_text.encode('utf-8')).hexdigest(),
            'size': len(checksum_text.encode('utf-8')),
        }
    ]
    return solution
