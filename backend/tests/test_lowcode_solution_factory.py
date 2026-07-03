import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_lowcode_solution_factory.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.schemas.lowcode_solution import LowCodeSolutionGenerateRequest
from app.services.lowcode_solution_factory import gerar_lowcode_solution


def test_gerar_lowcode_solution_completa():
    solution = gerar_lowcode_solution(
        LowCodeSolutionGenerateRequest(
            solution_name='ReqSysLowCode',
            display_name='ReqSys Low-Code',
            target_environment='dev',
            dry_run=True,
        )
    )

    assert solution['capability'] == 'LowCode Solution Factory P0'
    assert solution['status'] == 'planned'
    assert solution['governance']['no_custom_reqsys_api_required'] is True
    assert len(solution['dataverse']['tables']) >= 5
    assert solution['apps']['canvas_app']['app_type'] == 'canvas'
    assert solution['apps']['canvas_app']['start_screen'] == 'scrDashboard'
    assert len(solution['flows']) >= 4
    assert solution['copilot']['target'] == 'copilot_studio'
    assert len(solution['security_roles']) >= 4
    assert solution['alm_package']['requires_approval'] is True
    assert 'CANVAS.md' in [item['path'] for item in solution['package']['files']]
    assert solution['package']['zip_base64']


def test_lowcode_solution_respeita_modulos_selecionados():
    solution = gerar_lowcode_solution(
        LowCodeSolutionGenerateRequest(
            solution_name='ReqSysDataOnly',
            modules=['dataverse', 'security'],
            include_alm_package=False,
        )
    )

    assert len(solution['dataverse']['tables']) >= 5
    assert solution['apps']['canvas_app'] == {}
    assert solution['flows'] == []
    assert solution['copilot'] == {}
    assert solution['alm_package'] == {}
    assert len(solution['security_roles']) >= 4

