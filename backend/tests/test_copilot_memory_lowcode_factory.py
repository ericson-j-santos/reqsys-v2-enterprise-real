import base64
import io
import zipfile

from app.schemas.copilot_memory import CopilotMemoryLowCodePackageRequest
from app.services.copilot_memory_lowcode_factory import (
    gerar_copilot_memory_lowcode_solution,
)


def _abrir_zip(solution):
    raw = base64.b64decode(solution['package']['zip_base64'])
    return zipfile.ZipFile(io.BytesIO(raw), 'r')


def _arquivos_zip(solution):
    with _abrir_zip(solution) as archive:
        return set(archive.namelist())


def _conteudo_zip(solution):
    with _abrir_zip(solution) as archive:
        return b'\n'.join(archive.read(nome) for nome in archive.namelist())


def test_perfil_restrito_e_padrao_sem_dataverse_admin_api_ou_segredo():
    request = CopilotMemoryLowCodePackageRequest()
    solution = gerar_copilot_memory_lowcode_solution(request)

    assert request.profile == 'copilot_memory_corporativo_restrito'
    assert solution['profile'] == 'copilot_memory_corporativo_restrito'
    assert solution['effective_profile'] == 'copilot_memory_corporativo_restrito'
    assert solution['governance']['requires_custom_memory_api'] is False
    assert solution['governance']['requires_dataverse'] is False
    assert solution['governance']['requires_powerapps_admin'] is False
    assert solution['governance']['requires_power_platform_admin'] is False
    assert solution['governance']['source_of_truth']['tasks'] == 'Planner'
    assert 'Excel/SharePoint' in solution['governance']['source_of_truth']['memory_history']
    assert solution['dataverse']['tables'] == []
    assert solution['apps']['canvas_app'] == {}
    assert solution['security_roles'] == []
    assert solution['custom_connector'] == {}
    assert solution['core']['runtime_required'] is False
    assert len(solution['flows']) == 3

    connection_names = {item['name'] for item in solution['connections']}
    assert connection_names == {'cr_planner', 'cr_excel', 'cr_sharepoint'}

    variable_names = {item['name'] for item in solution['environment_variables']}
    assert 'COPILOT_MEMORY_API_BASE_URL' not in variable_names
    assert 'COPILOT_MEMORY_SERVICE_TOKEN' not in variable_names

    table_names = {item['table'] for item in solution['excel']['tables']}
    assert 'tbHistoricoCopilot' in table_names

    nomes = _arquivos_zip(solution)
    assert 'copilot-memory-lowcode/powerautomate/flows.json' in nomes
    assert 'copilot-memory-lowcode/excel/tables.json' in nomes
    assert 'copilot-memory-lowcode/deployment/INSTALL.md' in nomes
    assert not any('/connector/' in nome for nome in nomes)
    assert not any('/dataverse/' in nome for nome in nomes)
    assert not any('/powerapps/' in nome for nome in nomes)


def test_perfil_com_api_sem_dataverse_ou_admin():
    solution = gerar_copilot_memory_lowcode_solution(
        CopilotMemoryLowCodePackageRequest(profile='copilot_memory_corporativo_com_api')
    )

    assert solution['profile'] == 'copilot_memory_corporativo_com_api'
    assert solution['governance']['requires_custom_memory_api'] is True
    assert solution['governance']['requires_dataverse'] is False
    assert solution['governance']['requires_powerapps_admin'] is False
    assert solution['dataverse']['tables'] == []
    assert solution['apps']['canvas_app'] == {}
    assert len(solution['flows']) == 4

    nomes = _arquivos_zip(solution)
    assert 'copilot-memory-lowcode/connector/copilot-memory-api.json' in nomes
    assert not any('/dataverse/' in nome for nome in nomes)
    assert not any('/powerapps/' in nome for nome in nomes)


def test_perfil_minimal_antigo_permanece_compativel_com_perfil_com_api():
    solution = gerar_copilot_memory_lowcode_solution(
        CopilotMemoryLowCodePackageRequest(profile='copilot_memory_minimal')
    )

    assert solution['profile'] == 'copilot_memory_minimal'
    assert solution['effective_profile'] == 'copilot_memory_corporativo_com_api'
    assert solution['compatibility_alias'] is True
    assert solution['governance']['requires_custom_memory_api'] is True
    assert solution['dataverse']['tables'] == []


def test_perfil_enterprise_adiciona_governanca_visual_sem_mudar_fonte_canonica():
    solution = gerar_copilot_memory_lowcode_solution(
        CopilotMemoryLowCodePackageRequest(
            profile='copilot_memory_enterprise',
            owner_prefix='corp',
        )
    )

    assert solution['profile'] == 'copilot_memory_enterprise'
    assert len(solution['dataverse']['tables']) == 2
    assert solution['dataverse']['is_source_of_truth'] is False
    assert solution['apps']['canvas_app']['name'] == 'Copilot Memory Admin'
    assert len(solution['security_roles']) == 4
    assert solution['alm_package']['pac_cli_supported'] is True

    nomes = _arquivos_zip(solution)
    assert 'copilot-memory-lowcode/dataverse/schema.json' in nomes
    assert 'copilot-memory-lowcode/powerapps/admin-app.json' in nomes
    assert 'copilot-memory-lowcode/security/roles.json' in nomes


def test_pacote_restrito_nao_embute_token_api_ou_url_da_api():
    solution = gerar_copilot_memory_lowcode_solution(
        CopilotMemoryLowCodePackageRequest(profile='copilot_memory_corporativo_restrito')
    )
    conteudo = _conteudo_zip(solution)

    assert b'COPILOT_MEMORY_SERVICE_TOKEN' not in conteudo
    assert b'COPILOT_MEMORY_API_BASE_URL' not in conteudo
    assert b'X-Service-Token' not in conteudo
    assert b'Bearer ' not in conteudo


def test_pacote_com_api_nao_embute_valor_de_segredo():
    solution = gerar_copilot_memory_lowcode_solution(
        CopilotMemoryLowCodePackageRequest(profile='copilot_memory_corporativo_com_api')
    )
    conteudo = _conteudo_zip(solution)

    assert b'COPILOT_MEMORY_SERVICE_TOKEN' in conteudo
    assert b'Bearer ' not in conteudo
    assert b'X-Service-Token' in conteudo


def test_flows_restritos_possuem_idempotencia_e_politica_de_conflito():
    solution = gerar_copilot_memory_lowcode_solution(
        CopilotMemoryLowCodePackageRequest(profile='copilot_memory_corporativo_restrito')
    )
    flows = {item['id']: item for item in solution['flows']}

    planner_to_excel = flows['flow_planner_to_excel_memory']
    excel_to_planner = flows['flow_excel_to_planner_restrito']

    assert 'plannertaskid' in planner_to_excel['idempotency'].lower()
    assert 'signature' in planner_to_excel['idempotency'].lower()
    assert 'ultimo-vence' in excel_to_planner['conflict_policy']
    assert 'plannerappliedsignature' in excel_to_planner['idempotency'].lower()
