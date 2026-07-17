import base64
import hashlib
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_lowcode_teams_profile.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

from app.schemas.lowcode_solution import LowCodeSolutionGenerateRequest  # noqa: E402
from app.services.lowcode_solution_factory import gerar_lowcode_solution  # noqa: E402
from materialize_teams_notification_solution import materialize  # noqa: E402


def _request(**overrides):
    values = {
        'profile': 'teams_notification_v2',
        'solution_name': 'valor-ignorado-pelo-perfil',
        'target_environment': 'dev',
        'modules': ['powerautomate'],
        'dry_run': True,
    }
    values.update(overrides)
    return LowCodeSolutionGenerateRequest(**values)


def test_endpoint_factory_delega_para_perfil_teams_notification_v2():
    solution = gerar_lowcode_solution(_request())

    assert solution['profile'] == 'teams_notification_v2'
    assert solution['solution']['unique_name'] == 'ReqSysTeamsNotifications'
    assert solution['flow']['name'] == 'robo_envia_teamsv2'
    assert solution['flow']['version'] == '2.0.0.0'
    assert solution['factory_version'] == '0.2.0'
    assert solution['solution']['target_environment'] == 'dev'


def test_perfil_teams_v2_preserva_contrato_adaptive_card_e_fallback():
    solution = gerar_lowcode_solution(_request())
    properties = solution['trigger_schema']['properties']
    rules = solution['flow']['rendering_rules']

    assert {'adaptiveCard', 'adaptiveCardJson', 'content', 'correlationId'} <= set(properties)
    assert rules[0]['result_mode'] == 'adaptive-card'
    assert rules[1]['result_mode'] == 'adaptive-card-json'
    assert rules[2]['result_mode'] == 'markdown-fallback'
    assert solution['flow']['connection_references'][0]['connector'] == 'shared_teams'


def test_pacote_teams_v2_tem_hash_valido_e_arquivos_de_importacao():
    solution = gerar_lowcode_solution(_request(dry_run=False))
    package = solution['package']
    raw = base64.b64decode(package['zip_base64'])

    assert hashlib.sha256(raw).hexdigest() == package['sha256']
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        names = set(archive.namelist())
    assert any(name.endswith('/powerautomate/flow-definition.json') for name in names)
    assert any(name.endswith('/powerplatform/connection-references.json') for name in names)
    assert any(name.endswith('/powerplatform/environment-variables.json') for name in names)


def test_materializer_grava_zip_e_manifesto(tmp_path):
    result = materialize(tmp_path, target_environment='dev', dry_run=False)

    zip_path = Path(result['zip_path'])
    manifest_path = Path(result['manifest_path'])
    assert zip_path.is_file()
    assert manifest_path.is_file()
    assert result['profile'] == 'teams_notification_v2'
    assert result['flow_name'] == 'robo_envia_teamsv2'
    assert result['import_guardrails']['flow_state_after_import'] == 'off_after_import'
