import base64
import io
import json
import zipfile

from app.schemas.copilot_memory import CopilotMemoryLowCodePackageRequest
from app.services.copilot_memory_lowcode_factory import PACKAGE_NAME
from app.services.copilot_memory_simple_factory import (
    gerar_copilot_memory_simple_solution,
)
from copilot_memory_powerautomate_complete import (
    EXCEL_API,
    PLANNER_API,
    gerar_fluxos_completos,
    validar_definicao,
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


def test_planilha_pronta_declara_cellstyles_para_evitar_reparo_no_excel():
    pacote = gerar_pacote_pronto()
    xlsx = pacote['files']['CopilotMemory.xlsx']

    with zipfile.ZipFile(io.BytesIO(xlsx)) as archive:
        styles = archive.read('xl/styles.xml').decode('utf-8')

    assert '<cellStyles' in styles
    assert 'name="Normal"' in styles


def test_autoteste_do_pacote_pronto_fica_aprovado():
    pacote = gerar_pacote_pronto()

    assert pacote['autoteste']['status'] == 'APROVADO'
    assert all(check['ok'] for check in pacote['autoteste']['checks'])
    assert len(FLOW_CONTRACTS) == 3
    assert len(pacote['hashes']) >= 8


def test_definicoes_completas_tem_schema_gatilhos_acoes_e_so_dois_conectores():
    fluxos = gerar_fluxos_completos()

    assert len(fluxos) == 3
    for fluxo in fluxos:
        definicao = fluxo['definition']
        assert validar_definicao(definicao) == []
        assert '$authentication' in definicao['parameters']
        assert '$connections' in definicao['parameters']
        assert definicao['triggers']
        assert definicao['actions']
        texto = json.dumps(definicao)
        assert 'shared_commondataserviceforapps' not in texto
        assert PLANNER_API in texto or EXCEL_API in texto


def test_fluxos_completos_usam_operacoes_estaveis_e_protecao_de_conflito():
    texto = json.dumps(gerar_fluxos_completos(), ensure_ascii=False)

    assert 'ListTasks_V3' in texto
    assert 'GetTask_V2' in texto
    assert 'UpdateTask_V2' in texto
    assert 'UpdateTask_V3' not in texto
    assert 'GetItems' in texto
    assert 'AddRowV2' in texto
    assert 'PatchItem' in texto
    assert 'PlannerAppliedSignature' in texto
    assert 'AtualizarPlanner' in texto
    assert 'Buscar_comando_pendente' in texto
    assert 'PENDENTE' in texto
    assert 'CONFLITO' in texto
    assert 'ERRO' in texto


def test_gerador_padrao_entrega_um_unico_zip_com_fluxos_completos():
    request = CopilotMemoryLowCodePackageRequest()
    solution = gerar_copilot_memory_simple_solution(request)

    assert solution['profile'] == 'copilot_memory_corporativo_restrito'
    simple = solution['simple_installation']
    assert simple['enabled'] is True
    assert simple['requires_python_on_corporate_machine'] is False
    assert simple['requires_dataverse'] is False
    assert simple['requires_powerapps'] is False
    assert simple['requires_custom_api'] is False
    assert simple['requires_manual_flow_design'] is False
    assert simple['requires_connection_authentication'] is True
    assert simple['required_connections'] == ['Planner', 'Excel Online (Business)']
    assert simple['autoteste']['status'] == 'APROVADO'
    assert all(not errors for errors in simple['flow_validation'].values())
    assert len(simple['complete_flow_definitions']) == 3
    assert solution['package']['zip_filename'] == 'CopilotMemoryCorporativo-Pronto.zip'
    assert solution['package']['sha256']

    raw = base64.b64decode(solution['package']['zip_base64'])
    assert zipfile.is_zipfile(io.BytesIO(raw))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = set(archive.namelist())
        root = f'{PACKAGE_NAME}/'
        assert root + 'FLUXOS_COMPLETOS.html' in names
        assert root + 'INICIAR_AQUI.html' in names
        assert root + 'CopilotMemory.xlsx' in names
        assert root + 'AUTOTESTE.json' in names
        assert root + 'checksums.sha256' in names
        assert root + 'powerautomate/connection-references.json' in names
        assert root + 'powerautomate/deployment-index.json' in names
        assert root + 'powerautomate/create-flow-requests.json' in names
        definitions = [
            name for name in names if name.startswith(root + 'powerautomate/definitions/')
        ]
        assert len(definitions) == 3
        for path in definitions:
            definition = json.loads(archive.read(path))
            assert validar_definicao(definition) == []
        create_requests = json.loads(
            archive.read(root + 'powerautomate/create-flow-requests.json')
        )
        assert len(create_requests) == 3
        assert all(item['definition'] for item in create_requests)
        assert all(item['connectionReferences'] for item in create_requests)
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
