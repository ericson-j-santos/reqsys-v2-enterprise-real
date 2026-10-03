from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'sync-microsoft-identity-dev.yml'
PRODUCTION_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-production-sync.yml'
ENTERPRISE_WORKFLOW = ROOT / '.github' / 'workflows' / 'fly-enterprise-sync.yml'
MANIFEST = ROOT / 'infra' / 'fly-environments.json'
GOVERNANCE = ROOT / 'backend' / 'config' / 'identity-governance.runtime.json'

INTEGRATION_SECRET_NAMES = {
    'POWER_PLATFORM_TENANT_ID',
    'POWER_PLATFORM_CLIENT_ID',
    'POWER_PLATFORM_CLIENT_SECRET',
    'DATAVERSE_TENANT_ID',
    'DATAVERSE_CLIENT_ID',
    'DATAVERSE_CLIENT_SECRET',
    'DATAVERSE_ENVIRONMENT_URL',
    'SHAREPOINT_GRAPH_CLIENT_SECRET',
}

SHAREPOINT_VARIABLE_NAMES = {'SHAREPOINT_SITE_ID', 'SHAREPOINT_LIST_IA'}


def test_workflow_propaga_identidades_dedicadas_sem_sobrescrever_login_azure():
    text = WORKFLOW.read_text(encoding='utf-8')

    for name in INTEGRATION_SECRET_NAMES:
        assert f'{name}: ${{{{ secrets.{name} }}}}' in text
        assert f'{name}="${name}"' in text
    for name in SHAREPOINT_VARIABLE_NAMES:
        assert f'{name}: ${{{{ vars.{name} }}}}' in text
        assert f'{name}="${name}"' in text

    assert 'AZURE_CLIENT_SECRET="$POWER_PLATFORM_CLIENT_SECRET"' not in text
    assert '"check":"dataverse_whoami"' in text


def test_workflows_hml_e_producao_propagam_segredos_em_operacao_unica():
    for workflow in (PRODUCTION_WORKFLOW, ENTERPRISE_WORKFLOW):
        text = workflow.read_text(encoding='utf-8')
        for name in INTEGRATION_SECRET_NAMES:
            assert f'{name}: ${{{{ secrets.{name} }}}}' in text
            assert f'{name}="${name}"' in text
        for name in SHAREPOINT_VARIABLE_NAMES:
            assert f'{name}: ${{{{ vars.{name} }}}}' in text
            assert f'{name}="${name}"' in text
        assert 'flyctl secrets set \\' in text


def test_manifesto_exige_segredos_dedicados_em_todos_os_ambientes():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))

    for environment in ('dev', 'hml', 'prod'):
        required = set(manifest['environments'][environment]['required_secret_names'])
        assert INTEGRATION_SECRET_NAMES | SHAREPOINT_VARIABLE_NAMES <= required

    forbidden = set(manifest['forbidden_versioned_secret_patterns'])
    assert 'POWER_PLATFORM_CLIENT_SECRET' in forbidden
    assert 'DATAVERSE_CLIENT_SECRET' in forbidden
    assert 'SHAREPOINT_GRAPH_CLIENT_SECRET' in forbidden


def test_registro_sharepoint_tem_um_cliente_dedicado_por_ambiente_sem_segredo_materializado():
    profiles = json.loads(GOVERNANCE.read_text(encoding='utf-8'))

    assert {profile['environment'] for profile in profiles} == {'development', 'staging', 'production'}
    assert len({profile['client_id'] for profile in profiles}) == 3
    assert all(profile['purpose'] == 'sharepoint-package-catalog-read' for profile in profiles)
    assert all(profile['current_secret_ref'] == 'env://SHAREPOINT_GRAPH_CLIENT_SECRET' for profile in profiles)
    assert all('secret' not in profile or profile['secret'].startswith('env://') for profile in profiles)
