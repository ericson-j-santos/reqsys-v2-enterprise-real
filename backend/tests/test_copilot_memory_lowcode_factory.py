import base64
import io
import zipfile

from app.schemas.copilot_memory import CopilotMemoryLowCodePackageRequest
from app.services.copilot_memory_lowcode_factory import (
    gerar_copilot_memory_lowcode_solution,
)


def _arquivos_zip(solution):
    raw = base64.b64decode(solution['package']['zip_base64'])
    with zipfile.ZipFile(io.BytesIO(raw), 'r') as archive:
        return set(archive.namelist())


def test_perfil_minimo_e_portatil_e_sem_dataverse_obrigatorio():
    solution = gerar_copilot_memory_lowcode_solution(
        CopilotMemoryLowCodePackageRequest(profile='copilot_memory_minimal')
    )

    assert solution['profile'] == 'copilot_memory_minimal'
    assert solution['governance']['no_custom_reqsys_api_required'] is True
    assert solution['governance']['secrets_embedded'] is False
    assert solution['governance']['source_of_truth']['tasks'] == 'Planner'
    assert solution['dataverse']['tables'] == []
    assert solution['apps']['canvas_app'] == {}
    assert solution['security_roles'] == []
    assert len(solution['flows']) == 4
    assert solution['excel']['tables'][0]['key'] == 'MemoryId'

    nomes = _arquivos_zip(solution)
    assert 'copilot-memory-lowcode/powerautomate/flows.json' in nomes
    assert 'copilot-memory-lowcode/excel/tables.json' in nomes
    assert 'copilot-memory-lowcode/connector/copilot-memory-api.json' in nomes
    assert 'copilot-memory-lowcode/deployment/INSTALL.md' in nomes
    assert not any('/dataverse/' in nome for nome in nomes)


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


def test_pacote_nao_embute_token_ou_url_real():
    solution = gerar_copilot_memory_lowcode_solution(
        CopilotMemoryLowCodePackageRequest(profile='copilot_memory_minimal')
    )
    bruto = base64.b64decode(solution['package']['zip_base64'])

    assert b'COPILOT_MEMORY_SERVICE_TOKEN' in bruto
    assert b'POWERPLATFORM_CLIENT_SECRET' not in bruto
    assert b'Bearer ' not in bruto
    assert b'X-Service-Token' in bruto


def test_flows_possuem_idempotencia_e_politica_de_conflito():
    solution = gerar_copilot_memory_lowcode_solution(
        CopilotMemoryLowCodePackageRequest(profile='copilot_memory_minimal')
    )
    flows = {item['id']: item for item in solution['flows']}

    assert 'hash' in flows['flow_planner_to_memory']['idempotency'].lower()
    assert 'contenthash' in flows['flow_memory_to_excel']['idempotency'].lower()
    assert 'ultimo-vence' in flows['flow_excel_to_planner']['conflict_policy']
