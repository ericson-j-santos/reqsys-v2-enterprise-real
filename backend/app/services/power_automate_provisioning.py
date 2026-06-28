"""Provisionamento governado de Power Automate flows.

P0 nao cria flows diretamente pelo runtime do ReqSys. O runtime gera um manifesto
rastreavel e, quando configurado, despacha um GitHub Actions workflow que reutiliza
o repositorio ALM `reqsys-powerplatform-alm` e o padrao LowCodeFactory/pac CLI.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger('reqsys.power_automate_provisioning')

_WORKFLOW_FILE = 'power-automate-flow-provisioning-p0.yml'
_DEFAULT_ALM_REPO = 'ericson-j-santos/reqsys-powerplatform-alm'
_SUPPORTED_TRIGGER_TYPES = {'HttpRequest', 'Recurrence', 'Manual'}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalizar_trigger_type(trigger_type: str | None) -> str:
    value = (trigger_type or 'HttpRequest').strip()
    if value not in _SUPPORTED_TRIGGER_TYPES:
        raise ValueError(f'TriggerType invalido: {value}. Valores aceitos: {sorted(_SUPPORTED_TRIGGER_TYPES)}')
    return value


def gerar_manifesto_provisionamento_flow(
    display_name: str,
    trigger_type: str = 'HttpRequest',
    description: str = '',
    target_environment: str = 'dev',
    solution_name: str = 'ReqSysAutomacao',
    correlation_id: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Gera contrato de provisionamento sem expor segredo.

    O manifesto e idempotente por `flow_id` e deve ser executado pelo pipeline ALM.
    """

    nome = display_name.strip()
    if len(nome) < 5:
        raise ValueError('display_name deve ter pelo menos 5 caracteres')

    trigger = normalizar_trigger_type(trigger_type)
    flow_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{solution_name}:{target_environment}:{nome}')).upper()
    corr = correlation_id or str(uuid.uuid4())
    alm_repo = settings.github_alm_repo or _DEFAULT_ALM_REPO

    return {
        'schema_version': '1.0.0',
        'capability': 'Power Automate Flow Provisioning P0',
        'status': 'planned' if dry_run else 'dispatch_requested',
        'correlation_id': corr,
        'generated_at': _utc_now(),
        'source': {
            'system': 'ReqSys',
            'component': 'hub-lowcode',
            'runtime_environment': settings.normalized_environment,
        },
        'target': {
            'alm_repository': alm_repo,
            'workflow_file': _WORKFLOW_FILE,
            'environment': target_environment,
            'solution_name': solution_name,
        },
        'flow': {
            'flow_id': flow_id,
            'display_name': nome,
            'trigger_type': trigger,
            'description': description.strip(),
            'connection_strategy': 'http_only_sem_user_connections_no_p0',
        },
        'governance': {
            'mode': 'solution_import_via_pac_cli',
            'reuse_detected': 'reqsys-powerplatform-alm/scripts/LowCodeFactory.psm1',
            'requires_human_or_pipeline_approval': True,
            'secrets_required': [
                'POWERPLATFORM_APP_ID',
                'POWERPLATFORM_CLIENT_SECRET',
                'POWERPLATFORM_TENANT_ID',
                'DEV_ENVIRONMENT_URL ou TARGET_ENVIRONMENT_URL',
            ],
            'non_goals_p0': [
                'nao executar Flow Maker API diretamente pelo backend',
                'nao persistir client_secret no ReqSys',
                'nao criar conexoes de usuario automaticamente',
            ],
        },
    }


async def despachar_workflow_provisionamento(manifesto: dict[str, Any]) -> dict[str, Any]:
    """Despacha GitHub Actions workflow quando GITHUB_PAT estiver configurado.

    Retorna degradado quando o token nao existe; isso permite ambiente DEV seguro.
    """

    repo = manifesto['target']['alm_repository']
    token = settings.github_pat
    if not token:
        return {
            'dispatched': False,
            'configured': False,
            'reason': 'GITHUB_PAT nao configurado no ReqSys',
            'workflow_file': _WORKFLOW_FILE,
            'repository': repo,
            'correlation_id': manifesto['correlation_id'],
        }

    url = f'https://api.github.com/repos/{repo}/actions/workflows/{_WORKFLOW_FILE}/dispatches'
    payload = {
        'ref': 'main',
        'inputs': {
            'display_name': manifesto['flow']['display_name'],
            'trigger_type': manifesto['flow']['trigger_type'],
            'target_environment': manifesto['target']['environment'],
            'solution_name': manifesto['target']['solution_name'],
            'correlation_id': manifesto['correlation_id'],
            'dry_run': 'false',
        },
    }
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28',
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload, headers=headers)
        if response.status_code == 204:
            return {
                'dispatched': True,
                'configured': True,
                'repository': repo,
                'workflow_file': _WORKFLOW_FILE,
                'correlation_id': manifesto['correlation_id'],
            }
        logger.warning('provisionamento_flow_dispatch_http_%s body=%s', response.status_code, response.text[:300])
        return {
            'dispatched': False,
            'configured': True,
            'repository': repo,
            'workflow_file': _WORKFLOW_FILE,
            'status_code': response.status_code,
            'error': response.text[:500],
            'correlation_id': manifesto['correlation_id'],
        }
    except Exception as exc:
        logger.warning('provisionamento_flow_dispatch_erro=%s', exc)
        return {
            'dispatched': False,
            'configured': True,
            'repository': repo,
            'workflow_file': _WORKFLOW_FILE,
            'error': str(exc),
            'correlation_id': manifesto['correlation_id'],
        }
