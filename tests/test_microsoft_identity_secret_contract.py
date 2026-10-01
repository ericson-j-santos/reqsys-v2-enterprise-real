from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'sync-microsoft-identity-dev.yml'
PRODUCTION_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-production-sync.yml'
ENTERPRISE_WORKFLOW = ROOT / '.github' / 'workflows' / 'fly-enterprise-sync.yml'
MANIFEST = ROOT / 'infra' / 'fly-environments.json'

INTEGRATION_SECRET_NAMES = {
    'POWER_PLATFORM_TENANT_ID',
    'POWER_PLATFORM_CLIENT_ID',
    'POWER_PLATFORM_CLIENT_SECRET',
    'DATAVERSE_TENANT_ID',
    'DATAVERSE_CLIENT_ID',
    'DATAVERSE_CLIENT_SECRET',
    'DATAVERSE_ENVIRONMENT_URL',
}


def test_workflow_propaga_identidades_dedicadas_sem_sobrescrever_login_azure():
    text = WORKFLOW.read_text(encoding='utf-8')

    for name in INTEGRATION_SECRET_NAMES:
        assert f'{name}: ${{{{ secrets.{name} }}}}' in text
        assert f'{name}="${name}"' in text

    assert 'AZURE_CLIENT_SECRET="$POWER_PLATFORM_CLIENT_SECRET"' not in text
    assert '"check":"dataverse_whoami"' in text


def test_workflows_hml_e_producao_propagam_segredos_em_operacao_unica():
    for workflow in (PRODUCTION_WORKFLOW, ENTERPRISE_WORKFLOW):
        text = workflow.read_text(encoding='utf-8')
        for name in INTEGRATION_SECRET_NAMES:
            assert f'{name}: ${{{{ secrets.{name} }}}}' in text
            assert f'{name}="${name}"' in text
        assert 'flyctl secrets set \\' in text


def test_manifesto_exige_segredos_dedicados_em_todos_os_ambientes():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))

    for environment in ('dev', 'hml', 'prod'):
        required = set(manifest['environments'][environment]['required_secret_names'])
        assert INTEGRATION_SECRET_NAMES <= required

    forbidden = set(manifest['forbidden_versioned_secret_patterns'])
    assert 'POWER_PLATFORM_CLIENT_SECRET' in forbidden
    assert 'DATAVERSE_CLIENT_SECRET' in forbidden
