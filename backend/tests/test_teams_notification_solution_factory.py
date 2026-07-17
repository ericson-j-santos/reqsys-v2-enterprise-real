import base64
import io
import json
import os
import zipfile

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_teams_solution.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.services.teams_notification_solution_factory import (
    FLOW_NAME,
    FLOW_VERSION,
    SOLUTION_NAME,
    gerar_teams_notification_solution,
)


def test_gera_solution_teams_v2_com_contrato_adaptive_card():
    result = gerar_teams_notification_solution(target_environment='dev', dry_run=True)

    assert result['status'] == 'planned'
    assert result['solution']['unique_name'] == SOLUTION_NAME
    assert result['solution']['version'] == FLOW_VERSION
    assert result['flow']['name'] == FLOW_NAME
    assert result['flow']['state'] == 'off_after_import'
    assert result['governance']['minimum_adaptive_card_version'] == '1.5'
    assert result['governance']['secrets_embedded'] is False

    schema = result['trigger_schema']
    assert schema['additionalProperties'] is False
    assert {'title', 'content', 'correlationId'} <= set(schema['required'])
    assert 'adaptiveCard' in schema['properties']
    assert 'adaptiveCardJson' in schema['properties']

    rules = result['flow']['rendering_rules']
    assert rules[0]['payload_expression'] == "triggerBody()?['adaptiveCard']"
    assert rules[1]['payload_expression'] == "json(triggerBody()?['adaptiveCardJson'])"
    assert rules[2]['result_mode'] == 'markdown-fallback'


def test_solution_exige_connection_reference_e_environment_variables_sem_segredos():
    result = gerar_teams_notification_solution()

    references = result['connection_references']
    assert references == [
        {
            'logical_name': 'reqsys_sharedteams',
            'connector': 'shared_teams',
            'required': True,
        }
    ]

    variables = {item['schema_name']: item for item in result['environment_variables']}
    assert variables['reqsys_TeamsDestination']['required'] is True
    assert variables['reqsys_TeamsFallbackEnabled']['default_value'] is True
    assert variables['reqsys_AdaptiveCardMinimumVersion']['default_value'] == '1.5'
    assert all(item['secret'] is False for item in variables.values())


def test_package_zip_contem_artefatos_governados_e_hash_valido():
    result = gerar_teams_notification_solution()
    package = result['package']

    raw = base64.b64decode(package['zip_base64'])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = set(archive.namelist())
        expected = {
            f'{SOLUTION_NAME}/manifest.json',
            f'{SOLUTION_NAME}/powerautomate/flow-definition.json',
            f'{SOLUTION_NAME}/powerautomate/http-trigger-schema.json',
            f'{SOLUTION_NAME}/powerplatform/connection-references.json',
            f'{SOLUTION_NAME}/powerplatform/environment-variables.json',
            f'{SOLUTION_NAME}/alm/migration-and-rollback.json',
            f'{SOLUTION_NAME}/tests/contract-cases.json',
        }
        assert expected <= names

        flow = json.loads(archive.read(f'{SOLUTION_NAME}/powerautomate/flow-definition.json'))
        assert flow['success_response']['body']['flowVersion'] == FLOW_VERSION
        assert flow['error_response']['body']['errorCode'] == 'TEAMS_POST_FAILED'

    assert len(package['sha256']) == 64
    assert len(result['contract_tests']) == 9


def test_migracao_preserva_v1_e_define_rollback():
    result = gerar_teams_notification_solution(target_environment='dev')
    migration = result['migration']

    assert migration['source_flow'] == 'robo_envia_teamsv1'
    assert migration['target_flow'] == FLOW_NAME
    assert any('paralelo' in step for step in migration['steps'])
    assert any('robo_envia_teamsv1' in step for step in migration['rollback'])
