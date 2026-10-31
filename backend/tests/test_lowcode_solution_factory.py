import base64
import json
import os
import zipfile
from io import BytesIO

import pytest
from pydantic import ValidationError

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
    assert solution['delivery']['dispatch'] == 'not_requested'
    assert solution['delivery']['installation'] == 'not_verified'
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


@pytest.mark.parametrize('environment', ['dev', 'stg', 'prod'])
def test_sem_executor_dry_run_false_nao_despacha_nem_instala(environment):
    result = gerar_lowcode_solution(
        LowCodeSolutionGenerateRequest(target_environment=environment, dry_run=False)
    )
    assert result['status'] == 'pending_dispatch'
    assert result['governance']['mode'] == 'blueprint_only_pending_dispatch'
    assert result['alm_package']['mode'] == 'pending_dispatch'
    assert result['alm_package']['importable'] is False
    assert result['alm_package']['dispatch_receipt'] is None
    assert result['delivery'] == {
        'blueprint': 'generated',
        'dispatch': 'not_requested',
        'execution': 'not_started',
        'installation': 'not_verified',
        'dispatch_receipt': None,
        'execution_receipt': None,
        'installation_evidence': None,
        'external_write_performed': False,
        'blocker': 'alm_executor_not_integrated',
    }
    assert result['package']['importable'] is False
    content = base64.b64decode(result['package']['zip_base64'], validate=True)
    with zipfile.ZipFile(BytesIO(content)) as archive:
        files = archive.namelist()
        assert not any(name.endswith('/solution.xml') for name in files)
        manifest = json.loads(archive.read(next(name for name in files if name.endswith('/manifest.json'))))
        assert manifest['delivery']['dispatch'] == 'not_requested'
        assert manifest['delivery']['installation'] == 'not_verified'


def test_sem_alm_apenas_blueprint():
    result = gerar_lowcode_solution(
        LowCodeSolutionGenerateRequest(dry_run=False, include_alm_package=False)
    )
    assert result['status'] == 'blueprint_generated'
    assert result['alm_package'] == {}
    assert result['delivery']['dispatch_receipt'] is None


def test_replay_identidade_estavel_sem_dispatch():
    request = LowCodeSolutionGenerateRequest(dry_run=False)
    first, second = gerar_lowcode_solution(request), gerar_lowcode_solution(request)
    changed = gerar_lowcode_solution(
        LowCodeSolutionGenerateRequest(dry_run=False, solution_name='OutraSolution')
    )
    assert first['idempotency_key'] == second['idempotency_key']
    assert first['idempotency_key'] != changed['idempotency_key']
    assert first['correlation_id'] != second['correlation_id']
    for response in [first, second]:
        assert response['delivery']['external_write_performed'] is False
        assert response['delivery']['dispatch'] == 'not_requested'
        assert response['delivery']['installation_evidence'] is None


def test_entrada_invalida_rejeitada():
    with pytest.raises(ValidationError):
        LowCodeSolutionGenerateRequest(modules=[])
    with pytest.raises(ValidationError):
        LowCodeSolutionGenerateRequest(target_environment='\\n')


def test_perfil_teams_nao_declara_instalacao():
    result = gerar_lowcode_solution(
        LowCodeSolutionGenerateRequest(profile='teams_notification_v2', dry_run=False)
    )
    assert result['delivery']['dispatch'] == 'not_requested'
    assert result['delivery']['installation'] == 'not_verified'
    assert result['delivery']['external_write_performed'] is False
