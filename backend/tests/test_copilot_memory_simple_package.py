import base64
import io
import json
import zipfile

from app.schemas.copilot_memory import CopilotMemoryLowCodePackageRequest
from app.services.copilot_memory_simple_factory import (
    gerar_copilot_memory_simple_solution,
)
from copilot_memory_simple_package import (
    FLOW_CONTRACTS,
    gerar_pacote_pronto,
    validar_planilha_xlsx,
)


def test_planilha_pronta_tem_as_tres_tabelas_corporativas():
    pacote = gerar_pacote_pronto()
    xlsx = pacote['files']['CopilotMemory.xlsx']

    resultado = validar_planilha_xlsx(xlsx)

    assert resultado['ok'] is True
    assert resultado['tabelas'] == [
        'tbMemoriaCopilot',
        'tbAtualizacoesPlanner',
        'tbHistoricoCopilot',
    ]
    assert zipfile.is_zipfile(io.BytesIO(xlsx))


def test_autoteste_do_pacote_pronto_fica_aprovado():
    pacote = gerar_pacote_pronto()

    assert pacote['autoteste']['status'] == 'APROVADO'
    assert all(check['ok'] for check in pacote['autoteste']['checks'])
    assert len(FLOW_CONTRACTS) == 3
    assert len(pacote['hashes']) >= 8


def test_gerador_padrao_entrega_um_unico_zip_pronto_para_extrair():
    request = CopilotMemoryLowCodePackageRequest()
    solution = gerar_copilot_memory_simple_solution(request)

    assert solution['profile'] == 'copilot_memory_corporativo_restrito'
    assert solution['simple_installation']['enabled'] is True
    assert solution['simple_installation']['requires_python_on_corporate_machine'] is False
    assert solution['simple_installation']['requires_dataverse'] is False
    assert solution['simple_installation']['requires_powerapps'] is False
    assert solution['simple_installation']['requires_custom_api'] is False
    assert solution['simple_installation']['autoteste']['status'] == 'APROVADO'
    assert solution['package']['zip_filename'] == 'CopilotMemoryCorporativo-Pronto.zip'
    assert solution['package']['sha256']

    raw = base64.b64decode(solution['package']['zip_base64'])
    assert zipfile.is_zipfile(io.BytesIO(raw))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = set(archive.namelist())
        root = 'copilot-memory-lowcode/'
        assert root + 'INICIAR_AQUI.html' in names
        assert root + 'CopilotMemory.xlsx' in names
        assert root + 'AUTOTESTE.json' in names
        assert root + 'PROMPTS_POWER_AUTOMATE.txt' in names
        assert root + 'checksums.sha256' in names
        assert len([name for name in names if name.startswith(root + 'powerautomate/0')]) == 3
        autotest = json.loads(archive.read(root + 'AUTOTESTE.json'))
        assert autotest['status'] == 'APROVADO'
        workbook = archive.read(root + 'CopilotMemory.xlsx')
        assert validar_planilha_xlsx(workbook)['ok'] is True


def test_perfil_com_api_preserva_pacote_anterior_sem_forcar_modo_simples():
    request = CopilotMemoryLowCodePackageRequest(profile='copilot_memory_corporativo_com_api')
    solution = gerar_copilot_memory_simple_solution(request)

    assert solution['profile'] == 'copilot_memory_corporativo_com_api'
    assert 'simple_installation' not in solution
    assert solution['governance']['requires_custom_memory_api'] is True
