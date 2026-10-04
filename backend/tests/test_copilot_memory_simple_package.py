import base64
import io
import json
import zipfile

from app.schemas.copilot_memory import CopilotMemoryLowCodePackageRequest
from app.services.copilot_memory_lowcode_factory import PACKAGE_NAME
from app.services.copilot_memory_native_solution import (
    EXCEL_CONNECTION_LOGICAL_NAME,
    PLANNER_CONNECTION_LOGICAL_NAME,
    SOLUTION_UNIQUE_NAME,
    gerar_solution_power_platform_importavel,
    validar_solution_power_platform_importavel,
)
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
    gerar_planilha_xlsx,
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


def test_planilha_declara_docprops_exigidos_pelo_motor_excel_do_graph():
    xlsx = gerar_planilha_xlsx()

    with zipfile.ZipFile(io.BytesIO(xlsx)) as archive:
        names = set(archive.namelist())
        content_types = archive.read('[Content_Types].xml').decode('utf-8')
        root_rels = archive.read('_rels/.rels').decode('utf-8')

    assert 'docProps/core.xml' in names
    assert 'docProps/app.xml' in names
    assert '/docProps/core.xml' in content_types
    assert '/docProps/app.xml' in content_types
    assert 'docProps/core.xml' in root_rels
    assert 'docProps/app.xml' in root_rels


def test_planilha_aceita_tabelas_customizadas_para_outros_perfis():
    tabelas = [('Demandas', 'tbDemandas', ['TaskId', 'Titulo'])]

    xlsx = gerar_planilha_xlsx(tabelas)
    resultado = validar_planilha_xlsx_customizada(xlsx, tabelas)

    assert resultado['tabelas'] == ['tbDemandas']
    assert zipfile.is_zipfile(io.BytesIO(xlsx))


def validar_planilha_xlsx_customizada(xlsx: bytes, tabelas) -> dict:
    import re

    with zipfile.ZipFile(io.BytesIO(xlsx)) as archive:
        found = []
        for index in range(1, len(tabelas) + 1):
            texto = archive.read(f'xl/tables/table{index}.xml').decode('utf-8')
            match = re.search(r'displayName="([^"]+)"', texto)
            if match:
                found.append(match.group(1))
    return {'tabelas': found}


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


def test_solution_nativa_tem_formato_importavel_e_tres_fluxos_desligados():
    payload = gerar_solution_power_platform_importavel(gerar_fluxos_completos())
    validation = validar_solution_power_platform_importavel(payload)

    assert validation['ok'] is True
    assert validation['flows'] == 3
    assert validation['connections'] == 2
    assert validation['solution_name'] == SOLUTION_UNIQUE_NAME

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = set(archive.namelist())
        assert '[Content_Types].xml' in names
        assert 'solution.xml' in names
        assert 'customizations.xml' in names
        workflows = sorted(name for name in names if name.startswith('Workflows/'))
        assert len(workflows) == 3

        customizations = archive.read('customizations.xml').decode('utf-8')
        assert customizations.count('<Workflow WorkflowId=') == 3
        assert '<StateCode>0</StateCode>' in customizations
        assert '<StatusCode>1</StatusCode>' in customizations
        assert PLANNER_CONNECTION_LOGICAL_NAME in customizations
        assert EXCEL_CONNECTION_LOGICAL_NAME in customizations

        solution_xml = archive.read('solution.xml').decode('utf-8')
        assert solution_xml.count('<RootComponent type="29"') == 3
        assert '<Managed>0</Managed>' in solution_xml

        for path in workflows:
            wrapper = json.loads(archive.read(path))
            assert wrapper['schemaVersion'] == '1.0.0.0'
            assert wrapper['properties']['definition']
            assert wrapper['properties']['connectionReferences']


def test_gerador_padrao_entrega_um_unico_zip_com_solution_importavel():
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
    assert simple['direct_import_supported'] is True
    assert simple['native_solution'] == 'CopilotMemoryInstaller.zip'
    assert simple['native_solution_validation']['ok'] is True
    assert simple['flows_imported_disabled'] is True
    assert simple['post_import_configuration'] == [
        'PLANNER_GROUP_ID',
        'PLANNER_PLAN_ID',
        'EXCEL_SOURCE',
        'EXCEL_DRIVE',
        'EXCEL_FILE',
    ]
    assert solution['package']['zip_filename'] == 'CopilotMemoryCorporativo-Pronto.zip'
    assert solution['package']['sha256']

    raw = base64.b64decode(solution['package']['zip_base64'])
    assert zipfile.is_zipfile(io.BytesIO(raw))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = set(archive.namelist())
        root = f'{PACKAGE_NAME}/'
        assert root + 'FLUXOS_COMPLETOS.html' in names
        assert root + 'IMPORTAR_DIRETO_NO_POWER_AUTOMATE.html' in names
        assert root + 'CopilotMemoryInstaller.zip' in names
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

        native = archive.read(root + 'CopilotMemoryInstaller.zip')
        assert validar_solution_power_platform_importavel(native)['ok'] is True


def test_perfil_com_api_preserva_pacote_anterior_sem_forcar_modo_simples():
    request = CopilotMemoryLowCodePackageRequest(profile='copilot_memory_corporativo_com_api')
    solution = gerar_copilot_memory_simple_solution(request)

    assert solution['profile'] == 'copilot_memory_corporativo_com_api'
    assert 'simple_installation' not in solution
    assert solution['governance']['requires_custom_memory_api'] is True
