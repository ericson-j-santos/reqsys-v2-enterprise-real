import base64
import io
import json
import zipfile

from app.schemas.copilot_memory import CopilotMemoryLowCodePackageRequest
from app.services.copilot_memory_lowcode_factory import PACKAGE_NAME
from app.services.copilot_memory_native_solution import (
    EXCEL_REFERENCE,
    PLANNER_REFERENCE,
    gerar_solucao_nativa_power_platform,
)
from app.services.copilot_memory_simple_factory import gerar_copilot_memory_simple_solution


def test_solucao_nativa_e_zip_importavel_com_tres_fluxos_e_referencias():
    solution = gerar_solucao_nativa_power_platform()
    raw = base64.b64decode(solution['base64'])

    assert solution['filename'] == 'CopilotMemoryInstaller.zip'
    assert solution['solution_name'] == 'CopilotMemoryInstaller'
    assert solution['flow_count'] == 3
    assert solution['managed'] is False
    assert solution['connection_references'] == [PLANNER_REFERENCE, EXCEL_REFERENCE]
    assert solution['sha256']
    assert solution['size'] == len(raw)
    assert zipfile.is_zipfile(io.BytesIO(raw))

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = set(archive.namelist())
        assert 'solution.xml' in names
        assert 'customizations.xml' in names
        workflows = sorted(name for name in names if name.startswith('Workflows/') and name.endswith('.json'))
        assert len(workflows) == 3

        solution_xml = archive.read('solution.xml').decode('utf-8')
        customizations = archive.read('customizations.xml').decode('utf-8')
        assert '<UniqueName>CopilotMemoryInstaller</UniqueName>' in solution_xml
        assert solution_xml.count('<RootComponent type="29"') == 3
        assert '<MissingDependencies />' in solution_xml
        assert f'connectionreferencelogicalname="{PLANNER_REFERENCE}"' in customizations
        assert f'connectionreferencelogicalname="{EXCEL_REFERENCE}"' in customizations
        assert '/providers/Microsoft.PowerApps/apis/shared_planner' in customizations
        assert '/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness' in customizations

        for workflow in workflows:
            wrapper = json.loads(archive.read(workflow))
            refs = wrapper['properties']['connectionReferences']
            assert refs['shared_planner']['connection']['connectionReferenceLogicalName'] == PLANNER_REFERENCE
            assert refs['shared_excelonlinebusiness']['connection']['connectionReferenceLogicalName'] == EXCEL_REFERENCE
            assert wrapper['properties']['definition']['triggers']
            assert wrapper['properties']['definition']['actions']


def test_pacote_contingencia_inclui_solucao_nativa_e_download_direto():
    solution = gerar_copilot_memory_simple_solution(CopilotMemoryLowCodePackageRequest())
    package = solution['package']
    native_raw = base64.b64decode(package['native_solution_base64'])

    assert package['native_solution_filename'] == 'CopilotMemoryInstaller.zip'
    assert package['native_solution_sha256']
    assert package['native_solution_size'] == len(native_raw)
    assert zipfile.is_zipfile(io.BytesIO(native_raw))
    assert solution['simple_installation']['mode'] == 'native_solution_plus_full_contingency'
    assert solution['simple_installation']['native_solution'] == 'CopilotMemoryInstaller.zip'
    assert solution['simple_installation']['native_solution_flow_count'] == 3
    assert solution['simple_installation']['requires_manual_flow_design'] is False

    outer_raw = base64.b64decode(package['zip_base64'])
    with zipfile.ZipFile(io.BytesIO(outer_raw)) as archive:
        nested_path = f'{PACKAGE_NAME}/CopilotMemoryInstaller.zip'
        assert nested_path in archive.namelist()
        nested = archive.read(nested_path)
        assert nested == native_raw
        assert zipfile.is_zipfile(io.BytesIO(nested))
